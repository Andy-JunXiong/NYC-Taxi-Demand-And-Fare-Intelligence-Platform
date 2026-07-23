"""Score matured forecasts and report operational model drift."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from .forecast import AIRPORT_ZONE_IDS, metrics


def _segments(frame: pd.DataFrame, column: str, limit: int | None = None, min_actual: float = 0) -> list[dict]:
    rows = []
    for key, group in frame.groupby(column, sort=True):
        truth, prediction = group["trip_count"], group["predicted_trip_count"]
        if truth.sum() < min_actual:
            continue
        rows.append({
            "segment": str(key), "rows": len(group),
            "mae": float(np.abs(truth - prediction).mean()),
            "wape": float(np.abs(truth - prediction).sum() / max(truth.sum(), 1.0)),
            "bias": float((prediction - truth).sum() / max(truth.sum(), 1.0)),
        })
    return sorted(rows, key=lambda item: item["wape"], reverse=True)[:limit]


def score_frames(forecast: pd.DataFrame, actual: pd.DataFrame) -> dict:
    forecast = forecast.copy()
    actual = actual.copy()
    forecast["forecast_hour"] = pd.to_datetime(forecast["forecast_hour"])
    actual["pickup_hour"] = pd.to_datetime(actual["pickup_hour"])
    max_actual = actual["pickup_hour"].max()
    matured = forecast[forecast["forecast_hour"] <= max_actual]
    if matured.empty:
        return {"status": "waiting_for_actuals", "scored_rows": 0}
    actual_hourly = actual.groupby(["pickup_zone_id", "pickup_hour"], as_index=False)["trip_count"].sum()
    scored = matured.merge(
        actual_hourly,
        left_on=["pickup_zone_id", "forecast_hour"], right_on=["pickup_zone_id", "pickup_hour"], how="left",
    )
    scored["trip_count"] = scored["trip_count"].fillna(0.0)
    baseline = actual_hourly.rename(columns={"pickup_hour": "forecast_hour", "trip_count": "previous_week"}).copy()
    baseline["forecast_hour"] = baseline["forecast_hour"] + timedelta(days=7)
    scored = scored.merge(baseline, on=["pickup_zone_id", "forecast_hour"], how="left")
    scored["previous_week"] = scored["previous_week"].fillna(0.0)
    scored["hour"] = scored["forecast_hour"].dt.hour
    scored["month"] = scored["forecast_hour"].dt.to_period("M").astype(str)
    scored["market"] = np.where(scored["pickup_zone_id"].isin(AIRPORT_ZONE_IDS), "airport", "non_airport")
    threshold = float(scored["trip_count"].quantile(0.9))
    overall = metrics(scored["trip_count"], scored["predicted_trip_count"].to_numpy(), threshold)
    overall["bias"] = float((scored["predicted_trip_count"] - scored["trip_count"]).sum() / max(scored["trip_count"].sum(), 1.0))
    baseline_metrics = metrics(scored["trip_count"], scored["previous_week"].to_numpy(), threshold)
    overall["relative_wape_improvement_vs_previous_week"] = float(
        (baseline_metrics["wape"] - overall["wape"]) / baseline_metrics["wape"]
    )
    drift_checks = {
        "wape_below_25pct": overall["wape"] < 0.25,
        "absolute_bias_below_10pct": abs(overall["bias"]) < 0.10,
        "high_demand_recall_above_90pct": overall["high_demand_recall"] >= 0.90,
    }
    return {
        "status": "scored", "scored_rows": len(scored), "overall": overall,
        "previous_week_baseline": baseline_metrics,
        "drift": {"passed": all(drift_checks.values()), "checks": drift_checks},
        "by_month": _segments(scored, "month"), "by_hour": _segments(scored, "hour"),
        "by_market": _segments(scored, "market"), "worst_zones": _segments(scored, "pickup_zone_id", 15, min_actual=100),
    }


def monitor(forecast_path: Path, actual_path: Path, output: Path) -> dict:
    connection = duckdb.connect()
    forecast = connection.execute(f"SELECT * FROM read_parquet('{forecast_path.resolve().as_posix()}')").fetchdf()
    actual = connection.execute(f"SELECT pickup_zone_id, pickup_hour, trip_count FROM read_parquet('{actual_path.resolve().as_posix()}')").fetchdf()
    connection.close()
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), **score_frames(forecast, actual)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Monitor matured NYC demand forecasts")
    parser.add_argument("--forecast", type=Path, default=Path("data/processed/forecasts/hourly_zone_demand_forecast.parquet"))
    parser.add_argument("--actual", type=Path, default=Path("data/processed/hourly_zone_demand.parquet"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/monitoring/forecast-performance.json"))
    args = parser.parse_args(argv)
    report = monitor(args.forecast, args.actual, args.output)
    print(json.dumps(report, indent=2))
    return 2 if report.get("status") == "scored" and not report["drift"]["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
