"""Compare verified Agent Operator runs by semantic outcome."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from verify_run import SCENARIO_PATH, load_json, sandbox_path, verify_run


def semantic_signature(run_root: Path, scenario: dict) -> dict:
    paths = scenario["paths"]
    lineage = load_json(sandbox_path(run_root, paths["lineage"]))
    gate = load_json(sandbox_path(run_root, paths["gate"]))
    agent_result = load_json(sandbox_path(run_root, paths["agent_result"]))
    return {
        "product": lineage.get("product"),
        "status": lineage.get("status"),
        "horizon_hours": lineage.get("horizon_hours"),
        "zones": lineage.get("zones"),
        "rows": lineage.get("rows"),
        "forecast_start": lineage.get("forecast_start"),
        "forecast_end": lineage.get("forecast_end"),
        "source_gold_sha256": lineage.get("source_gold_sha256"),
        "source_model_sha256": lineage.get("source_model_sha256"),
        "model_report_sha256": lineage.get("model_report_sha256"),
        "gate_passed": gate.get("passed"),
        "gate_checks": gate.get("checks"),
        "expected_rows": gate.get("expected_rows"),
        "actual_rows": gate.get("actual_rows"),
        "final_state": agent_result.get("final_state"),
        "publication_attempted": agent_result.get("publication_attempted"),
        "approval_created": agent_result.get("approval_created"),
    }


def compare_runs(
    run_a: Path,
    baseline_a: Path,
    run_b: Path,
    baseline_b: Path,
    scenario_path: Path = SCENARIO_PATH,
) -> dict:
    scenario = load_json(scenario_path)
    errors = [f"run-a: {error}" for error in verify_run(run_a, baseline_a, scenario_path)]
    errors.extend(f"run-b: {error}" for error in verify_run(run_b, baseline_b, scenario_path))
    signature_a = semantic_signature(run_a, scenario) if not any(error.startswith("run-a:") for error in errors) else {}
    signature_b = semantic_signature(run_b, scenario) if not any(error.startswith("run-b:") for error in errors) else {}
    if signature_a and signature_b:
        for field in signature_a:
            if signature_a[field] != signature_b[field]:
                errors.append(
                    f"semantic mismatch for {field}: {signature_a[field]!r} != {signature_b[field]!r}"
                )

    lineage_a = load_json(sandbox_path(run_a, scenario["paths"]["lineage"])) if signature_a else {}
    lineage_b = load_json(sandbox_path(run_b, scenario["paths"]["lineage"])) if signature_b else {}
    return {
        "status": "passed" if not errors else "failed",
        "errors": errors,
        "semantic_signature": signature_a if not errors else None,
        "run_output_sha256": {
            "run_a": lineage_a.get("output_sha256"),
            "run_b": lineage_b.get("output_sha256"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-a", type=Path, required=True)
    parser.add_argument("--baseline-a", type=Path, required=True)
    parser.add_argument("--run-b", type=Path, required=True)
    parser.add_argument("--baseline-b", type=Path, required=True)
    parser.add_argument("--scenario", type=Path, default=SCENARIO_PATH)
    args = parser.parse_args()
    try:
        result = compare_runs(
            args.run_a,
            args.baseline_a,
            args.run_b,
            args.baseline_b,
            args.scenario,
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        result = {"status": "failed", "errors": [f"invalid comparison input: {exc}"]}
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
