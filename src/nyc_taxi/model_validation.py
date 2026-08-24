"""Expanding-window backtests, airport specialization, and model release gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from math import gcd
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .approvals import promote_approved_artifact
from .download import sha256_file
from .forecast import AIRPORT_ZONE_IDS, MODEL_FEATURES, load_hourly, make_feature_table, metrics
from .monitoring import score_frames
from .prediction import _future_features, validate_forecast


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_EVALUATION_PLAN_KEYS = {
    "schema_version",
    "plan_id",
    "rationale",
    "candidate_model_sha256",
    "training_period_end",
    "horizon_hours",
    "origin_hour_step",
    "observational_only",
    "promotion_permitted",
    "blocks",
    "metric_roles",
}
_EVALUATION_BLOCK_KEYS = {"id", "start_date", "end_date"}
_EVALUATION_METRIC_ROLES = {
    "daily_win_rate": "proposed_release_criterion",
    "worst_day_degradation": "proposed_release_criterion",
    "daily_drift": "advisory",
    "horizon_clock": "diagnostic_only",
}


def _validate_sha256(value: str, label: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} must be 64 lowercase hexadecimal characters")
    return value


def _reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate evaluation plan key: {key}")
        result[key] = value
    return result


def _strict_plan_date(value: object, label: str) -> pd.Timestamp:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO calendar date")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO calendar date") from exc
    if parsed.strftime("%Y-%m-%d") != value:
        raise ValueError(f"{label} must be an ISO calendar date")
    return pd.Timestamp(parsed)


def _validate_evaluation_plan(plan: object) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("Evaluation plan must be a JSON object")
    if set(plan) != _EVALUATION_PLAN_KEYS:
        missing = sorted(_EVALUATION_PLAN_KEYS - set(plan))
        unknown = sorted(set(plan) - _EVALUATION_PLAN_KEYS)
        raise ValueError(
            f"Evaluation plan schema mismatch; missing={missing}, unknown={unknown}"
        )
    if plan["schema_version"] != "1.0":
        raise ValueError("Unsupported evaluation plan schema_version")
    if not isinstance(plan["plan_id"], str) or not plan["plan_id"].strip():
        raise ValueError("Evaluation plan plan_id must be a non-empty string")
    rationale = plan["rationale"]
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("Evaluation plan rationale must be a non-empty relative path")
    rationale_path = Path(rationale)
    if rationale_path.is_absolute() or ".." in rationale_path.parts:
        raise ValueError("Evaluation plan rationale must be a safe relative path")
    _validate_sha256(plan["candidate_model_sha256"], "candidate_model_sha256")
    training_end = _strict_plan_date(
        plan["training_period_end"], "training_period_end"
    )
    if type(plan["horizon_hours"]) is not int or plan["horizon_hours"] != 24:
        raise ValueError("Evaluation plan horizon_hours must equal 24")
    origin_hour_step = plan["origin_hour_step"]
    if (
        type(origin_hour_step) is not int
        or not 1 <= origin_hour_step < 24
        or gcd(origin_hour_step, 24) != 1
    ):
        raise ValueError(
            "Evaluation plan origin_hour_step must be between 1 and 23 and coprime with 24"
        )
    if plan["observational_only"] is not True:
        raise ValueError("Evaluation plan must be observational_only")
    if plan["promotion_permitted"] is not False:
        raise ValueError("Evaluation plan must prohibit promotion")
    if plan["metric_roles"] != _EVALUATION_METRIC_ROLES:
        raise ValueError("Evaluation plan metric_roles do not match the closed schema")

    blocks = plan["blocks"]
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("Evaluation plan blocks must be a non-empty list")
    block_ids = set()
    previous_end = None
    first_start = None
    for index, block in enumerate(blocks):
        if not isinstance(block, dict) or set(block) != _EVALUATION_BLOCK_KEYS:
            raise ValueError(f"Evaluation block {index} does not match the closed schema")
        block_id = block["id"]
        if not isinstance(block_id, str) or not block_id.strip():
            raise ValueError(f"Evaluation block {index} id must be a non-empty string")
        if block_id in block_ids:
            raise ValueError(f"Duplicate evaluation block id: {block_id}")
        block_ids.add(block_id)
        block_start = _strict_plan_date(block["start_date"], f"block {block_id} start_date")
        block_end = _strict_plan_date(block["end_date"], f"block {block_id} end_date")
        if block_end - block_start != timedelta(days=23):
            raise ValueError(f"Evaluation block {block_id} must contain exactly 24 days")
        if previous_end is not None and block_start <= previous_end:
            raise ValueError("Evaluation plan blocks must be chronological and non-overlapping")
        first_start = block_start if first_start is None else first_start
        previous_end = block_end
    if training_end >= first_start:
        raise ValueError("Evaluation plan training period must end before its first block")
    return plan


def _load_evaluation_plan(path: Path, expected_sha256: str) -> tuple[dict, str]:
    """Load and authenticate a closed-schema plan by canonical JSON identity."""
    _validate_sha256(expected_sha256, "expected_evaluation_plan_sha256")
    try:
        plan = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid evaluation plan JSON: {exc.msg}") from exc
    _validate_evaluation_plan(plan)
    canonical = json.dumps(
        plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    actual_sha256 = hashlib.sha256(canonical).hexdigest()
    if actual_sha256 != expected_sha256:
        raise PermissionError(
            "Evaluation plan SHA-256 mismatch: expected "
            f"{expected_sha256}, got {actual_sha256}"
        )
    return plan, actual_sha256


def _model(max_iter: int) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="poisson", learning_rate=0.08, max_iter=max_iter,
        max_leaf_nodes=31, l2_regularization=1.0, random_state=42,
    )


def release_decision(folds: list[dict]) -> dict:
    improvements = [
        (fold["baseline"]["wape"] - fold["candidate"]["wape"]) / fold["baseline"]["wape"]
        for fold in folds
    ]
    airport_improvements = [
        (fold["airport_global_model"]["wape"] - fold["airport_specialist"]["wape"])
        / fold["airport_global_model"]["wape"] for fold in folds
    ]
    event_folds = [fold for fold in folds if fold.get("event_candidate")]
    event_improvements = [
        (fold["event_previous_year"]["wape"] - fold["event_candidate"]["wape"])
        / fold["event_previous_year"]["wape"] for fold in event_folds
    ]
    ordinary_improvements = [
        (fold["ordinary_baseline"]["wape"] - fold["ordinary_candidate"]["wape"])
        / fold["ordinary_baseline"]["wape"] for fold in folds
    ]
    new_year = [fold for fold in folds if fold.get("new_year_candidate")]
    checks = {
        "minimum_four_folds": len(folds) >= 4,
        "overall_win_rate_at_least_75pct": np.mean(np.array(improvements) > 0) >= 0.75,
        "median_wape_improvement_at_least_5pct": np.median(improvements) >= 0.05,
        "worst_fold_degradation_no_more_than_2pct": min(improvements) >= -0.02,
        "airport_win_rate_at_least_two_thirds": np.mean(np.array(airport_improvements) > 0) >= 2 / 3,
        "at_least_three_major_event_folds": len(event_folds) >= 3,
        "event_median_improves_previous_year": bool(event_improvements) and np.median(event_improvements) > 0,
        "ordinary_days_never_degrade_over_2pct": min(ordinary_improvements) >= -0.02,
        "new_year_window_improves_previous_week": bool(new_year) and all(
            fold["new_year_candidate"]["wape"] < fold["new_year_previous_week"]["wape"] for fold in new_year
        ),
        "new_year_high_demand_recall_at_least_80pct": bool(new_year) and all(
            fold["new_year_candidate"]["high_demand_recall"] >= 0.80 for fold in new_year
        ),
    }
    return {
        "passed": all(checks.values()), "checks": {key: bool(value) for key, value in checks.items()},
        "overall_relative_wape_improvements": improvements,
        "airport_relative_wape_improvements": airport_improvements,
        "event_relative_wape_improvements_vs_previous_year": event_improvements,
        "ordinary_relative_wape_improvements": ordinary_improvements,
    }


def _previous_year_prediction(rows: pd.DataFrame, history: pd.DataFrame) -> np.ndarray:
    keys = rows[["pickup_zone_id", "pickup_hour"]].copy()
    keys["comparison_hour"] = keys["pickup_hour"].map(lambda value: value - pd.DateOffset(years=1))
    prior = history[["pickup_zone_id", "pickup_hour", "trip_count"]].rename(
        columns={"pickup_hour": "comparison_hour", "trip_count": "previous_year"}
    )
    return keys.merge(prior, on=["pickup_zone_id", "comparison_hour"], how="left")["previous_year"].fillna(0).to_numpy()


def _recursive_day_forecast(
    hourly: pd.DataFrame,
    artifact: dict,
    forecast_day: pd.Timestamp,
) -> pd.DataFrame:
    """Forecast 24 hours from one UTC-naive origin using only earlier observations."""
    forecast_start = pd.Timestamp(forecast_day)
    if forecast_start.tzinfo is not None:
        raise ValueError("Recursive shadow forecast origin must be UTC-naive")
    if forecast_start != forecast_start.floor("h"):
        raise ValueError("Recursive shadow forecast origin must align to an hour")
    history_end = forecast_start - timedelta(hours=1)
    history_hours = pd.date_range(history_end - timedelta(hours=167), history_end, freq="h")
    zones = np.sort(hourly["pickup_zone_id"].dropna().astype(int).unique())
    observed = hourly[hourly["pickup_hour"].between(history_hours.min(), history_hours.max())]
    pivot = observed.pivot_table(
        index="pickup_hour", columns="pickup_zone_id", values="trip_count", aggfunc="sum"
    ).reindex(history_hours).fillna(0.0)
    history = {
        int(zone): pivot[zone].tolist() if zone in pivot else [0.0] * 168
        for zone in zones
    }
    airport_ids = set(map(int, artifact["airport_zone_ids"]))
    model_features = artifact.get("features", [])
    if not set(model_features).issubset(MODEL_FEATURES):
        raise ValueError("Model artifact requires features unavailable to recursive shadow evaluation")

    rows = []
    for horizon_hour in range(1, 25):
        forecast_hour = history_end + timedelta(hours=horizon_hour)
        features = _future_features(zones, forecast_hour, history, airport_ids)
        predictions = np.clip(artifact["global_model"].predict(features[model_features]), 0, None)
        airport_mask = features["pickup_zone_id"].isin(airport_ids).to_numpy()
        event_mask = (
            features["is_event_window"].eq(1)
            & ~features["pickup_zone_id"].isin(airport_ids)
        ).to_numpy()
        if event_mask.any() and "event_model" in artifact:
            predictions[event_mask] = np.clip(
                artifact["event_model"].predict(features.loc[event_mask, model_features]), 0, None
            )
        if airport_mask.any():
            predictions[airport_mask] = np.clip(
                artifact["airport_model"].predict(features.loc[airport_mask, model_features]), 0, None
            )
        for zone, prediction, is_airport, is_event, event_code, is_holiday in zip(
            zones,
            predictions,
            airport_mask,
            features["is_event_window"].to_numpy(),
            features["event_code"].to_numpy(),
            features["is_us_holiday"].to_numpy(),
        ):
            history[int(zone)].append(float(prediction))
            rows.append({
                "forecast_hour": forecast_hour,
                "pickup_zone_id": int(zone),
                "predicted_trip_count": float(prediction),
                "model_type": "airport_specialist" if is_airport else "event_specialist" if is_event and "event_model" in artifact else "global",
                "event_code": int(event_code),
                "is_event_window": int(is_event),
                "is_us_holiday": int(is_holiday),
                "horizon_hour": horizon_hour,
            })
    forecast = pd.DataFrame(rows)
    gate = validate_forecast(forecast, set(map(int, zones)), 24, airport_ids)
    if not gate["passed"]:
        raise ValueError(f"Recursive shadow forecast failed validation: {gate['checks']}")
    return forecast


def _recursive_origins(
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    origin_hour_step: int = 0,
) -> list[pd.Timestamp]:
    """Return deterministic UTC-naive origins for inclusive calendar dates."""
    if not 0 <= origin_hour_step < 24:
        raise ValueError("origin_hour_step must be between 0 and 23")
    if origin_hour_step and gcd(origin_hour_step, 24) != 1:
        raise ValueError("Non-zero origin_hour_step must be coprime with 24")
    return [
        day + timedelta(hours=(origin_hour_step * index) % 24)
        for index, day in enumerate(pd.date_range(start.normalize(), end.normalize(), freq="D"))
    ]


def _shadow_segments(
    scored: pd.DataFrame,
    column: str,
    *,
    limit: int | None = None,
    min_actual: float = 0.0,
) -> list[dict]:
    output = []
    for key, group in scored.groupby(column, sort=True):
        actual = group["trip_count"].to_numpy(dtype=float)
        if actual.sum() < min_actual:
            continue
        predicted = group["predicted_trip_count"].to_numpy(dtype=float)
        baseline = group["previous_week"].to_numpy(dtype=float)
        actual_total = max(float(actual.sum()), 1.0)
        output.append({
            "segment": str(key),
            "rows": len(group),
            "wape": float(np.abs(actual - predicted).sum() / actual_total),
            "bias": float((predicted - actual).sum() / actual_total),
            "baseline_wape": float(np.abs(actual - baseline).sum() / actual_total),
        })
    ranked = sorted(output, key=lambda row: row["wape"], reverse=True)
    return ranked[:limit] if limit is not None else ranked


def _horizon_clock_segments(scored: pd.DataFrame) -> list[dict]:
    output = []
    for (horizon_hour, clock_hour), group in scored.groupby(
        ["horizon_hour", "forecast_clock_hour"], sort=True
    ):
        actual = group["trip_count"].to_numpy(dtype=float)
        predicted = group["predicted_trip_count"].to_numpy(dtype=float)
        baseline = group["previous_week"].to_numpy(dtype=float)
        actual_total = max(float(actual.sum()), 1.0)
        output.append({
            "horizon_hour": int(horizon_hour),
            "clock_hour_utc": int(clock_hour),
            "rows": len(group),
            "actual_demand": float(actual.sum()),
            "wape": float(np.abs(actual - predicted).sum() / actual_total),
            "baseline_wape": float(np.abs(actual - baseline).sum() / actual_total),
            "excess_absolute_error_vs_previous_week": float(
                np.abs(actual - predicted).sum() - np.abs(actual - baseline).sum()
            ),
        })
    return output


def recursive_shadow_evaluation(
    hourly_path: Path,
    model_path: Path,
    output_dir: Path,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    origin_hour_step: int = 0,
    evaluation_plan_path: Path | None = None,
    expected_evaluation_plan_sha256: str | None = None,
    evaluation_block: str | None = None,
    expected_model_sha256: str | None = None,
) -> dict:
    """Write read-only, observational 24-hour recursive evidence; never promote artifacts."""
    binding_values = (
        evaluation_plan_path,
        expected_evaluation_plan_sha256,
        evaluation_block,
        expected_model_sha256,
    )
    bound = any(value is not None for value in binding_values)
    plan = None
    plan_sha256 = None
    if bound:
        if not all(value is not None for value in binding_values):
            raise ValueError(
                "Bound recursive evaluation requires evaluation plan path, plan SHA-256, "
                "block id, and model SHA-256"
            )
        if start_date is not None or end_date is not None or origin_hour_step != 0:
            raise ValueError(
                "Bound recursive evaluation derives dates and origin step from the plan"
            )
        _validate_sha256(expected_model_sha256, "expected_model_sha256")
        plan, plan_sha256 = _load_evaluation_plan(
            evaluation_plan_path, expected_evaluation_plan_sha256
        )
        blocks = {block["id"]: block for block in plan["blocks"]}
        if evaluation_block not in blocks:
            raise ValueError(f"Evaluation block is not present in plan: {evaluation_block}")
        block = blocks[evaluation_block]
        if plan["candidate_model_sha256"] != expected_model_sha256:
            raise PermissionError(
                "Expected model SHA-256 does not match the evaluation plan candidate"
            )
        model_sha256 = sha256_file(model_path)
        if model_sha256 != expected_model_sha256:
            raise PermissionError(
                "Model SHA-256 mismatch: expected "
                f"{expected_model_sha256}, got {model_sha256}"
            )
        start_date = block["start_date"]
        end_date = block["end_date"]
        origin_hour_step = plan["origin_hour_step"]
        identity_binding = {
            "status": "verified",
            "plan_id": plan["plan_id"],
            "block_id": evaluation_block,
            "evaluation_plan_sha256": plan_sha256,
            "candidate_model_sha256": model_sha256,
            "verified_before_model_load": True,
            "reverified_before_report_write": True,
        }
        artifact = joblib.load(model_path)
        hourly = load_hourly(hourly_path)
    else:
        if start_date is None or end_date is None:
            raise ValueError("Unbound recursive evaluation requires start_date and end_date")
        if origin_hour_step != 0:
            raise PermissionError(
                "Staggered recursive evaluation requires a bound evaluation plan"
            )
        hourly = load_hourly(hourly_path)
        identity_binding = {
            "status": "unbound_exploratory",
            "reason": "legacy_midnight_shadow",
            "verified_before_model_load": False,
            "reverified_before_report_write": False,
        }

    hourly["pickup_hour"] = pd.to_datetime(hourly["pickup_hour"])
    start, end = pd.Timestamp(start_date).normalize(), pd.Timestamp(end_date).normalize()
    if end < start:
        raise ValueError("end_date must not precede start_date")
    origins = _recursive_origins(start, end, origin_hour_step=origin_hour_step)
    if hourly["pickup_hour"].min() > min(origins) - timedelta(hours=168):
        raise ValueError("At least 168 hours of pre-forecast history are required")
    if not bound:
        model_sha256 = sha256_file(model_path)
        artifact = joblib.load(model_path)
    training_period = artifact.get("training_period")
    if training_period and pd.Period(training_period[-1], freq="M") >= min(origins).to_period("M"):
        raise ValueError("Model training period must end before the recursive shadow period")
    forecasts = []
    daily = []
    last_target_hour = max(origins) + timedelta(hours=23)
    actual = hourly[
        hourly["pickup_hour"].between(min(origins), last_target_hour)
    ].copy()
    for origin in origins:
        forecast = _recursive_day_forecast(
            hourly[hourly["pickup_hour"] < origin], artifact, origin
        )
        origin_end = origin + timedelta(hours=23)
        origin_actual = actual[actual["pickup_hour"].between(origin, origin_end)]
        target_hours = pd.date_range(origin, origin_end, freq="h")
        actual_hours = pd.DatetimeIndex(origin_actual["pickup_hour"].drop_duplicates())
        if not target_hours.isin(actual_hours).all():
            raise ValueError(f"Incomplete actuals for shadow origin {origin.isoformat()}")
        available_actual = hourly[hourly["pickup_hour"] <= origin_end]
        score = score_frames(forecast, available_actual)
        daily.append({
            "date": str(origin.date()),
            "forecast_origin": origin.isoformat(),
            "forecast_end": origin_end.isoformat(),
            "origin_hour_utc": int(origin.hour),
            "candidate_wape": score["overall"]["wape"],
            "baseline_wape": score["previous_week_baseline"]["wape"],
            "relative_wape_improvement_vs_previous_week": score["overall"]["relative_wape_improvement_vs_previous_week"],
            "candidate_won": score["overall"]["wape"] < score["previous_week_baseline"]["wape"],
            "bias": score["overall"]["bias"],
            "high_demand_recall": score["overall"]["high_demand_recall"],
            "absolute_drift": score["drift"],
        })
        forecasts.append(forecast)

    combined_forecast = pd.concat(forecasts, ignore_index=True)
    combined_score = score_frames(combined_forecast, hourly)
    scored = combined_forecast.merge(
        actual.groupby(["pickup_zone_id", "pickup_hour"], as_index=False)["trip_count"].sum(),
        left_on=["pickup_zone_id", "forecast_hour"],
        right_on=["pickup_zone_id", "pickup_hour"],
        how="left",
    )
    baseline = hourly.rename(columns={"pickup_hour": "forecast_hour", "trip_count": "previous_week"})
    baseline["forecast_hour"] = baseline["forecast_hour"] + timedelta(days=7)
    scored = scored.merge(
        baseline[["pickup_zone_id", "forecast_hour", "previous_week"]],
        on=["pickup_zone_id", "forecast_hour"], how="left",
    ).fillna({"trip_count": 0.0, "previous_week": 0.0})
    scored["market"] = np.where(scored["pickup_zone_id"].isin(AIRPORT_ZONE_IDS), "airport", "non_airport")
    scored["calendar_segment"] = np.where(
        scored["is_event_window"].eq(1), "event_window",
        np.where(
            scored["is_us_holiday"].eq(1), "holiday",
            np.where(scored["forecast_hour"].dt.dayofweek.ge(5), "weekend", "ordinary_weekday"),
        ),
    )
    scored["forecast_clock_hour"] = scored["forecast_hour"].dt.hour
    horizon_clock = _horizon_clock_segments(scored)
    wins = sum(row["candidate_won"] for row in daily)
    origin_hours = [int(origin.hour) for origin in origins]
    complete_crossing = (
        len(origins) == 24
        and len(set(origin_hours)) == 24
        and len(horizon_clock) == 24 * 24
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_type": (
            "out_of_time_staggered_24h_recursive_shadow"
            if origin_hour_step
            else "out_of_time_daily_24h_recursive_shadow"
        ),
        "observational_only": True,
        "model_sha256": model_sha256,
        "identity_binding": identity_binding,
        "period": {"start": str(start.date()), "end": str(end.date()), "days": len(daily)},
        "origin_schedule": {
            "strategy": "staggered_utc_hour" if origin_hour_step else "midnight_utc",
            "hour_step": origin_hour_step,
            "origins": [origin.isoformat() for origin in origins],
            "unique_origin_hours": len(set(origin_hours)),
        },
        "horizon_clock_crossing": {
            "observed_cells": len(horizon_clock),
            "expected_cells": 24 * 24,
            "complete": complete_crossing,
        },
        "daily_baseline_wins": {"wins": wins, "days": len(daily), "rate": wins / len(daily)},
        "daily": daily,
        "overall": combined_score["overall"],
        "previous_week_baseline": combined_score["previous_week_baseline"],
        "absolute_drift": combined_score["drift"],
        "segments": {
            "recursive_horizon": _shadow_segments(scored, "horizon_hour"),
            "forecast_clock_hour": _shadow_segments(scored, "forecast_clock_hour"),
            "horizon_clock": horizon_clock,
            "calendar": _shadow_segments(scored, "calendar_segment"),
            "market": _shadow_segments(scored, "market"),
            "worst_zones": _shadow_segments(
                scored, "pickup_zone_id", limit=15, min_actual=100.0
            ),
        },
        "promotion": {"status": "not_permitted", "reason": "observational_shadow_only"},
    }
    if bound:
        _load_evaluation_plan(evaluation_plan_path, expected_evaluation_plan_sha256)
        if sha256_file(model_path) != expected_model_sha256:
            raise PermissionError("Model changed during evaluation; report was not replaced")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "recursive_shadow.json"
    staging_path = output_dir / "recursive_shadow.json.part"
    staging_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    staging_path.replace(report_path)
    return report


def rolling_backtest(
    hourly_path: Path,
    output_dir: Path,
    *,
    first_test: str = "2024-07",
    max_iter: int = 60,
    approval_file: Path | None = None,
) -> dict:
    features = make_feature_table(load_hourly(hourly_path))
    periods = features["pickup_hour"].dt.to_period("M")
    test_periods = [period for period in sorted(periods.unique()) if period >= pd.Period(first_test)]
    folds = []
    for test_period in test_periods:
        train = features.loc[periods < test_period]
        test = features.loc[periods == test_period]
        if train.empty or test.empty:
            continue
        threshold = float(train["trip_count"].quantile(0.9))
        global_model = _model(max_iter)
        global_model.fit(train[MODEL_FEATURES], train["trip_count"])
        global_prediction = np.clip(global_model.predict(test[MODEL_FEATURES]), 0, None)

        airport_train = train[train["pickup_zone_id"].isin(AIRPORT_ZONE_IDS)]
        airport_test = test[test["pickup_zone_id"].isin(AIRPORT_ZONE_IDS)]
        airport_model = _model(max_iter)
        airport_model.fit(airport_train[MODEL_FEATURES], airport_train["trip_count"])
        airport_prediction = np.clip(airport_model.predict(airport_test[MODEL_FEATURES]), 0, None)
        airport_mask = test["pickup_zone_id"].isin(AIRPORT_ZONE_IDS).to_numpy()
        global_airport_prediction = global_prediction[airport_mask]
        candidate_prediction = global_prediction.copy()
        candidate_prediction[airport_mask] = airport_prediction

        event_train = train[(train["is_event_window"] == 1) & ~train["pickup_zone_id"].isin(AIRPORT_ZONE_IDS)]
        event_mask = (test["is_event_window"].eq(1) & ~test["pickup_zone_id"].isin(AIRPORT_ZONE_IDS)).to_numpy()
        if not event_train.empty and event_mask.any():
            event_model = _model(max_iter)
            event_weights = (
                1.0 + 2.0 * event_train["is_new_year_window"]
                + 1.0 * event_train["trip_count"].ge(threshold)
            )
            event_model.fit(event_train[MODEL_FEATURES], event_train["trip_count"], sample_weight=event_weights)
            candidate_prediction[event_mask] = np.clip(event_model.predict(test.loc[event_mask, MODEL_FEATURES]), 0, None)

        event_all_mask = test["is_event_window"].eq(1).to_numpy()
        ordinary_mask = ~event_all_mask
        fold = {
            "test_month": str(test_period), "train_rows": len(train), "test_rows": len(test),
            "baseline": metrics(test["trip_count"], test["lag_168"].to_numpy(), threshold),
            "candidate": metrics(test["trip_count"], candidate_prediction, threshold),
            "ordinary_baseline": metrics(test.loc[ordinary_mask, "trip_count"], test.loc[ordinary_mask, "lag_168"].to_numpy(), threshold),
            "ordinary_candidate": metrics(test.loc[ordinary_mask, "trip_count"], candidate_prediction[ordinary_mask], threshold),
            "airport_global_model": metrics(airport_test["trip_count"], global_airport_prediction, threshold),
            "airport_specialist": metrics(airport_test["trip_count"], airport_prediction, threshold),
        }
        if event_all_mask.any():
            event_test = test.loc[event_all_mask]
            fold.update({
                "event_previous_week": metrics(event_test["trip_count"], event_test["lag_168"].to_numpy(), threshold),
                "event_previous_year": metrics(event_test["trip_count"], _previous_year_prediction(event_test, features), threshold),
                "event_candidate": metrics(event_test["trip_count"], candidate_prediction[event_all_mask], threshold),
            })
        new_year_mask = test["is_new_year_window"].eq(1).to_numpy()
        if new_year_mask.any():
            fold.update({
                "new_year_previous_week": metrics(test.loc[new_year_mask, "trip_count"], test.loc[new_year_mask, "lag_168"].to_numpy(), threshold),
                "new_year_previous_year": metrics(test.loc[new_year_mask, "trip_count"], _previous_year_prediction(test.loc[new_year_mask], features), threshold),
                "new_year_candidate": metrics(test.loc[new_year_mask, "trip_count"], candidate_prediction[new_year_mask], threshold),
            })
        folds.append(fold)

    decision = release_decision(folds)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "folds": folds, "release_gate": decision}
    output_dir.mkdir(parents=True, exist_ok=True)

    final_global, final_airport, final_event = _model(max_iter), _model(max_iter), _model(max_iter)
    final_global.fit(features[MODEL_FEATURES], features["trip_count"])
    airport = features[features["pickup_zone_id"].isin(AIRPORT_ZONE_IDS)]
    final_airport.fit(airport[MODEL_FEATURES], airport["trip_count"])
    event = features[(features["is_event_window"] == 1) & ~features["pickup_zone_id"].isin(AIRPORT_ZONE_IDS)]
    final_threshold = float(features["trip_count"].quantile(0.9))
    final_event_weights = (
        1.0 + 2.0 * event["is_new_year_window"]
        + 1.0 * event["trip_count"].ge(final_threshold)
    )
    final_event.fit(event[MODEL_FEATURES], event["trip_count"], sample_weight=final_event_weights)
    artifact = {
        "global_model": final_global, "airport_model": final_airport, "event_model": final_event,
        "airport_zone_ids": AIRPORT_ZONE_IDS, "features": MODEL_FEATURES,
        "training_period": [str(periods.min()), str(periods.max())], "release_gate": decision,
    }
    candidate_path = output_dir / "candidate.joblib"
    joblib.dump(artifact, candidate_path)
    report["promotion"] = {"status": "blocked", "reason": "release_gate_failed"}
    if decision["passed"]:
        report["promotion"] = {
            "status": "awaiting_human_approval",
            "candidate_sha256": sha256_file(candidate_path),
        }
    (output_dir / "rolling_backtest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if decision["passed"] and approval_file is not None:
        approval = promote_approved_artifact(
            candidate_path,
            output_dir / "production.joblib",
            approval_file,
            action="model_promotion",
        )
        report["promotion"] = {
            "status": "promoted",
            "reviewer": approval["reviewer"],
            "approved_at": approval["approved_at"],
            "candidate_sha256": approval["artifact_sha256"],
        }
    (output_dir / "rolling_backtest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run expanding-window NYC demand backtests")
    parser.add_argument("--input", type=Path, default=Path("data/processed/hourly_zone_demand.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/demand_release"))
    parser.add_argument("--first-test", default="2024-07")
    parser.add_argument("--max-iter", type=int, default=60)
    parser.add_argument("--approval-file", type=Path)
    parser.add_argument("--shadow-model", type=Path)
    parser.add_argument("--shadow-start")
    parser.add_argument("--shadow-end")
    parser.add_argument("--shadow-origin-hour-step", type=int, default=0)
    parser.add_argument("--evaluation-plan", type=Path)
    parser.add_argument("--expected-evaluation-plan-sha256")
    parser.add_argument("--evaluation-block")
    parser.add_argument("--expected-model-sha256")
    args = parser.parse_args(argv)
    if args.shadow_model is not None:
        binding_values = (
            args.evaluation_plan,
            args.expected_evaluation_plan_sha256,
            args.evaluation_block,
            args.expected_model_sha256,
        )
        bound = any(value is not None for value in binding_values)
        if bound and not all(value is not None for value in binding_values):
            parser.error(
                "bound shadow evaluation requires --evaluation-plan, "
                "--expected-evaluation-plan-sha256, --evaluation-block, and "
                "--expected-model-sha256"
            )
        if bound and (
            args.shadow_start is not None
            or args.shadow_end is not None
            or args.shadow_origin_hour_step != 0
        ):
            parser.error(
                "bound shadow evaluation derives dates and origin step from its plan"
            )
        if not bound and (not args.shadow_start or not args.shadow_end):
            parser.error("unbound --shadow-model requires --shadow-start and --shadow-end")
        if not bound and args.shadow_origin_hour_step != 0:
            parser.error("staggered shadow evaluation requires a bound evaluation plan")
        report = recursive_shadow_evaluation(
            args.input, args.shadow_model, args.output_dir,
            start_date=args.shadow_start, end_date=args.shadow_end,
            origin_hour_step=args.shadow_origin_hour_step,
            evaluation_plan_path=args.evaluation_plan,
            expected_evaluation_plan_sha256=args.expected_evaluation_plan_sha256,
            evaluation_block=args.evaluation_block,
            expected_model_sha256=args.expected_model_sha256,
        )
        print(json.dumps(report, indent=2))
        return 0
    report = rolling_backtest(
        args.input, args.output_dir, first_test=args.first_test, max_iter=args.max_iter,
        approval_file=args.approval_file,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["release_gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
