"""Credential-safe Bronze capture for the TfNSW Taxi Rank APIs."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

try:  # Installed/src-on-PYTHONPATH execution
    from nyc_taxi.download import sha256_file, update_manifest
except ModuleNotFoundError:  # Repository: python -m src.sydney_taxi.capture
    from src.nyc_taxi.download import sha256_file, update_manifest


URL_ENV = {
    "static": "TFNSW_TAXI_RANK_STATIC_URL",
    "realtime": "TFNSW_TAXI_RANK_REALTIME_URL",
    "historical": "TFNSW_TAXI_RANK_HISTORICAL_URL_TEMPLATE",
}
DEFAULT_URLS = {
    "static": "https://api.transport.nsw.gov.au/v1/taxirank/info",
    "realtime": "https://api.transport.nsw.gov.au/v1/taxirank/realtime",
    "historical": (
        "https://api.transport.nsw.gov.au/v1/taxirank/history"
        "?rankId={rank_id}&date={date}"
    ),
}


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE settings without replacing existing environment values."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_url(kind: str, *, rank_id: str | None = None, day: str | None = None) -> str:
    template = os.environ.get(URL_ENV[kind], "") or DEFAULT_URLS[kind]
    if kind == "historical":
        if not rank_id or not day:
            raise ValueError("historical capture requires --rank-id and --date")
        date.fromisoformat(day)
        return template.format(rank_id=rank_id, date=day)
    return template


def auth_headers() -> dict[str, str]:
    key = os.environ.get("TFNSW_API_KEY", "")
    if not key:
        raise ValueError("Set TFNSW_API_KEY in the local environment")
    header = os.environ.get("TFNSW_AUTH_HEADER", "Authorization")
    scheme = os.environ.get("TFNSW_AUTH_SCHEME", "apikey")
    value = f"{scheme} {key}".strip() if scheme else key
    return {header: value, "Accept": "application/json", "User-Agent": "sydney-mobility/1.0"}


def capture_json(url: str, output: Path) -> dict[str, object]:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".part")
    with urlopen(Request(url, headers=auth_headers()), timeout=60) as response:
        payload = response.read()
    parsed = json.loads(payload.decode("utf-8-sig"))
    temporary.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return {
        "url": url,
        "path": output.as_posix(),
        "bytes": output.stat().st_size,
        "sha256": sha256_file(output),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "source": "TfNSW Taxi Rank API",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capture a TfNSW Taxi Rank API response")
    parser.add_argument("kind", choices=("static", "realtime", "historical"))
    parser.add_argument("--rank-id")
    parser.add_argument("--date")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path("data/raw/manifest.json"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)
    load_env_file(args.env_file)
    url = resolve_url(args.kind, rank_id=args.rank_id, day=args.date)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.output:
        output = args.output
    elif args.kind == "historical":
        output = Path("data/raw/sydney_taxi/historical") / f"date={args.date}" / f"{args.rank_id}.json"
    else:
        output = Path("data/raw/sydney_taxi") / args.kind / f"{stamp}.json"
    record = capture_json(url, output)
    update_manifest(args.manifest, record)
    print(f"Captured {args.kind} response to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
