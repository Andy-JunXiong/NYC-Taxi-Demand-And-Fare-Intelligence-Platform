"""Non-destructive Silver normalization for TfNSW Taxi Rank history."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

try:  # Installed/src-on-PYTHONPATH execution
    from nyc_taxi.download import sha256_file
except ModuleNotFoundError:  # Repository: python -m src.sydney_taxi.governance
    from src.nyc_taxi.download import sha256_file


CONTRACT_PATH = Path("contracts/sydney_taxi_rank.v1.json")
MISSING = {"", "N/A", "None", None}
PASSENGER_BANDS = {"Low": 0, "Medium": 1, "High": 2}
CLASSES = {"taxi", "passenger", "wat"}


def _missing(value):
    return None if value in MISSING else value


def _number(value):
    value = _missing(value)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_records(path: Path, root: str, required: set[str]) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    records = payload.get(root)
    if not isinstance(records, list):
        raise ValueError(f"{path} must contain a {root!r} array")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"{path} record {index} is not an object")
        missing = required.difference(record)
        if missing:
            raise ValueError(f"{path} record {index} missing {sorted(missing)}")
    return records


def normalize_history(paths: list[Path]) -> pd.DataFrame:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    spec = contract["feeds"]["historical"]
    rows = []
    for path in paths:
        for raw in _load_records(path, spec["root"], set(spec["required"])):
            trip_class = str(raw["class"]).lower()
            start = pd.to_datetime(_missing(raw["start_time"]), utc=True, errors="coerce")
            end = pd.to_datetime(_missing(raw["end_time"]), utc=True, errors="coerce")
            passenger = trip_class == "passenger"
            raw_previous = _missing(raw["from_previous_count"])
            raw_total = _missing(raw["total"])
            raw_arrivals = _missing(raw["new_arrivals"])
            interval_seconds = (end - start).total_seconds() if pd.notna(start) and pd.notna(end) else None
            rows.append(
                {
                    "rank_id": _missing(raw["rank_id"]),
                    "tsn": _missing(raw.get("tsn")),
                    "comments": _missing(raw.get("comments")),
                    "total_bays": _number(raw["total_bays"]),
                    "start_time_utc": start,
                    "end_time_utc": end,
                    "start_time_sydney": start.tz_convert("Australia/Sydney") if pd.notna(start) else pd.NaT,
                    "end_time_sydney": end.tz_convert("Australia/Sydney") if pd.notna(end) else pd.NaT,
                    "class": trip_class,
                    "from_previous_raw": raw_previous,
                    "total_raw": raw_total,
                    "new_arrivals_raw": raw_arrivals,
                    "from_previous_count": None if passenger else _number(raw_previous),
                    "total_count": None if passenger else _number(raw_total),
                    "new_arrivals_count": None if passenger else _number(raw_arrivals),
                    "from_previous_band": PASSENGER_BANDS.get(raw_previous) if passenger else None,
                    "total_band": PASSENGER_BANDS.get(raw_total) if passenger else None,
                    "new_arrivals_band": PASSENGER_BANDS.get(raw_arrivals) if passenger else None,
                    "average_wait_seconds": _number(raw["average_wait"]),
                    "source_file": path.as_posix(),
                    "dq_missing_rank_id": _missing(raw["rank_id"]) is None,
                    "dq_unknown_class": trip_class not in CLASSES,
                    "dq_invalid_timestamp": pd.isna(start) or pd.isna(end),
                    "dq_invalid_interval": interval_seconds != 900,
                    "dq_invalid_passenger_band": passenger and any(
                        value not in PASSENGER_BANDS for value in (raw_previous, raw_total, raw_arrivals)
                    ),
                    "dq_invalid_numeric_count": (not passenger) and any(
                        _number(value) is None for value in (raw_previous, raw_total, raw_arrivals)
                    ),
                    "dq_negative_wait": (_number(raw["average_wait"]) or 0) < 0,
                }
            )
    return pd.DataFrame(rows)


def build_history_silver(paths: list[Path], output: Path, report_path: Path) -> dict[str, object]:
    if not paths:
        raise ValueError("At least one historical Bronze JSON file is required")
    frame = normalize_history(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.register("history", frame)
    connection.execute(
        f"COPY history TO '{output.resolve().as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)"
    )
    silver_rows = connection.execute(
        f"SELECT count(*) FROM read_parquet('{output.resolve().as_posix()}')"
    ).fetchone()[0]
    connection.close()
    if silver_rows != len(frame):
        raise RuntimeError("Sydney Bronze-to-Silver row reconciliation failed")
    flags = [column for column in frame if column.startswith("dq_")]
    report = {
        "contract": "sydney_taxi_rank",
        "contract_version": 1,
        "feed": "historical",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_files": [
            {"path": path.as_posix(), "sha256": sha256_file(path)} for path in paths
        ],
        "bronze_rows": len(frame),
        "silver_rows": int(silver_rows),
        "class_counts": {str(key): int(value) for key, value in frame["class"].value_counts().items()},
        "quality_counts": {column: int(frame[column].fillna(False).sum()) for column in flags},
        "output": output.as_posix(),
        "output_sha256": sha256_file(output),
        "reconciled": True,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build governed Sydney Taxi Rank Silver data")
    parser.add_argument(
        "--input-root", type=Path, default=Path("data/raw/sydney_taxi/historical")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/interim/silver/sydney_taxi/history.parquet")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("data/processed/quality/sydney_taxi_history.json")
    )
    args = parser.parse_args(argv)
    paths = sorted(args.input_root.rglob("*.json"))
    report = build_history_silver(paths, args.output, args.report)
    print(f"Built Sydney Silver with {report['silver_rows']:,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
