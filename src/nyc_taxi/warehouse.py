"""Out-of-core sample and demand-table creation with DuckDB."""

from __future__ import annotations

import argparse
import calendar
import re
from datetime import datetime
from pathlib import Path


def _duckdb():
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError("DuckDB is required; install requirements.txt") from error
    return duckdb


def _monthly_source_sql(paths: list[Path]) -> str:
    """Read each partition with a strict pickup-time boundary from its filename."""
    if not paths:
        raise ValueError("At least one Parquet input is required")
    selects = []
    for path in paths:
        match = re.search(r"_(\d{4})-(\d{2})\.parquet$", path.name)
        if not match:
            raise ValueError(f"Cannot infer year and month from {path.name}")
        year, month = map(int, match.groups())
        start = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59, 999999)
        quoted = path.resolve().as_posix().replace("'", "''")
        selects.append(
            "SELECT * FROM read_parquet('"
            + quoted
            + "') WHERE tpep_pickup_datetime >= TIMESTAMP '"
            + start.isoformat(sep=" ")
            + "' AND tpep_pickup_datetime <= TIMESTAMP '"
            + end.isoformat(sep=" ")
            + "'"
        )
    return "(" + " UNION ALL BY NAME ".join(selects) + ")"


def discover_parquet(root: Path, trip_type: str = "yellow") -> list[Path]:
    return sorted((root / trip_type).glob("year=*/month=*/*.parquet"))


def build_sample(inputs: list[Path], output: Path, rows: int = 10_000) -> int:
    """Create a deterministic, time-stratified sample without loading all rows."""
    if rows <= 0:
        raise ValueError("rows must be positive")
    output.parent.mkdir(parents=True, exist_ok=True)
    source = _monthly_source_sql(inputs)
    query = f"""
        COPY (
            WITH ranked AS (
                SELECT *,
                    row_number() OVER (
                        PARTITION BY date_trunc('day', tpep_pickup_datetime)
                        ORDER BY hash(tpep_pickup_datetime, PULocationID, DOLocationID)
                    ) AS sample_rank
                FROM {source}
                WHERE tpep_pickup_datetime IS NOT NULL
            )
            SELECT * EXCLUDE (sample_rank)
            FROM ranked
            ORDER BY sample_rank, hash(CAST(tpep_pickup_datetime AS DATE))
            LIMIT {int(rows)}
        ) TO '{output.resolve().as_posix().replace("'", "''")}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """
    connection = _duckdb().connect()
    connection.execute(query)
    count = connection.execute(
        f"SELECT count(*) FROM read_parquet('{output.resolve().as_posix()}')"
    ).fetchone()[0]
    connection.close()
    return count


def aggregate_hourly_demand(inputs: list[Path], output: Path) -> int:
    """Build the compact zone-by-hour demand table used for forecasting."""
    output.parent.mkdir(parents=True, exist_ok=True)
    source = _monthly_source_sql(inputs)
    target = output.resolve().as_posix().replace("'", "''")
    query = f"""
        COPY (
            SELECT
                CAST(PULocationID AS INTEGER) AS pickup_zone_id,
                date_trunc('hour', tpep_pickup_datetime) AS pickup_hour,
                count(*) AS trip_count,
                avg(CASE WHEN fare_amount >= 0 THEN fare_amount END) AS avg_fare,
                avg(CASE WHEN trip_distance >= 0 THEN trip_distance END) AS avg_distance,
                avg(date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime))
                    FILTER (WHERE tpep_dropoff_datetime >= tpep_pickup_datetime) AS avg_duration_seconds
            FROM {source}
            WHERE PULocationID BETWEEN 1 AND 265
              AND tpep_pickup_datetime IS NOT NULL
            GROUP BY 1, 2
            ORDER BY 2, 1
        ) TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)
    """
    connection = _duckdb().connect()
    connection.execute(query)
    count = connection.execute(f"SELECT count(*) FROM read_parquet('{target}')").fetchone()[0]
    connection.close()
    return count


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build compact datasets from TLC Parquet files")
    parser.add_argument("command", choices=("sample", "aggregate"))
    parser.add_argument("--root", type=Path, default=Path("data/raw"))
    parser.add_argument("--trip-type", choices=("yellow",), default="yellow")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--rows", type=int, default=10_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = discover_parquet(args.root, args.trip_type)
    if not inputs:
        raise SystemExit(f"No Parquet files found below {args.root / args.trip_type}")
    if args.command == "sample":
        output = args.output or Path("data/sample/yellow_taxi_sample.parquet")
        count = build_sample(inputs, output, args.rows)
    else:
        output = args.output or Path("data/processed/hourly_zone_demand.parquet")
        count = aggregate_hourly_demand(inputs, output)
    print(f"Wrote {count:,} rows to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
