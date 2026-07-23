"""Expanding-window backtests, airport specialization, and model release gates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from .forecast import AIRPORT_ZONE_IDS, MODEL_FEATURES, load_hourly, make_feature_table, metrics


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


def rolling_backtest(hourly_path: Path, output_dir: Path, *, first_test: str = "2024-07", max_iter: int = 60) -> dict:
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
    (output_dir / "rolling_backtest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

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
    if decision["passed"]:
        temporary = output_dir / "production.joblib.part"
        joblib.dump(artifact, temporary)
        temporary.replace(output_dir / "production.joblib")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run expanding-window NYC demand backtests")
    parser.add_argument("--input", type=Path, default=Path("data/processed/hourly_zone_demand.parquet"))
    parser.add_argument("--output-dir", type=Path, default=Path("models/demand_release"))
    parser.add_argument("--first-test", default="2024-07")
    parser.add_argument("--max-iter", type=int, default=60)
    args = parser.parse_args(argv)
    report = rolling_backtest(args.input, args.output_dir, first_test=args.first_test, max_iter=args.max_iter)
    print(json.dumps(report, indent=2))
    return 0 if report["release_gate"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
