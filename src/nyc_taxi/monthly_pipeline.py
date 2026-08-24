"""Idempotent monthly NYC Taxi ingestion and governed release orchestration."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from .download import main as download_main, month_range, parse_month
from .governance import build_all_silver, build_gold_demand
from .quality_gates import run_gates


class SourceUnavailableError(RuntimeError):
    """Raised before governance writes when an official monthly source is absent."""


def run_monthly(start, end, *, force: bool = False, skip_download: bool = False) -> dict:
    periods = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        periods.append(f"{year}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if not skip_download:
        download_status = download_main(
            ["--start", periods[0], "--end", periods[-1], *( ["--force"] if force else [] )]
        )
        if download_status == 2:
            raise SourceUnavailableError(
                "Official TLC source is not available; monthly governance stopped before writes"
            )
        if download_status != 0:
            raise RuntimeError(f"TLC download failed with status {download_status}")
    start_dt, end_dt = datetime(start.year, start.month, 1), datetime(end.year, end.month, 1)
    reports = build_all_silver(
        Path("data/raw"), Path("data/interim/silver"), Path("data/processed/quality"),
        Path("data/raw/reference/taxi_zone_lookup.csv"), force=force, start=start_dt, end=end_dt,
    )
    lineage_path = Path("data/processed/lineage/hourly_zone_demand.json")
    release_start = start
    release_end = end
    if lineage_path.is_file():
        previous = json.loads(lineage_path.read_text(encoding="utf-8"))
        prior_periods = []
        for source in previous.get("sources", []):
            match = re.search(r"year=(\d{4})[/\\]month=(\d{2})", source["path"])
            if match:
                prior_periods.append(parse_month(f"{match.group(1)}-{match.group(2)}"))
        if prior_periods:
            release_start = min(start, min(prior_periods))
            release_end = max(end, max(prior_periods))
    release_periods = [f"{year}-{month:02d}" for year, month in month_range(release_start, release_end)]
    gates = run_gates(Path("data/processed/quality"), release_periods, Path("data/processed/quality/gate-report.json"))
    if not gates["passed"]:
        raise RuntimeError("Quality gate failed; Gold release was not updated")
    lineage = build_gold_demand(
        Path("data/interim/silver"), Path("data/processed/hourly_zone_demand.parquet"),
        Path("data/processed/lineage/hourly_zone_demand.json"),
        start=datetime(release_start.year, release_start.month, 1),
        end=datetime(release_end.year, release_end.month, 1),
    )
    return {
        "processed_periods": periods, "release_periods": release_periods,
        "silver_partitions": len(reports), "quality_passed": True, "gold_rows": lineage["rows"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run incremental governed NYC Taxi pipeline")
    parser.add_argument("--start", type=parse_month, required=True)
    parser.add_argument("--end", type=parse_month, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args(argv)
    if args.start > args.end:
        raise SystemExit("start month must not be after end month")
    try:
        result = run_monthly(
            args.start, args.end, force=args.force, skip_download=args.skip_download
        )
    except SourceUnavailableError:
        # download_main already emitted the structured source report.
        return 2
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
