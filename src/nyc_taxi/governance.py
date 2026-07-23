"""Contract-first Bronze-to-Silver-to-Gold processing for modern TLC data."""

from __future__ import annotations

import argparse
import calendar
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .download import sha256_file
from .download import parse_month


CONTRACT_PATH = Path("contracts/yellow_taxi_modern.v1.json")


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(source: Path, contract: dict[str, object]) -> dict[str, str]:
    connection = duckdb.connect()
    rows = connection.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{source.resolve().as_posix()}')"
    ).fetchall()
    connection.close()
    actual = {row[0]: row[1].upper() for row in rows}
    errors = []
    for column, allowed in contract["required_columns"].items():
        if column not in actual:
            errors.append(f"missing {column}")
            continue
        if not any(actual[column].startswith(prefix) for prefix in allowed):
            errors.append(f"{column} has {actual[column]}, expected one of {allowed}")
    if errors:
        raise ValueError("Schema contract failed: " + "; ".join(errors))
    return actual


def _period(source: Path) -> tuple[int, int, str, str]:
    match = re.search(r"_(\d{4})-(\d{2})\.parquet$", source.name)
    if not match:
        raise ValueError(f"Cannot infer source period from {source.name}")
    year, month = map(int, match.groups())
    start = f"{year}-{month:02d}-01 00:00:00"
    last = calendar.monthrange(year, month)[1]
    end = f"{year}-{month:02d}-{last:02d} 23:59:59.999999"
    return year, month, start, end


def _git_state() -> dict[str, object]:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], text=True, stderr=subprocess.DEVNULL
            ).strip()
        )
        return {"git_commit": commit, "working_tree_dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"git_commit": None, "working_tree_dirty": None}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def build_silver_partition(
    source: Path,
    zone_lookup: Path,
    output: Path,
    quality_output: Path,
    *,
    contract_path: Path = CONTRACT_PATH,
) -> dict[str, object]:
    """Validate and enrich one month without deleting source rows."""
    contract = load_contract(contract_path)
    schema = validate_schema(source, contract)
    if not zone_lookup.is_file():
        raise FileNotFoundError(f"Official zone lookup is required: {zone_lookup}")
    year, month, start, end = _period(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(output.suffix + ".part")
    temporary_output.unlink(missing_ok=True)
    source_sql = source.resolve().as_posix().replace("'", "''")
    zone_sql = zone_lookup.resolve().as_posix().replace("'", "''")
    output_sql = temporary_output.resolve().as_posix().replace("'", "''")
    query = f"""
    COPY (
      WITH joined AS (
        SELECT
          s.*,
          date_diff('second', s.tpep_pickup_datetime, s.tpep_dropoff_datetime)
            AS derived_duration_seconds,
          pu.Borough AS pickup_borough,
          pu.Zone AS pickup_zone,
          pu.service_zone AS pickup_service_zone,
          dz.Borough AS dropoff_borough,
          dz.Zone AS dropoff_zone,
          dz.service_zone AS dropoff_service_zone,
          pu.LocationID IS NULL AS dq_unknown_pickup_zone,
          dz.LocationID IS NULL AS dq_unknown_dropoff_zone,
          s.tpep_pickup_datetime IS NULL AS dq_missing_pickup_datetime,
          s.tpep_dropoff_datetime IS NULL AS dq_missing_dropoff_datetime,
          s.tpep_pickup_datetime < TIMESTAMP '{start}'
            OR s.tpep_pickup_datetime > TIMESTAMP '{end}' AS dq_pickup_outside_partition,
          date_diff('second', s.tpep_pickup_datetime, s.tpep_dropoff_datetime) <= 0
            AS dq_nonpositive_duration,
          s.trip_distance < 0 AS dq_negative_distance,
          s.fare_amount < 0 AS dq_negative_fare,
          s.total_amount < 0 AS dq_negative_total,
          CASE
            WHEN date_diff('second', s.tpep_pickup_datetime, s.tpep_dropoff_datetime) > 0
            THEN s.trip_distance /
              (date_diff('second', s.tpep_pickup_datetime, s.tpep_dropoff_datetime) / 3600.0)
            ELSE NULL
          END AS derived_speed_mph,
          count(*) OVER (
            PARTITION BY s.VendorID, s.tpep_pickup_datetime, s.tpep_dropoff_datetime,
              s.PULocationID, s.DOLocationID, s.trip_distance,
              s.fare_amount, s.total_amount
          ) > 1 AS dq_candidate_duplicate
        FROM read_parquet('{source_sql}') s
        LEFT JOIN read_csv_auto('{zone_sql}', header=true) pu
          ON s.PULocationID = pu.LocationID
        LEFT JOIN read_csv_auto('{zone_sql}', header=true) dz
          ON s.DOLocationID = dz.LocationID
      )
      SELECT *,
        derived_speed_mph > 100 AS dq_implausible_speed,
        NOT dq_missing_pickup_datetime
          AND NOT dq_pickup_outside_partition
          AND NOT dq_unknown_pickup_zone AS dq_valid_for_demand,
        NOT dq_missing_pickup_datetime
          AND NOT dq_pickup_outside_partition
          AND NOT dq_unknown_pickup_zone
          AND NOT dq_missing_dropoff_datetime
          AND NOT dq_nonpositive_duration
          AND NOT dq_negative_distance
          AND NOT dq_negative_fare
          AND NOT dq_negative_total AS dq_valid_for_fare
      FROM joined
    ) TO '{output_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """
    connection = duckdb.connect()
    connection.execute(query)
    counts = connection.execute(
        f"""
        SELECT
          count(*) AS source_rows,
          count(*) FILTER (WHERE dq_missing_pickup_datetime) AS missing_pickup_datetime,
          count(*) FILTER (WHERE dq_missing_dropoff_datetime) AS missing_dropoff_datetime,
          count(*) FILTER (WHERE dq_pickup_outside_partition) AS pickup_outside_partition,
          count(*) FILTER (WHERE dq_unknown_pickup_zone) AS unknown_pickup_zone,
          count(*) FILTER (WHERE dq_unknown_dropoff_zone) AS unknown_dropoff_zone,
          count(*) FILTER (WHERE dq_nonpositive_duration) AS nonpositive_duration,
          count(*) FILTER (WHERE dq_negative_distance) AS negative_distance,
          count(*) FILTER (WHERE dq_negative_fare) AS negative_fare,
          count(*) FILTER (WHERE dq_negative_total) AS negative_total,
          count(*) FILTER (WHERE dq_implausible_speed) AS implausible_speed,
          count(*) FILTER (WHERE dq_candidate_duplicate) AS candidate_duplicate_rows,
          count(*) FILTER (WHERE dq_valid_for_demand) AS demand_eligible,
          count(*) FILTER (WHERE dq_valid_for_fare) AS fare_eligible
        FROM read_parquet('{output_sql}')
        """
    ).fetchone()
    columns = [item[0] for item in connection.description]
    silver_rows = connection.execute(
        f"SELECT count(*) FROM read_parquet('{output_sql}')"
    ).fetchone()[0]
    connection.close()
    count_map = dict(zip(columns, map(int, counts)))
    if count_map["source_rows"] != silver_rows:
        raise RuntimeError("Bronze-to-Silver row reconciliation failed")
    temporary_output.replace(output)
    report = {
        "contract": contract["contract"],
        "contract_version": contract["version"],
        "period": f"{year}-{month:02d}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source.as_posix(),
        "source_sha256": sha256_file(source),
        "silver": output.as_posix(),
        "silver_sha256": sha256_file(output),
        "schema": schema,
        "counts": count_map,
        "reconciled": True,
        **_git_state(),
    }
    _write_json(quality_output, report)
    return report


def _within_window(path: Path, start: datetime | None, end: datetime | None) -> bool:
    match = re.search(r"year=(\d{4})[/\\]month=(\d{2})", path.as_posix())
    if match:
        year, month = map(int, match.groups())
    else:
        year, month, _, _ = _period(path)
    period = datetime(year, month, 1)
    return (start is None or period >= start) and (end is None or period <= end)


def discover_bronze(
    root: Path, start: datetime | None = None, end: datetime | None = None
) -> list[Path]:
    return [
        path
        for path in sorted((root / "yellow").glob("year=*/month=*/*.parquet"))
        if _within_window(path, start, end)
    ]


def discover_silver(
    root: Path, start: datetime | None = None, end: datetime | None = None
) -> list[Path]:
    return [
        path
        for path in sorted((root / "yellow").glob("year=*/month=*/*.parquet"))
        if _within_window(path, start, end)
    ]


def build_all_silver(
    bronze_root: Path,
    silver_root: Path,
    quality_root: Path,
    zone_lookup: Path,
    *,
    force: bool = False,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, object]]:
    reports = []
    sources = discover_bronze(bronze_root, start, end)
    if not sources:
        raise ValueError(f"No Bronze Parquet files found below {bronze_root}")
    for source in sources:
        year, month, _, _ = _period(source)
        output = silver_root / "yellow" / f"year={year}" / f"month={month:02d}" / "trips.parquet"
        quality = quality_root / f"yellow_{year}-{month:02d}.json"
        if output.exists() and quality.exists() and not force:
            reports.append(json.loads(quality.read_text(encoding="utf-8")))
            continue
        reports.append(build_silver_partition(source, zone_lookup, output, quality))
    return reports


def build_gold_demand(
    silver_root: Path,
    output: Path,
    lineage_output: Path,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, object]:
    sources = discover_silver(silver_root, start, end)
    if not sources:
        raise ValueError(f"No Silver Parquet files found below {silver_root}")
    files = "[" + ",".join(
        "'" + path.resolve().as_posix().replace("'", "''") + "'" for path in sources
    ) + "]"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(output.suffix + ".part")
    temporary_output.unlink(missing_ok=True)
    target = temporary_output.resolve().as_posix().replace("'", "''")
    connection = duckdb.connect()
    connection.execute(
        f"""
        COPY (
          SELECT
            CAST(PULocationID AS INTEGER) AS pickup_zone_id,
            pickup_borough,
            pickup_zone,
            date_trunc('hour', tpep_pickup_datetime) AS pickup_hour,
            count(*) AS trip_count
          FROM read_parquet({files}, union_by_name=true)
          WHERE dq_valid_for_demand
          GROUP BY 1, 2, 3, 4
          ORDER BY 4, 1
        ) TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    rows, trips = connection.execute(
        f"SELECT count(*), sum(trip_count) FROM read_parquet('{target}')"
    ).fetchone()
    connection.close()
    temporary_output.replace(output)
    lineage = {
        "product": "hourly_zone_demand",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {"path": path.as_posix(), "sha256": sha256_file(path)} for path in sources
        ],
        "output": output.as_posix(),
        "output_sha256": sha256_file(output),
        "rows": int(rows),
        "trips": int(trips),
        **_git_state(),
    }
    _write_json(lineage_output, lineage)
    return lineage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build governed Silver and Gold datasets")
    parser.add_argument("command", choices=("silver", "gold", "all"))
    parser.add_argument("--bronze-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--silver-root", type=Path, default=Path("data/interim/silver"))
    parser.add_argument("--quality-root", type=Path, default=Path("data/processed/quality"))
    parser.add_argument(
        "--zone-lookup", type=Path, default=Path("data/raw/reference/taxi_zone_lookup.csv")
    )
    parser.add_argument(
        "--gold-output", type=Path, default=Path("data/processed/hourly_zone_demand.parquet")
    )
    parser.add_argument(
        "--lineage-output", type=Path, default=Path("data/processed/lineage/hourly_zone_demand.json")
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--start", type=parse_month, help="inclusive month, YYYY-MM")
    parser.add_argument("--end", type=parse_month, help="inclusive month, YYYY-MM")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if (args.start is None) != (args.end is None):
        raise SystemExit("--start and --end must be supplied together")
    if args.start and args.start > args.end:
        raise SystemExit("start month must not be after end month")
    start = datetime(args.start.year, args.start.month, 1) if args.start else None
    end = datetime(args.end.year, args.end.month, 1) if args.end else None
    if args.command in ("silver", "all"):
        reports = build_all_silver(
            args.bronze_root,
            args.silver_root,
            args.quality_root,
            args.zone_lookup,
            force=args.force,
            start=start,
            end=end,
        )
        print(f"Validated {len(reports)} Silver partitions")
    if args.command in ("gold", "all"):
        lineage = build_gold_demand(
            args.silver_root,
            args.gold_output,
            args.lineage_output,
            start=start,
            end=end,
        )
        print(f"Built Gold demand table with {lineage['rows']:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
