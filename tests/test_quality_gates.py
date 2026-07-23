import json
from pathlib import Path

from nyc_taxi.quality_gates import evaluate_report, run_gates
from nyc_taxi.model_validation import release_decision


def report(negative_fare=1):
    return {"period": "2024-01", "reconciled": True, "counts": {
        "source_rows": 1000, "pickup_outside_partition": 0,
        "unknown_pickup_zone": 0, "candidate_duplicate_rows": 0,
        "negative_fare": negative_fare, "implausible_speed": 0,
        "demand_eligible": 999,
    }}


def test_quality_gate_blocks_threshold_breach():
    assert evaluate_report(report())["passed"]
    assert evaluate_report(report(negative_fare=100), product="demand")["passed"]
    assert not evaluate_report(report(negative_fare=100), product="fare")["passed"]


def test_quality_gate_requires_every_period(tmp_path: Path):
    root = tmp_path / "quality"
    root.mkdir()
    (root / "yellow_2024-01.json").write_text(json.dumps(report()), encoding="utf-8")
    result = run_gates(root, ["2024-01", "2024-02"], tmp_path / "gate.json")
    assert not result["passed"]
    assert not result["complete"]


def test_model_release_requires_consistent_monthly_wins():
    folds = [{
        "baseline": {"wape": 0.30}, "candidate": {"wape": 0.20},
        "airport_global_model": {"wape": 0.25}, "airport_specialist": {"wape": 0.20},
        "ordinary_baseline": {"wape": 0.30}, "ordinary_candidate": {"wape": 0.20},
        "event_previous_year": {"wape": 0.30}, "event_candidate": {"wape": 0.20},
        "new_year_previous_week": {"wape": 0.30},
        "new_year_candidate": {"wape": 0.20, "high_demand_recall": 0.90},
    } for _ in range(4)]
    assert release_decision(folds)["passed"]
    folds[0]["candidate"]["wape"] = 0.40
    assert not release_decision(folds)["passed"]
