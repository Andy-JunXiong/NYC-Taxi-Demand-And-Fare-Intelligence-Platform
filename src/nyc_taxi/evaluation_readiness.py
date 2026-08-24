"""Read-only readiness checks for bound recursive evaluation blocks."""

from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import duckdb
import pandas as pd

from .download import sha256_file
from .model_validation import (
    _load_evaluation_plan,
    _recursive_origins,
    _validate_sha256,
)


_GOLD_COLUMNS = {"pickup_zone_id", "pickup_hour", "trip_count"}


def _load_json_object(path: Path, label: str) -> dict:
    def reject_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate {label} key: {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label} JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _validate_gold_lineage(lineage_path: Path, gold_path: Path) -> tuple[dict, list[str]]:
    lineage = _load_json_object(lineage_path, "Gold lineage")
    required = {"product", "sources", "output_sha256", "rows"}
    missing = sorted(required - set(lineage))
    if missing:
        raise ValueError(f"Gold lineage is missing required fields: {missing}")
    if lineage["product"] != "hourly_zone_demand":
        raise ValueError("Gold lineage names the wrong product")
    _validate_sha256(lineage["output_sha256"], "Gold output_sha256")
    if lineage["output_sha256"] != sha256_file(gold_path):
        raise PermissionError("Gold SHA-256 does not match its lineage")
    if type(lineage["rows"]) is not int or lineage["rows"] < 0:
        raise ValueError("Gold lineage rows must be a non-negative integer")
    sources = lineage["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("Gold lineage must declare at least one Silver source")

    periods = []
    seen_paths = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict) or set(source) != {"path", "sha256"}:
            raise ValueError(f"Gold lineage source {index} has an invalid schema")
        source_path = source["path"]
        if not isinstance(source_path, str) or not source_path:
            raise ValueError(f"Gold lineage source {index} path is invalid")
        if source_path in seen_paths:
            raise ValueError(f"Gold lineage repeats source path: {source_path}")
        seen_paths.add(source_path)
        _validate_sha256(source["sha256"], f"Gold lineage source {index} sha256")
        path = Path(source_path)
        if not path.is_file():
            raise FileNotFoundError(f"Gold lineage source is missing: {path}")
        if sha256_file(path) != source["sha256"]:
            raise PermissionError(f"Silver SHA-256 does not match lineage: {path}")
        year = path.parent.parent.name.removeprefix("year=")
        month = path.parent.name.removeprefix("month=")
        period = f"{year}-{month}"
        if len(period) != 7 or not year.isdigit() or not month.isdigit():
            raise ValueError(f"Cannot derive a source period from lineage path: {path}")
        periods.append(period)
    if periods != sorted(periods) or len(periods) != len(set(periods)):
        raise ValueError("Gold lineage source periods must be unique and chronological")
    return lineage, periods


def _quality_gate_check(quality_gate_path: Path, source_periods: list[str]) -> dict:
    gate = _load_json_object(quality_gate_path, "quality gate")
    partitions = gate.get("partitions")
    if not isinstance(partitions, list):
        partitions = []
    partition_status = {
        row.get("period"): row.get("passed") is True
        for row in partitions
        if isinstance(row, dict) and isinstance(row.get("period"), str)
    }
    declared_periods = gate.get("periods")
    declared = set(declared_periods) if isinstance(declared_periods, list) else set()
    missing_periods = [
        period
        for period in source_periods
        if period not in declared or not partition_status.get(period, False)
    ]
    passed = (
        gate.get("product") == "demand"
        and gate.get("complete") is True
        and gate.get("passed") is True
        and gate.get("missing_reports") == []
        and not missing_periods
    )
    return {
        "passed": passed,
        "sha256": sha256_file(quality_gate_path),
        "missing_or_failed_periods": missing_periods,
    }


def _gold_coverage(gold_path: Path, origins: list[pd.Timestamp], lineage_rows: int) -> dict:
    required_start = min(origins) - timedelta(hours=168)
    required_end = max(origins) + timedelta(hours=23)
    expected = pd.date_range(required_start, required_end, freq="h")
    gold_sql = gold_path.resolve().as_posix().replace("'", "''")
    connection = duckdb.connect()
    try:
        description = connection.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{gold_sql}')"
        ).fetchall()
        columns = {row[0] for row in description}
        missing_columns = sorted(_GOLD_COLUMNS - columns)
        if missing_columns:
            return {
                "schema_complete": False,
                "missing_columns": missing_columns,
                "row_count_matches_lineage": False,
                "keys_valid": False,
                "required_hours_complete": False,
                "required_start": required_start.isoformat(),
                "required_end": required_end.isoformat(),
                "expected_hours": len(expected),
                "observed_hours": 0,
                "missing_hour_count": len(expected),
                "missing_hours_sample": [value.isoformat() for value in expected[:10]],
            }
        row = connection.execute(
            f"""
            SELECT
              count(*) AS rows,
              min(pickup_hour) AS first_hour,
              max(pickup_hour) AS last_hour,
              count(*) FILTER (
                WHERE pickup_zone_id IS NULL OR pickup_hour IS NULL OR trip_count IS NULL
              ) AS null_key_or_value_rows,
              count(*) FILTER (
                WHERE pickup_hour != date_trunc('hour', pickup_hour)
              ) AS non_hour_aligned_rows,
              count(*) - count(DISTINCT (pickup_zone_id, pickup_hour)) AS duplicate_keys
            FROM read_parquet('{gold_sql}')
            """
        ).fetchone()
        observed_rows = connection.execute(
            f"""
            SELECT DISTINCT pickup_hour
            FROM read_parquet('{gold_sql}')
            WHERE pickup_hour BETWEEN ? AND ?
            ORDER BY pickup_hour
            """,
            [required_start.to_pydatetime(), required_end.to_pydatetime()],
        ).fetchall()
    finally:
        connection.close()

    observed = pd.DatetimeIndex([value[0] for value in observed_rows])
    missing = expected[~expected.isin(observed)]
    return {
        "schema_complete": True,
        "missing_columns": [],
        "row_count_matches_lineage": int(row[0]) == lineage_rows,
        "keys_valid": int(row[3]) == 0 and int(row[4]) == 0 and int(row[5]) == 0,
        "required_hours_complete": len(missing) == 0,
        "gold_first_hour": pd.Timestamp(row[1]).isoformat(),
        "gold_last_hour": pd.Timestamp(row[2]).isoformat(),
        "required_start": required_start.isoformat(),
        "required_end": required_end.isoformat(),
        "expected_hours": len(expected),
        "observed_hours": len(observed),
        "missing_hour_count": len(missing),
        "missing_hours_sample": [value.isoformat() for value in missing[:10]],
    }


def recursive_evaluation_readiness(
    gold_path: Path,
    lineage_path: Path,
    quality_gate_path: Path,
    model_path: Path,
    evaluation_plan_path: Path,
    *,
    expected_evaluation_plan_sha256: str,
    evaluation_block: str,
    expected_model_sha256: str,
) -> dict:
    """Authenticate inputs and inspect coverage without loading or evaluating a model."""
    _validate_sha256(expected_model_sha256, "expected_model_sha256")
    plan, plan_sha256 = _load_evaluation_plan(
        evaluation_plan_path, expected_evaluation_plan_sha256
    )
    blocks = {block["id"]: block for block in plan["blocks"]}
    if evaluation_block not in blocks:
        raise ValueError(f"Evaluation block is not present in plan: {evaluation_block}")
    if plan["candidate_model_sha256"] != expected_model_sha256:
        raise PermissionError(
            "Expected model SHA-256 does not match the evaluation plan candidate"
        )
    model_sha256 = sha256_file(model_path)
    if model_sha256 != expected_model_sha256:
        raise PermissionError("Model SHA-256 mismatch during readiness preflight")

    lineage, periods = _validate_gold_lineage(lineage_path, gold_path)
    quality = _quality_gate_check(quality_gate_path, periods)
    block = blocks[evaluation_block]
    start = pd.Timestamp(block["start_date"])
    end = pd.Timestamp(block["end_date"])
    origins = _recursive_origins(
        start, end, origin_hour_step=plan["origin_hour_step"]
    )
    coverage = _gold_coverage(gold_path, origins, lineage["rows"])
    checks = {
        "plan_identity_verified": True,
        "model_identity_verified": True,
        "gold_lineage_verified": True,
        "quality_gate_covers_lineage": quality["passed"],
        "gold_schema_complete": coverage["schema_complete"],
        "gold_row_count_matches_lineage": coverage["row_count_matches_lineage"],
        "gold_keys_valid": coverage["keys_valid"],
        "required_hours_complete": coverage["required_hours_complete"],
    }
    ready = all(checks.values())
    return {
        "status": "ready" if ready else "blocked",
        "read_only": True,
        "model_deserialized": False,
        "outcomes_calculated": False,
        "plan_id": plan["plan_id"],
        "block_id": evaluation_block,
        "evaluation_plan_sha256": plan_sha256,
        "candidate_model_sha256": model_sha256,
        "gold_sha256": lineage["output_sha256"],
        "quality_gate_sha256": quality["sha256"],
        "source_period": {
            "first": periods[0],
            "last": periods[-1],
            "count": len(periods),
        },
        "origin_schedule": {
            "hour_step": plan["origin_hour_step"],
            "origins": [origin.isoformat() for origin in origins],
        },
        "checks": checks,
        "quality_gate": quality,
        "coverage": coverage,
        "promotion": {"status": "not_permitted", "reason": "readiness_preflight_only"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check recursive evaluation readiness without loading the model"
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=Path("data/processed/hourly_zone_demand.parquet"),
    )
    parser.add_argument(
        "--lineage",
        type=Path,
        default=Path("data/processed/lineage/hourly_zone_demand.json"),
    )
    parser.add_argument(
        "--quality-gate",
        type=Path,
        default=Path("data/processed/quality/gate-report.json"),
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--evaluation-plan", type=Path, required=True)
    parser.add_argument("--expected-evaluation-plan-sha256", required=True)
    parser.add_argument("--evaluation-block", required=True)
    parser.add_argument("--expected-model-sha256", required=True)
    args = parser.parse_args(argv)
    report = recursive_evaluation_readiness(
        args.gold,
        args.lineage,
        args.quality_gate,
        args.model,
        args.evaluation_plan,
        expected_evaluation_plan_sha256=args.expected_evaluation_plan_sha256,
        evaluation_block=args.evaluation_block,
        expected_model_sha256=args.expected_model_sha256,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
