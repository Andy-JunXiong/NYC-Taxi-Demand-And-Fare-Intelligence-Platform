"""Governed recursive 24-hour demand inference and publication."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import duckdb
import joblib
import numpy as np
import pandas as pd

from .approvals import require_approval
from .download import sha256_file
from .forecast import LAGS, MODEL_FEATURES, ROLLING_WINDOWS, _us_holiday, load_hourly
from .events import event_features
from .releases import LATEST_SCHEMA_VERSION, load_latest_release


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


def _stage_parquet(frame: pd.DataFrame, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.unlink(missing_ok=True)
    connection = duckdb.connect()
    try:
        connection.register("forecast", frame)
        connection.execute(f"COPY forecast TO '{temporary.resolve().as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        connection.close()
    return temporary


def _write_parquet_atomic(frame: pd.DataFrame, output: Path) -> None:
    temporary = _stage_parquet(frame, output)
    try:
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def _stage_text(output: Path, content: str) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    temporary.unlink(missing_ok=True)
    try:
        temporary.write_text(content, encoding="utf-8")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def _previous_release_id(latest_path: Path) -> str | None:
    """Return the current release ID, allowing one migration from the legacy pointer."""
    if not latest_path.is_file():
        return None
    try:
        pointer = json.loads(latest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Existing forecast latest pointer is invalid: {latest_path}") from exc
    if not isinstance(pointer, dict):
        raise ValueError("Existing forecast latest pointer must be a JSON object")
    if pointer.get("schema_version") == LATEST_SCHEMA_VERSION:
        return str(load_latest_release(latest_path)["release_id"])
    legacy_fields = {"forecast", "lineage", "output_sha256"}
    if "schema_version" not in pointer and legacy_fields.issubset(pointer):
        return "legacy"
    raise ValueError("Existing forecast latest pointer has an unsupported schema")


def _remove_pending_release(path: Path) -> None:
    """Remove only the known files from one unpublished staging directory."""
    for name in (
        "forecast.parquet.part",
        "forecast.parquet",
        "lineage.json.part",
        "lineage.json",
        "gate.json.part",
        "gate.json",
    ):
        (path / name).unlink(missing_ok=True)
    try:
        path.rmdir()
    except OSError:
        pass


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
    """Publish a complete immutable release, then atomically switch its pointer.

    ``output`` and ``lineage_output`` locate the legacy publication boundary but
    are intentionally not replaced. The only canonical mutable file is
    ``output.parent / 'latest.json'``.
    """
    approval = require_approval(
        approval_file, action="forecast_publication", artifact_sha256=sha256_file(model_path)
    )
    frame, gate, generated_at, zone_count = generate_forecast(
        hourly_path,
        model_path,
        horizon=horizon,
        expected_model_sha256=approval["artifact_sha256"],
    )
    gate_temporary = _stage_text(gate_output, json.dumps(gate, indent=2) + "\n")
    try:
        gate_temporary.replace(gate_output)
    finally:
        gate_temporary.unlink(missing_ok=True)
    if not gate["passed"]:
        raise RuntimeError("Forecast publication gate failed")

    publication_root = output.parent
    latest_path = output.parent / "latest.json"
    previous_release_id = _previous_release_id(latest_path)
    releases_root = publication_root / "releases"
    releases_root.mkdir(parents=True, exist_ok=True)
    pending_release = releases_root / f".pending-{uuid4().hex}"
    pending_release.mkdir()
    bundle_visible = False
    latest_temporary: Path | None = None
    try:
        pending_forecast = pending_release / "forecast.parquet"
        forecast_temporary = _stage_parquet(frame, pending_forecast)
        forecast_temporary.replace(pending_forecast)
        output_sha256 = sha256_file(pending_forecast)
        release_id = (
            generated_at.strftime("%Y%m%dT%H%M%S%fZ")
            + f"-{output_sha256[:12]}"
        )
        final_release = releases_root / release_id
        if final_release.exists():
            raise FileExistsError(f"Forecast release already exists: {final_release}")
        final_forecast = final_release / "forecast.parquet"
        final_lineage = final_release / "lineage.json"
        final_gate = final_release / "gate.json"
        lineage = {
            "product": "hourly_zone_demand_forecast", "status": "published",
            "release_id": release_id, "generated_at": generated_at.isoformat(),
            "forecast_start": str(frame["forecast_hour"].min()), "forecast_end": str(frame["forecast_hour"].max()),
            "horizon_hours": horizon, "zones": zone_count, "rows": len(frame),
            "source_gold": hourly_path.as_posix(), "source_gold_sha256": sha256_file(hourly_path),
            "production_model": model_path.as_posix(), "production_model_sha256": sha256_file(model_path),
            "output": final_forecast.as_posix(), "output_sha256": output_sha256, "gate": gate,
            "release_path": final_release.as_posix(),
            "canonical_pointer": latest_path.as_posix(),
            "previous_release_id": previous_release_id,
            "legacy_output": output.as_posix(),
            "legacy_lineage": lineage_output.as_posix(),
            "publication_approval": {
                "reviewer": approval["reviewer"],
                "approved_at": approval["approved_at"],
                "model_sha256": approval["artifact_sha256"],
            },
        }
        lineage_temporary = _stage_text(
            pending_release / "lineage.json",
            json.dumps(lineage, indent=2) + "\n",
        )
        lineage_temporary.replace(pending_release / "lineage.json")
        gate_temporary = _stage_text(
            pending_release / "gate.json",
            json.dumps(gate, indent=2) + "\n",
        )
        gate_temporary.replace(pending_release / "gate.json")
        lineage_sha256 = sha256_file(pending_release / "lineage.json")
        gate_sha256 = sha256_file(pending_release / "gate.json")

        pending_release.rename(final_release)
        bundle_visible = True
        relative_release = final_release.relative_to(publication_root).as_posix()
        latest = {
            "schema_version": LATEST_SCHEMA_VERSION,
            "product": "hourly_zone_demand_forecast",
            "release_id": release_id,
            "release": relative_release,
            "forecast": f"{relative_release}/forecast.parquet",
            "lineage": f"{relative_release}/lineage.json",
            "gate": f"{relative_release}/gate.json",
            "generated_at": lineage["generated_at"], "forecast_start": lineage["forecast_start"],
            "model_sha256": lineage["production_model_sha256"], "output_sha256": output_sha256,
            "lineage_sha256": lineage_sha256, "gate_sha256": gate_sha256,
        }
        latest_temporary = _stage_text(
            latest_path,
            json.dumps(latest, indent=2) + "\n",
        )
        load_latest_release(latest_temporary)
        latest_temporary.replace(latest_path)
    finally:
        if latest_temporary is not None:
            latest_temporary.unlink(missing_ok=True)
        if not bundle_visible:
            _remove_pending_release(pending_release)
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
