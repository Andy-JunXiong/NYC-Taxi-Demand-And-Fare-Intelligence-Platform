"""Command-line entry point for the reproducible preprocessing pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from .cleaning import clean_trips
from .features import add_trip_features
from .io import load_and_merge


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a cleaned NYC taxi dataset")
    parser.add_argument("--trips", type=Path, default=Path("data/raw/trip_data_1.csv"))
    parser.add_argument("--fares", type=Path, default=Path("data/raw/trip_fare_1.csv"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/trips_cleaned.csv")
    )
    parser.add_argument("--nrows", type=int, help="Read only N rows for a quick smoke test")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.nrows is not None and args.nrows <= 0:
        raise SystemExit("--nrows must be a positive integer")
    merged = load_and_merge(args.trips, args.fares, nrows=args.nrows)
    cleaned = add_trip_features(clean_trips(merged))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(args.output, index=False)
    print(f"Wrote {len(cleaned):,} cleaned trips to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
