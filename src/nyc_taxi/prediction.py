"""Governed recursive 24-hour demand inference and publication."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd

from .approvals import require_approval
from .download import sha256_file
from .forecast import LAGS, MODEL_FEATURES, ROLLING_WINDOWS, _us_holiday, load_hourly
from .events import event_features


def archive_current(output: Path, lineage_output: Path) -> Path | None:
    """Archive the currently published immutable pair before replacement."""
    if not output.is_file() or not lineage_output.is_file():
        return None
    lineage = json.loads(lineage_output.read_text(encoding="utf-8"))
    generated = datetime.fromisoformat(lineage["generated_at"]).astimezone(timezone.utc)
    forecast_date = str(lineage["forecast_start"])[:10]
    stamp = generated.strftime("%Y%m%dT%H%M%SZ")
    archive = output.parent / "archive" / f"forecast_date={forecast_date}" / f"generated_at={stamp}"
    archive.mkdir(parents=True, exist_ok=True)
    archived_output = archive / "forecast.parquet"
    archived_lineage = archive / "lineage.json"
    if not archived_output.exists():
        shutil.copy2(output, archived_output)
    if not archived_lineage.exists():
        shutil.copy2(lineage_output, archived_lineage)
    return archive


def _future_features(zones: np.ndarray, timestamp: pd.Timestamp, history: dict[int, list[float]], airport_ids: set[int]) -> pd.DataFrame:
    frame = pd.DataFrame({"pickup_zone_id": zones.astype(int)})
    frame["hour"] = timestamp.hour
    frame["day_of_week"] = timestamp.dayofweek
    frame["month"] = timestamp.month
    frame["is_weekend"] = int(timestamp.dayofweek >= 5)
    frame["is_us_holiday"] = int(_us_holiday(pd.Series([timestamp])).iloc[0])
    event = event_features(pd.Series([timestamp])).iloc[0]
    for column, value in event.items():
        frame[column] = value
    frame["is_airport_zone"] = frame["pickup_zone_id"].isin(airport_ids).astype(int)
    frame["temperature_c"] = 0.0
    frame["precipitation_mm"] = 0.0
    frame["weather_missing"] = 1
    frame["hour_sin"] = np.sin(2 * np.pi * timestamp.hour / 24)
    frame["hour_cos"] = np.cos(2 * np.pi * timestamp.hour / 24)
    frame["dow_sin"] = np.sin(2 * np.pi * timestamp.dayofweek / 7)
    frame["dow_cos"] = np.cos(2 * np.pi * timestamp.dayofweek / 7)
    for lag in LAGS:
        frame[f"lag_{lag}"] = [history[int(zone)][-lag] for zone in zones]
    for window in ROLLING_WINDOWS:
        frame[f"rolling_mean_{window}"] = [float(np.mean(history[int(zone)][-window:])) for zone in zones]
    return frame


def validate_forecast(frame: pd.DataFrame, zones: set[int], horizon: int, airport_ids: set[int]) -> dict:
    duplicate_rows = int(frame.duplicated(["pickup_zone_id", "forecast_hour"]).sum())
    expected_rows = len(zones) * horizon
    actual_pairs = set(zip(frame["pickup_zone_id"].astype(int), pd.to_datetime(frame["forecast_hour"])))
    hours = sorted(pd.to_datetime(frame["forecast_hour"]).unique())
    expected_pairs = {(zone, hour) for zone in zones for hour in hours}
    airport = frame[frame["pickup_zone_id"].isin(airport_ids)]
    event_window = (
        frame["is_event_window"].eq(1)
        if "is_event_window" in frame
        else frame["event_code"].ne(0)
    )
    checks = {
        "expected_row_count": len(frame) == expected_rows,
        "complete_zone_hour_grid": len(hours) == horizon and actual_pairs == expected_pairs,
        "unique_zone_hour": duplicate_rows == 0,
        "no_null_predictions": not frame["predicted_trip_count"].isna().any(),
        "no_negative_predictions": bool(frame["predicted_trip_count"].ge(0).all()),
        "airport_model_routing": not airport.empty and bool(airport["model_type"].eq("airport_specialist").all()),
        "event_model_routing": bool(frame.loc[(~frame["pickup_zone_id"].isin(airport_ids)) & event_window, "model_type"].eq("event_specialist").all()),
        "global_model_routing": bool(frame.loc[(~frame["pickup_zone_id"].isin(airport_ids)) & ~event_window, "model_type"].eq("global").all()),
    }
    return {"passed": all(checks.values()), "checks": checks, "expected_rows": expected_rows, "actual_rows": len(frame)}


def generate_forecast(
    hourly_path: Path,
    model_path: Path,
    *,
    horizon: int = 24,
    expected_model_sha256: str | None = None,
) -> tuple[pd.DataFrame, dict, datetime, int]:
    """Generate and validate a forecast without publishing or writing artifacts."""
    model_sha256 = sha256_file(model_path)
    if expected_model_sha256 is not None and model_sha256 != expected_model_sha256:
        raise PermissionError("Model artifact does not match the reviewed SHA-256")
    artifact = joblib.load(model_path)
    model_features = artifact.get("features", [])
    if not set(model_features).issubset(MODEL_FEATURES):
        raise ValueError("Model artifact requires features unavailable to inference code")
    hourly = load_hourly(hourly_path)
    last_hour = pd.Timestamp(hourly["pickup_hour"].max()).floor("h")
    zones = np.sort(hourly["pickup_zone_id"].dropna().astype(int).unique())
    recent_hours = pd.date_range(last_hour - timedelta(hours=167), last_hour, freq="h")
    recent = hourly[hourly["pickup_hour"].between(recent_hours.min(), recent_hours.max())]
    pivot = recent.pivot_table(index="pickup_hour", columns="pickup_zone_id", values="trip_count", aggfunc="sum").reindex(recent_hours).fillna(0)
    history = {int(zone): pivot[zone].tolist() if zone in pivot else [0.0] * 168 for zone in zones}
    airport_ids = set(map(int, artifact["airport_zone_ids"]))
    generated_at = datetime.now(timezone.utc)
    model_version = model_sha256[:16]
    rows = []
    for step in range(1, horizon + 1):
        forecast_hour = last_hour + timedelta(hours=step)
        features = _future_features(zones, forecast_hour, history, airport_ids)
        predictions = np.clip(artifact["global_model"].predict(features[model_features]), 0, None)
        airport_mask = features["pickup_zone_id"].isin(airport_ids).to_numpy()
        event_mask = (features["is_event_window"].eq(1) & ~features["pickup_zone_id"].isin(airport_ids)).to_numpy()
        if event_mask.any() and "event_model" in artifact:
            predictions[event_mask] = np.clip(artifact["event_model"].predict(features.loc[event_mask, model_features]), 0, None)
        if airport_mask.any():
            predictions[airport_mask] = np.clip(artifact["airport_model"].predict(features.loc[airport_mask, model_features]), 0, None)
        for zone, prediction, is_airport in zip(zones, predictions, airport_mask):
            history[int(zone)].append(float(prediction))
            rows.append({
                "forecast_generated_at": generated_at, "forecast_hour": forecast_hour,
                "pickup_zone_id": int(zone), "predicted_trip_count": float(prediction),
                "model_type": "airport_specialist" if is_airport else "event_specialist" if features.loc[features["pickup_zone_id"].eq(zone), "is_event_window"].iloc[0] and "event_model" in artifact else "global",
                "model_version": model_version,
                "event_code": int(features.loc[features["pickup_zone_id"].eq(zone), "event_code"].iloc[0]),
                "is_event_window": int(features.loc[features["pickup_zone_id"].eq(zone), "is_event_window"].iloc[0]),
            })
    if sha256_file(model_path) != model_sha256:
        raise OSError("Model artifact changed during forecast generation")
    frame = pd.DataFrame(rows)
    gate = validate_forecast(frame, set(map(int, zones)), horizon, airport_ids)
    return frame, gate, generated_at, len(zones)


def _write_parquet_atomic(frame: pd.DataFrame, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    connection = duckdb.connect()
    try:
        connection.register("forecast", frame)
        connection.execute(f"COPY forecast TO '{temporary.resolve().as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    finally:
        connection.close()
    temporary.replace(output)


def write_forecast_candidate(
    hourly_path: Path,
    model_path: Path,
    model_report_path: Path,
    output_dir: Path,
    *,
    horizon: int = 24,
    expected_model_sha256: str,
) -> dict:
    """Write a reviewed staging forecast candidate without publishing it."""
    frame, gate, generated_at, zone_count = generate_forecast(
        hourly_path,
        model_path,
        horizon=horizon,
        expected_model_sha256=expected_model_sha256,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    gate_output = output_dir / "gate.json"
    gate_temporary = gate_output.with_suffix(".json.part")
    gate_temporary.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    gate_temporary.replace(gate_output)
    if not gate["passed"]:
        raise RuntimeError("Forecast candidate gate failed")
    output = output_dir / "forecast.parquet"
    lineage_output = output_dir / "lineage.json"
    _write_parquet_atomic(frame, output)
    lineage = {
        "product": "hourly_zone_demand_forecast",
        "status": "candidate",
        "generated_at": generated_at.isoformat(),
        "forecast_start": str(frame["forecast_hour"].min()),
        "forecast_end": str(frame["forecast_hour"].max()),
        "horizon_hours": horizon,
        "zones": zone_count,
        "rows": len(frame),
        "source_gold": hourly_path.as_posix(),
        "source_gold_sha256": sha256_file(hourly_path),
        "source_model": model_path.as_posix(),
        "source_model_sha256": expected_model_sha256,
        "model_report": model_report_path.as_posix(),
        "model_report_sha256": sha256_file(model_report_path),
        "output": output.as_posix(),
        "output_sha256": sha256_file(output),
        "gate": gate,
    }
    lineage_temporary = lineage_output.with_suffix(".json.part")
    lineage_temporary.write_text(json.dumps(lineage, indent=2) + "\n", encoding="utf-8")
    lineage_temporary.replace(lineage_output)
    return lineage


def publish_forecast(
    hourly_path: Path,
    model_path: Path,
    output: Path,
    lineage_output: Path,
    gate_output: Path,
    *,
    horizon: int = 24,
    approval_file: Path,
) -> dict:
    approval = require_approval(
        approval_file, action="forecast_publication", artifact_sha256=sha256_file(model_path)
    )
    frame, gate, generated_at, zone_count = generate_forecast(
        hourly_path,
        model_path,
        horizon=horizon,
        expected_model_sha256=approval["artifact_sha256"],
    )
    gate_output.parent.mkdir(parents=True, exist_ok=True)
    gate_output.write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    if not gate["passed"]:
        raise RuntimeError("Forecast publication gate failed")
    archived = archive_current(output, lineage_output)
    _write_parquet_atomic(frame, output)
    lineage = {
        "product": "hourly_zone_demand_forecast", "generated_at": generated_at.isoformat(),
        "forecast_start": str(frame["forecast_hour"].min()), "forecast_end": str(frame["forecast_hour"].max()),
        "horizon_hours": horizon, "zones": zone_count, "rows": len(frame),
        "source_gold": hourly_path.as_posix(), "source_gold_sha256": sha256_file(hourly_path),
        "production_model": model_path.as_posix(), "production_model_sha256": sha256_file(model_path),
        "output": output.as_posix(), "output_sha256": sha256_file(output), "gate": gate,
        "previous_release_archive": archived.as_posix() if archived else None,
        "publication_approval": {
            "reviewer": approval["reviewer"],
            "approved_at": approval["approved_at"],
            "model_sha256": approval["artifact_sha256"],
        },
    }
    lineage_output.parent.mkdir(parents=True, exist_ok=True)
    lineage_output.write_text(json.dumps(lineage, indent=2) + "\n", encoding="utf-8")
    latest = {
        "forecast": output.as_posix(), "lineage": lineage_output.as_posix(),
        "generated_at": lineage["generated_at"], "forecast_start": lineage["forecast_start"],
        "model_sha256": lineage["production_model_sha256"], "output_sha256": lineage["output_sha256"],
    }
    latest_path = output.parent / "latest.json"
    latest_temporary = latest_path.with_suffix(".json.part")
    latest_temporary.write_text(json.dumps(latest, indent=2) + "\n", encoding="utf-8")
    latest_temporary.replace(latest_path)
    return lineage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish governed NYC demand forecasts")
    parser.add_argument("--input", type=Path, default=Path("data/processed/hourly_zone_demand.parquet"))
    parser.add_argument("--model", type=Path, default=Path("models/demand_release/production.joblib"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/forecasts/hourly_zone_demand_forecast.parquet"))
    parser.add_argument("--lineage", type=Path, default=Path("data/processed/lineage/hourly_zone_demand_forecast.json"))
    parser.add_argument("--gate-output", type=Path, default=Path("data/processed/quality/forecast-gate.json"))
    parser.add_argument("--horizon", type=int, default=24)
    parser.add_argument("--approval-file", type=Path, required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.horizon <= 168:
        raise SystemExit("horizon must be between 1 and 168 hours")
    print(json.dumps(publish_forecast(
        args.input, args.model, args.output, args.lineage, args.gate_output,
        horizon=args.horizon, approval_file=args.approval_file,
    ), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
