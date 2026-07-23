"""Reproducible EDA over governed 2024 Yellow Taxi products."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .download import sha256_file


def _save_chart(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()


def _lineage_inputs(lineage_path: Path, gold: Path) -> tuple[list[Path], list[str]]:
    """Resolve and verify the exact Silver snapshot declared by Gold lineage."""
    lineage = json.loads(lineage_path.read_text(encoding="utf-8"))
    if lineage.get("output_sha256") != sha256_file(gold):
        raise ValueError(f"Gold checksum does not match lineage: {gold}")

    sources: list[Path] = []
    periods: list[str] = []
    for source in lineage.get("sources", []):
        path = Path(source["path"])
        if not path.is_file():
            raise FileNotFoundError(f"Lineage source is missing: {path}")
        if source.get("sha256") != sha256_file(path):
            raise ValueError(f"Silver checksum does not match lineage: {path}")
        sources.append(path)
        year = path.parent.parent.name.removeprefix("year=")
        month = path.parent.name.removeprefix("month=")
        periods.append(f"{year}-{month}")
    if not sources:
        raise ValueError(f"No Silver sources declared in {lineage_path}")
    return sources, periods


def run_eda(gold: Path, lineage: Path, quality_root: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    gold_sql = gold.resolve().as_posix()
    silver, periods = _lineage_inputs(lineage, gold)
    silver_sql = "[" + ",".join(f"'{p.resolve().as_posix()}'" for p in silver) + "]"

    monthly = con.execute(f"""
        SELECT date_trunc('month', pickup_hour) AS month, sum(trip_count) AS trips
        FROM read_parquet('{gold_sql}') GROUP BY 1 ORDER BY 1
    """).fetchdf()
    temporal = con.execute(f"""
        SELECT dayofweek(pickup_hour) AS day_of_week, hour(pickup_hour) AS hour,
               sum(trip_count) AS trips
        FROM read_parquet('{gold_sql}') GROUP BY 1,2 ORDER BY 1,2
    """).fetchdf()
    borough = con.execute(f"""
        SELECT pickup_borough AS borough, sum(trip_count) AS trips
        FROM read_parquet('{gold_sql}') GROUP BY 1 ORDER BY 2 DESC
    """).fetchdf()
    top_zones = con.execute(f"""
        SELECT pickup_zone_id, pickup_zone, pickup_borough, sum(trip_count) AS trips
        FROM read_parquet('{gold_sql}') GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 15
    """).fetchdf()
    distributions = con.execute(f"""
        SELECT
          count(*) AS fare_eligible_rows,
          avg(fare_amount) AS mean_fare,
          median(fare_amount) AS median_fare,
          approx_quantile(fare_amount, 0.95) AS p95_fare,
          avg(trip_distance) AS mean_distance,
          median(trip_distance) AS median_distance,
          avg(derived_duration_seconds) / 60 AS mean_duration_minutes,
          median(derived_duration_seconds) / 60 AS median_duration_minutes
        FROM read_parquet({silver_sql}, union_by_name=true)
        WHERE dq_valid_for_fare
    """).fetchdf().iloc[0].to_dict()
    payment = con.execute(f"""
        SELECT payment_type, count(*) AS trips
        FROM read_parquet({silver_sql}, union_by_name=true)
        WHERE dq_valid_for_fare GROUP BY 1 ORDER BY 2 DESC
    """).fetchdf()
    airport = con.execute(f"""
        SELECT CASE WHEN pickup_zone_id IN (132, 138) THEN 'Airport' ELSE 'Non-airport' END AS segment,
               sum(trip_count) AS trips
        FROM read_parquet('{gold_sql}') GROUP BY 1 ORDER BY 2 DESC
    """).fetchdf()
    day_type = con.execute(f"""
        SELECT CASE WHEN dayofweek(pickup_hour) IN (0, 6) THEN 'Weekend' ELSE 'Weekday' END AS day_type,
               sum(trip_count) AS trips,
               count(DISTINCT CAST(pickup_hour AS DATE)) AS calendar_days
        FROM read_parquet('{gold_sql}') GROUP BY 1 ORDER BY 1
    """).fetchdf()
    day_type["pickups_per_day"] = day_type["trips"] / day_type["calendar_days"]
    distance_fare = con.execute(f"""
        SELECT CASE
          WHEN trip_distance < 1 THEN '<1'
          WHEN trip_distance < 3 THEN '1-3'
          WHEN trip_distance < 10 THEN '3-10'
          ELSE '10+' END AS distance_miles,
          count(*) AS trips, median(fare_amount) AS median_fare,
          approx_quantile(fare_amount, 0.95) AS p95_fare
        FROM read_parquet({silver_sql}, union_by_name=true)
        WHERE dq_valid_for_fare GROUP BY 1
        ORDER BY CASE distance_miles WHEN '<1' THEN 1 WHEN '1-3' THEN 2 WHEN '3-10' THEN 3 ELSE 4 END
    """).fetchdf()
    con.close()

    report_paths = [quality_root / f"yellow_{period}.json" for period in periods]
    missing_reports = [path for path in report_paths if not path.is_file()]
    if missing_reports:
        raise FileNotFoundError(f"Missing quality reports: {missing_reports}")
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in report_paths]
    period_label = f"{periods[0]} to {periods[-1]}"
    quality_keys = [
        "pickup_outside_partition", "nonpositive_duration", "negative_fare",
        "negative_total", "implausible_speed", "candidate_duplicate_rows",
    ]
    quality = pd.DataFrame({
        "quality_flag": quality_keys,
        "rows": [sum(report["counts"][key] for report in reports) for key in quality_keys],
    })

    for name, frame in {
        "monthly-demand": monthly,
        "weekday-hour-demand": temporal,
        "borough-demand": borough,
        "top-zones": top_zones,
        "payment-types": payment,
        "quality-flags": quality,
        "airport-demand": airport,
        "weekday-weekend": day_type,
        "distance-fare": distance_fare,
    }.items():
        frame.to_csv(output / f"{name}.csv", index=False)

    plt.figure(figsize=(8, 4.5))
    plt.plot(pd.to_datetime(monthly["month"]), monthly["trips"] / 1e6, marker="o")
    plt.ylabel("Pickups (millions)")
    plt.xlabel("Month")
    plt.title(f"Governed Yellow Taxi demand, {period_label}")
    plt.grid(axis="y", alpha=.25)
    _save_chart(output / "monthly-demand.png")

    pivot = temporal.pivot(index="day_of_week", columns="hour", values="trips").fillna(0) / 1e3
    pivot = pivot.reindex(range(7))
    plt.figure(figsize=(11, 4.8))
    image = plt.imshow(pivot, aspect="auto", cmap="viridis")
    plt.colorbar(image, label="Pickups (thousands)")
    plt.yticks(range(7), ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
    plt.xticks(range(0, 24, 2))
    plt.xlabel("Pickup hour (local wall time)")
    plt.title("Demand by weekday and hour")
    _save_chart(output / "weekday-hour-demand.png")

    plt.figure(figsize=(8, 4.5))
    ordered = borough.sort_values("trips")
    plt.barh(ordered["borough"], ordered["trips"] / 1e6)
    plt.xlabel("Pickups (millions)")
    plt.title("Pickup demand by official Taxi Zone borough")
    _save_chart(output / "borough-demand.png")

    plt.figure(figsize=(8, 4.5))
    q = quality.sort_values("rows")
    plt.barh(q["quality_flag"].str.replace("_", " "), q["rows"])
    plt.xlabel("Flagged rows")
    plt.title("Non-destructive Silver quality flags")
    _save_chart(output / "quality-flags.png")

    plt.figure(figsize=(8, 4.5))
    plt.bar(distance_fare["distance_miles"], distance_fare["median_fare"])
    plt.xlabel("Trip distance band (miles)")
    plt.ylabel("Median fare ($)")
    plt.title("Governed fare by distance band")
    _save_chart(output / "distance-fare.png")

    summary = {
        "period": [periods[0], periods[-1]],
        "eligible_pickups": int(monthly["trips"].sum()),
        "peak_month": str(pd.to_datetime(monthly.loc[monthly["trips"].idxmax(), "month"]).date()),
        "top_borough": str(borough.iloc[0]["borough"]),
        "top_zone": str(top_zones.iloc[0]["pickup_zone"]),
        "airport_pickups": int(airport.loc[airport["segment"] == "Airport", "trips"].iloc[0]),
        "pickups_per_day": dict(zip(day_type["day_type"], day_type["pickups_per_day"].round(2))),
        "fare_distribution": {key: float(value) for key, value in distributions.items()},
        "quality_flags": dict(zip(quality["quality_flag"], quality["rows"].astype(int))),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run governed NYC Taxi EDA")
    parser.add_argument("--gold", type=Path, default=Path("data/processed/hourly_zone_demand.parquet"))
    parser.add_argument(
        "--lineage", type=Path,
        default=Path("data/processed/lineage/hourly_zone_demand.json"),
        help="Gold lineage manifest defining the exact Silver snapshot",
    )
    parser.add_argument("--quality-root", type=Path, default=Path("data/processed/quality"))
    parser.add_argument("--output", type=Path, default=Path("docs/assets/eda"))
    args = parser.parse_args(argv)
    print(json.dumps(run_eda(args.gold, args.lineage, args.quality_root, args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
