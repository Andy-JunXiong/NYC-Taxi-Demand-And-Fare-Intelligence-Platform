"""Safe, resumable downloader for official monthly NYC TLC files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .datasets import parquet_url, raw_path


def parse_month(value: str) -> date:
    """Parse an inclusive YYYY-MM command-line month."""
    try:
        parsed = datetime.strptime(value, "%Y-%m").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("month must use YYYY-MM") from exc
    return parsed.replace(day=1)


def month_range(start: date, end: date) -> list[tuple[int, int]]:
    """Return inclusive (year, month) periods without loading calendar data."""
    if start > end:
        raise ValueError("start month must not be after end month")
    periods = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        periods.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return periods


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def check_source_availability(url: str, *, timeout: int = 30) -> dict[str, object]:
    """Check one official object without downloading its body or writing locally."""
    request = Request(
        url,
        headers={"User-Agent": "nyc-taxi-intelligence/1.0"},
        method="HEAD",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200) or 200)
            length = response.headers.get("Content-Length")
            return {
                "status": "available",
                "http_status": status,
                "content_length": int(length) if length and length.isdigit() else None,
            }
    except HTTPError as exc:
        if exc.code in {403, 404}:
            return {
                "status": "source_not_available",
                "http_status": int(exc.code),
                "content_length": None,
            }
        raise


def download_file(url: str, destination: Path, *, retries: int = 3) -> dict[str, object]:
    """Download atomically and return reproducibility metadata."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    for attempt in range(1, retries + 1):
        try:
            existing = temporary.stat().st_size if temporary.exists() else 0
            headers = {"User-Agent": "nyc-taxi-intelligence/1.0"}
            if existing:
                headers["Range"] = f"bytes={existing}-"
            request = Request(url, headers=headers)
            with urlopen(request, timeout=60) as response:
                append = existing > 0 and getattr(response, "status", None) == 206
                mode = "ab" if append else "wb"
                with temporary.open(mode) as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
            os.replace(temporary, destination)
            return {
                "url": url,
                "path": destination.as_posix(),
                "bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
                "downloaded_at": datetime.now(timezone.utc).isoformat(),
            }
        except (HTTPError, URLError, TimeoutError, OSError):
            if attempt == retries:
                raise
            time.sleep(attempt)
    raise RuntimeError("unreachable")


def update_manifest(path: Path, record: dict[str, object]) -> None:
    manifest = {"version": 1, "files": []}
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
    files = [item for item in manifest["files"] if item["path"] != record["path"]]
    files.append(record)
    manifest["files"] = sorted(files, key=lambda item: item["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download monthly official TLC Parquet data")
    parser.add_argument("--year", type=int)
    parser.add_argument("--months", type=int, nargs="+")
    parser.add_argument("--start", type=parse_month, help="inclusive month, YYYY-MM")
    parser.add_argument("--end", type=parse_month, help="inclusive month, YYYY-MM")
    parser.add_argument("--trip-type", choices=("yellow", "green"), default="yellow")
    parser.add_argument("--root", type=Path, default=Path("data/raw"))
    parser.add_argument("--manifest", type=Path, default=Path("data/raw/manifest.json"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--check-availability",
        action="store_true",
        help="verify official objects without downloading or writing files",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    legacy_mode = args.year is not None or args.months is not None
    range_mode = args.start is not None or args.end is not None
    if legacy_mode and range_mode:
        raise SystemExit("Use either --year/--months or --start/--end, not both")
    if legacy_mode:
        if args.year is None or not args.months:
            raise SystemExit("--year and --months must be supplied together")
        periods = [(args.year, month) for month in sorted(set(args.months))]
    elif range_mode:
        if args.start is None or args.end is None:
            raise SystemExit("--start and --end must be supplied together")
        try:
            periods = month_range(args.start, args.end)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    else:
        raise SystemExit("Supply --year/--months or --start/--end")
    if len(periods) > 12:
        raise SystemExit("At most 12 months may be requested at once")
    if args.dry_run and args.check_availability:
        raise SystemExit("--dry-run and --check-availability cannot be combined")

    targets = [
        {
            "period": f"{year}-{month:02d}",
            "destination": raw_path(args.root, year, month, args.trip_type),
            "url": parquet_url(year, month, args.trip_type),
        }
        for year, month in periods
    ]
    if args.dry_run:
        for target in targets:
            print(f"Would download {target['url']} -> {target['destination']}")
        return 0

    availability = []
    for target in targets:
        destination = target["destination"]
        if destination.exists() and not args.force and not args.check_availability:
            continue
        source = check_source_availability(target["url"])
        availability.append({
            "period": target["period"],
            "url": target["url"],
            **source,
        })
    unavailable = [
        source for source in availability if source["status"] != "available"
    ]
    if unavailable:
        print(json.dumps({
            "status": "blocked",
            "check": "tlc_source_availability",
            "writes_performed": False,
            "sources": availability,
        }, indent=2))
        return 2
    if args.check_availability:
        print(json.dumps({
            "status": "ready",
            "check": "tlc_source_availability",
            "writes_performed": False,
            "sources": availability,
        }, indent=2))
        return 0

    for target in targets:
        destination = target["destination"]
        url = target["url"]
        if destination.exists() and not args.force:
            print(f"Skipping existing file: {destination}")
        else:
            print(f"Downloading {url}")
            record = download_file(url, destination)
            update_manifest(args.manifest, record)
            print(f"Saved {record['bytes']:,} bytes to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
