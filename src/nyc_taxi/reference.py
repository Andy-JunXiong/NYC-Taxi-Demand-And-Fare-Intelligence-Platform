"""Download and validate governed reference dimensions."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .download import download_file, update_manifest


ZONE_LOOKUP_URL = "https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv"


def validate_zone_lookup(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    required = {"LocationID", "Borough", "Zone", "service_zone"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Zone lookup is missing: {', '.join(sorted(missing))}")
    if frame["LocationID"].isna().any() or frame["LocationID"].duplicated().any():
        raise ValueError("LocationID must be non-null and unique")
    return frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download governed TLC reference data")
    parser.add_argument(
        "--output", type=Path, default=Path("data/raw/reference/taxi_zone_lookup.csv")
    )
    parser.add_argument("--manifest", type=Path, default=Path("data/raw/manifest.json"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.output.exists() and not args.force:
        validate_zone_lookup(args.output)
        print(f"Validated existing zone lookup: {args.output}")
        return 0
    record = download_file(ZONE_LOOKUP_URL, args.output)
    validate_zone_lookup(args.output)
    update_manifest(args.manifest, record)
    print(f"Downloaded and validated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
