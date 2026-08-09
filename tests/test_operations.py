import json
import sqlite3
from hashlib import sha256
from pathlib import Path

import pytest

import nyc_taxi.operations as operations
from nyc_taxi.operations import record_run


def write_report(path: Path, candidate_sha256: str, *, gate_passed: bool = True) -> None:
    path.write_text(
        json.dumps(
            {
                "release_gate": {"passed": gate_passed},
                "promotion": {
                    "status": "awaiting_human_approval",
                    "candidate_sha256": candidate_sha256,
                },
            }
        ),
        encoding="utf-8",
    )


def write_approval(path: Path, candidate_sha256: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "action": "model_promotion",
                "approved": True,
                "reviewer": "NYC Taxi maintainer",
                "approved_at": "2026-08-09T12:00:00+10:00",
                "artifact_sha256": candidate_sha256,
            }
        ),
        encoding="utf-8",
    )


def configure_model_paths(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    production = tmp_path / "release" / "production.joblib"
    archive_root = tmp_path / "release" / "archive"
    monkeypatch.setattr(operations, "PRODUCTION_MODEL_PATH", production)
    monkeypatch.setattr(operations, "MODEL_ARCHIVE_ROOT", archive_root)
    return production, archive_root


def test_run_ledger_records_success_and_failure(tmp_path: Path):
    ledger = tmp_path / "runs.sqlite"
    with record_run("sample", ledger=ledger) as state:
        state["gate_status"] = "passed"
        state["result"] = {"rows": 10}
    with pytest.raises(RuntimeError):
        with record_run("broken", ledger=ledger):
            raise RuntimeError("boom")
    connection = sqlite3.connect(ledger)
    rows = connection.execute(
        "SELECT pipeline,status,gate_status,error_message FROM pipeline_runs ORDER BY started_at"
    ).fetchall()
    connection.close()
    assert rows[0][:3] == ("sample", "completed", "passed")
    assert rows[1][0:2] == ("broken", "failed")
    assert "boom" in rows[1][3]


def test_promote_existing_candidate_archives_previous_model_and_records_ledger(tmp_path: Path, monkeypatch):
    production, archive_root = configure_model_paths(tmp_path, monkeypatch)
    production.parent.mkdir(parents=True)
    previous_bytes = b"previous production"
    candidate_bytes = b"reviewed candidate"
    production.write_bytes(previous_bytes)
    candidate = tmp_path / "candidate.joblib"
    report = tmp_path / "rolling_backtest.json"
    approval = tmp_path / "approval.json"
    ledger = tmp_path / "runs.sqlite"
    candidate.write_bytes(candidate_bytes)
    candidate_sha256 = sha256(candidate_bytes).hexdigest()
    previous_sha256 = sha256(previous_bytes).hexdigest()
    write_report(report, candidate_sha256)
    write_approval(approval, candidate_sha256)

    exit_code = operations.main(
        [
            "--ledger", str(ledger), "promote",
            "--candidate", str(candidate),
            "--report", str(report),
            "--approval-file", str(approval),
        ]
    )

    archive = archive_root / f"{previous_sha256}.joblib"
    assert exit_code == 0
    assert production.read_bytes() == candidate_bytes
    assert archive.read_bytes() == previous_bytes
    assert not list(archive_root.rglob("*.part"))
    connection = sqlite3.connect(ledger)
    row = connection.execute(
        "SELECT pipeline,status,gate_status,model_checksum,result_json FROM pipeline_runs"
    ).fetchone()
    connection.close()
    result = json.loads(row[4])
    assert row[:4] == ("promote", "completed", "passed", candidate_sha256)
    assert result["previous_model_sha256"] == previous_sha256
    assert result["production_model_sha256"] == candidate_sha256
    assert result["archive_path"] == archive.as_posix()


@pytest.mark.parametrize(
    ("gate_passed", "reported_sha256", "approved_sha256", "message"),
    [
        (False, None, None, "passing release gate"),
        (True, "0" * 64, None, "does not match the candidate"),
        (True, None, "0" * 64, "target artifact"),
    ],
)
def test_blocked_promotion_preserves_production_and_records_failure(
    tmp_path: Path,
    monkeypatch,
    gate_passed: bool,
    reported_sha256: str | None,
    approved_sha256: str | None,
    message: str,
):
    production, archive_root = configure_model_paths(tmp_path, monkeypatch)
    production.parent.mkdir(parents=True)
    production.write_bytes(b"current production")
    candidate = tmp_path / "candidate.joblib"
    report = tmp_path / "rolling_backtest.json"
    approval = tmp_path / "approval.json"
    ledger = tmp_path / "runs.sqlite"
    candidate.write_bytes(b"candidate")
    candidate_sha256 = sha256(b"candidate").hexdigest()
    write_report(report, reported_sha256 or candidate_sha256, gate_passed=gate_passed)
    write_approval(approval, approved_sha256 or candidate_sha256)

    with pytest.raises(PermissionError, match=message):
        operations.main(
            [
                "--ledger", str(ledger), "promote",
                "--candidate", str(candidate),
                "--report", str(report),
                "--approval-file", str(approval),
            ]
        )

    assert production.read_bytes() == b"current production"
    assert not archive_root.exists()
    connection = sqlite3.connect(ledger)
    row = connection.execute(
        "SELECT pipeline,status,error_message FROM pipeline_runs"
    ).fetchone()
    connection.close()
    assert row[0:2] == ("promote", "failed")
    assert message in row[2]


def test_interrupted_archive_preserves_production_and_removes_partial(tmp_path: Path, monkeypatch):
    production, archive_root = configure_model_paths(tmp_path, monkeypatch)
    production.parent.mkdir(parents=True)
    production.write_bytes(b"current production")
    candidate = tmp_path / "candidate.joblib"
    report = tmp_path / "rolling_backtest.json"
    approval = tmp_path / "approval.json"
    ledger = tmp_path / "runs.sqlite"
    candidate.write_bytes(b"candidate")
    candidate_sha256 = sha256(b"candidate").hexdigest()
    write_report(report, candidate_sha256)
    write_approval(approval, candidate_sha256)

    def interrupt_copy(_source: Path, target: Path) -> None:
        Path(target).write_bytes(b"partial archive")
        raise OSError("simulated archive failure")

    monkeypatch.setattr(operations.shutil, "copyfile", interrupt_copy)
    with pytest.raises(OSError, match="simulated archive failure"):
        operations.main(
            [
                "--ledger", str(ledger), "promote",
                "--candidate", str(candidate),
                "--report", str(report),
                "--approval-file", str(approval),
            ]
        )

    assert production.read_bytes() == b"current production"
    assert not list(archive_root.rglob("*.part"))


def test_model_approval_routes_through_guarded_existing_candidate_promotion(tmp_path: Path, monkeypatch):
    approval = tmp_path / "approval.json"
    ledger = tmp_path / "runs.sqlite"
    approval.write_text("{}", encoding="utf-8")
    calls = {}

    def fake_backtest(input_path, output_dir, *, first_test, max_iter, approval_file):
        calls["backtest"] = (input_path, output_dir, first_test, max_iter, approval_file)
        return {"release_gate": {"passed": True}}

    def fake_promote(candidate_path, report_path, approval_file, *, production_path, archive_root):
        calls["promote"] = (
            candidate_path,
            report_path,
            approval_file,
            production_path,
            archive_root,
        )
        return {"status": "promoted", "production_model_sha256": "a" * 64}

    monkeypatch.setattr(operations, "rolling_backtest", fake_backtest)
    monkeypatch.setattr(operations, "promote_existing_candidate", fake_promote)

    exit_code = operations.main(
        ["--ledger", str(ledger), "model", "--approval-file", str(approval)]
    )

    assert exit_code == 0
    assert calls["backtest"] == (
        Path("data/processed/hourly_zone_demand.parquet"),
        Path("models/demand_release"),
        "2024-07",
        60,
        None,
    )
    assert calls["promote"][0:3] == (
        Path("models/demand_release/candidate.joblib"),
        Path("models/demand_release/rolling_backtest.json"),
        approval,
    )
