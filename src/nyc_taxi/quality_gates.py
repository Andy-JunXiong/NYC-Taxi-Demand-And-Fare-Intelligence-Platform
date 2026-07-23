"""Release gates for governed Yellow Taxi partitions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_THRESHOLDS = {
    "reconciled": True,
    "pickup_outside_partition_rate_max": 0.0002,
    "unknown_pickup_zone_rate_max": 0.01,
    "candidate_duplicate_rate_max": 0.001,
    "negative_fare_rate_max": 0.03,
    "implausible_speed_rate_max": 0.005,
    "demand_eligible_rate_min": 0.95,
}


def evaluate_report(report: dict, thresholds: dict | None = None, *, product: str = "demand") -> dict:
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    counts = report["counts"]
    total = max(int(counts["source_rows"]), 1)
    checks = []

    def check(name: str, value: float | bool, operator: str, limit: float | bool, *, blocking: bool = True) -> None:
        passed = value == limit if operator == "==" else value <= limit if operator == "<=" else value >= limit
        checks.append({"check": name, "value": value, "operator": operator, "limit": limit, "passed": bool(passed), "blocking": blocking})

    check("reconciled", bool(report.get("reconciled")), "==", limits["reconciled"])
    for field, threshold in (
        ("pickup_outside_partition", "pickup_outside_partition_rate_max"),
        ("unknown_pickup_zone", "unknown_pickup_zone_rate_max"),
        ("candidate_duplicate_rows", "candidate_duplicate_rate_max"),
        ("negative_fare", "negative_fare_rate_max"),
        ("implausible_speed", "implausible_speed_rate_max"),
    ):
        check(field + "_rate", int(counts[field]) / total, "<=", limits[threshold], blocking=(field != "negative_fare" or product == "fare"))
    check("demand_eligible_rate", int(counts["demand_eligible"]) / total, ">=", limits["demand_eligible_rate_min"])
    return {
        "period": report.get("period"), "product": product,
        "passed": all(item["passed"] or not item["blocking"] for item in checks),
        "warnings": [item["check"] for item in checks if not item["passed"] and not item["blocking"]],
        "checks": checks,
    }


def run_gates(quality_root: Path, periods: list[str], output: Path, thresholds: dict | None = None, *, product: str = "demand") -> dict:
    expected = [quality_root / f"yellow_{period}.json" for period in periods]
    missing = [path.as_posix() for path in expected if not path.is_file()]
    results = [evaluate_report(json.loads(path.read_text(encoding="utf-8")), thresholds, product=product) for path in expected if path.is_file()]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "periods": periods, "product": product,
        "complete": not missing,
        "missing_reports": missing,
        "passed": not missing and all(result["passed"] for result in results),
        "partitions": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate NYC Taxi release quality gates")
    parser.add_argument("--quality-root", type=Path, default=Path("data/processed/quality"))
    parser.add_argument("--periods", nargs="+", required=True, help="expected YYYY-MM periods")
    parser.add_argument("--output", type=Path, default=Path("data/processed/quality/gate-report.json"))
    parser.add_argument("--product", choices=("demand", "fare"), default="demand")
    args = parser.parse_args(argv)
    result = run_gates(args.quality_root, args.periods, args.output, product=args.product)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
