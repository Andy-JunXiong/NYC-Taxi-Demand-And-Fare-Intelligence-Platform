from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from nyc_taxi import evaluation_readiness, model_validation


PLAN_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "recursive-evaluation-plan-2026-08-24.v1.json"
)


def canonical_digest(value: dict) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_fixture(tmp_path: Path, *, omit_last_hour: bool = False) -> dict:
    model_path = tmp_path / "candidate.joblib"
    model_path.write_bytes(b"reviewed candidate")
    model_sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()

    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    plan["candidate_model_sha256"] = model_sha256
    plan["training_period_end"] = "2024-04-30"
    plan["blocks"][0] = {
        "id": "A",
        "start_date": "2024-05-27",
        "end_date": "2024-06-19",
    }
    plan_path = tmp_path / "evaluation-plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    plan_sha256 = canonical_digest(plan)
    origins = model_validation._recursive_origins(
        pd.Timestamp("2024-05-27"),
        pd.Timestamp("2024-06-19"),
        origin_hour_step=5,
    )
    required_start = min(origins) - pd.Timedelta(hours=168)
    required_end = max(origins) + pd.Timedelta(hours=23)
    hours = pd.date_range(required_start, required_end, freq="h")
    if omit_last_hour:
        hours = hours[:-1]
    frame = pd.DataFrame(
        {
            "pickup_zone_id": 1,
            "pickup_hour": hours,
            "trip_count": 1,
        }
    )
    gold_path = tmp_path / "hourly_zone_demand.parquet"
    connection = duckdb.connect()
    connection.register("gold_fixture", frame)
    connection.execute(
        f"COPY gold_fixture TO '{gold_path.as_posix()}' (FORMAT PARQUET)"
    )
    connection.close()

    source_path = tmp_path / "silver/yellow/year=2024/month=05/trips.parquet"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"verified Silver source")
    lineage_path = tmp_path / "lineage.json"
    lineage_path.write_text(
        json.dumps(
            {
                "product": "hourly_zone_demand",
                "sources": [
                    {
                        "path": str(source_path),
                        "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                    }
                ],
                "output": str(gold_path),
                "output_sha256": hashlib.sha256(gold_path.read_bytes()).hexdigest(),
                "rows": len(frame),
            }
        ),
        encoding="utf-8",
    )
    quality_gate_path = tmp_path / "gate-report.json"
    quality_gate_path.write_text(
        json.dumps(
            {
                "product": "demand",
                "periods": ["2024-05"],
                "complete": True,
                "missing_reports": [],
                "passed": True,
                "partitions": [{"period": "2024-05", "passed": True}],
            }
        ),
        encoding="utf-8",
    )
    return {
        "gold": gold_path,
        "lineage": lineage_path,
        "quality": quality_gate_path,
        "model": model_path,
        "model_sha256": model_sha256,
        "plan": plan_path,
        "plan_sha256": plan_sha256,
        "expected_hours": len(pd.date_range(required_start, required_end, freq="h")),
    }


def run_preflight(paths: dict) -> dict:
    return evaluation_readiness.recursive_evaluation_readiness(
        paths["gold"],
        paths["lineage"],
        paths["quality"],
        paths["model"],
        paths["plan"],
        expected_evaluation_plan_sha256=paths["plan_sha256"],
        evaluation_block="A",
        expected_model_sha256=paths["model_sha256"],
    )


def test_ready_preflight_verifies_inputs_without_loading_model_or_scoring(
    tmp_path: Path, monkeypatch
):
    paths = write_fixture(tmp_path)
    monkeypatch.setattr(
        model_validation.joblib,
        "load",
        lambda _path: (_ for _ in ()).throw(AssertionError("model must not load")),
    )

    report = run_preflight(paths)

    assert report["status"] == "ready"
    assert report["read_only"] is True
    assert report["model_deserialized"] is False
    assert report["outcomes_calculated"] is False
    assert all(report["checks"].values())
    assert report["coverage"]["expected_hours"] == paths["expected_hours"]
    assert report["coverage"]["missing_hour_count"] == 0
    assert report["promotion"] == {
        "status": "not_permitted",
        "reason": "readiness_preflight_only",
    }
    serialized = json.dumps(report)
    assert "candidate_wape" not in serialized
    assert "trip_count" not in serialized


def test_preflight_blocks_incomplete_required_hour_coverage(tmp_path: Path):
    paths = write_fixture(tmp_path, omit_last_hour=True)

    report = run_preflight(paths)

    assert report["status"] == "blocked"
    assert report["checks"]["required_hours_complete"] is False
    assert report["coverage"]["missing_hour_count"] == 1
    assert report["coverage"]["observed_hours"] == paths["expected_hours"] - 1


def test_model_mismatch_fails_before_gold_or_lineage_access(tmp_path: Path):
    paths = write_fixture(tmp_path)
    paths["model"].write_bytes(b"changed model")
    paths["gold"].unlink()
    paths["lineage"].unlink()

    with pytest.raises(PermissionError, match="Model SHA-256 mismatch"):
        run_preflight(paths)


def test_gold_digest_mismatch_fails_closed(tmp_path: Path):
    paths = write_fixture(tmp_path)
    lineage = json.loads(paths["lineage"].read_text(encoding="utf-8"))
    lineage["output_sha256"] = "0" * 64
    paths["lineage"].write_text(json.dumps(lineage), encoding="utf-8")

    with pytest.raises(PermissionError, match="Gold SHA-256"):
        run_preflight(paths)


def test_preflight_blocks_when_quality_gate_does_not_cover_lineage(tmp_path: Path):
    paths = write_fixture(tmp_path)
    gate = json.loads(paths["quality"].read_text(encoding="utf-8"))
    gate["partitions"][0]["passed"] = False
    paths["quality"].write_text(json.dumps(gate), encoding="utf-8")

    report = run_preflight(paths)

    assert report["status"] == "blocked"
    assert report["checks"]["quality_gate_covers_lineage"] is False
    assert report["quality_gate"]["missing_or_failed_periods"] == ["2024-05"]


def test_cli_returns_blocked_exit_code_without_writing_report(
    tmp_path: Path, monkeypatch, capsys
):
    captured = {}

    def fake_preflight(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"status": "blocked", "read_only": True}

    monkeypatch.setattr(
        evaluation_readiness, "recursive_evaluation_readiness", fake_preflight
    )
    output_path = tmp_path / "readiness.json"

    result = evaluation_readiness.main(
        [
            "--gold",
            str(tmp_path / "gold.parquet"),
            "--lineage",
            str(tmp_path / "lineage.json"),
            "--quality-gate",
            str(tmp_path / "gate.json"),
            "--model",
            str(tmp_path / "candidate.joblib"),
            "--evaluation-plan",
            str(tmp_path / "plan.json"),
            "--expected-evaluation-plan-sha256",
            "a" * 64,
            "--evaluation-block",
            "A",
            "--expected-model-sha256",
            "b" * 64,
        ]
    )

    assert result == 2
    assert json.loads(capsys.readouterr().out) == {
        "status": "blocked",
        "read_only": True,
    }
    assert not output_path.exists()
    assert captured["kwargs"]["evaluation_block"] == "A"
