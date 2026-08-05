import json
from hashlib import sha256
from pathlib import Path

import pytest

import nyc_taxi.approvals as approvals
from nyc_taxi.approvals import promote_approved_artifact, require_approval


APPROVAL_TEMPLATE = Path(__file__).parents[1] / "docs" / "approval-record-template.json"


def write_approval(path: Path, **overrides) -> None:
    approval = {
        "schema_version": "1.0",
        "action": "model_promotion",
        "approved": True,
        "reviewer": "NYC Taxi maintainer",
        "approved_at": "2026-07-25T10:00:00+10:00",
        "artifact_sha256": "abc123",
    }
    approval.update(overrides)
    path.write_text(json.dumps(approval), encoding="utf-8")


def test_approval_must_match_action_and_artifact(tmp_path: Path):
    path = tmp_path / "approval.json"
    write_approval(path)
    result = require_approval(path, action="model_promotion", artifact_sha256="abc123")
    assert result["reviewer"] == "NYC Taxi maintainer"

    with pytest.raises(PermissionError, match="target artifact"):
        require_approval(path, action="model_promotion", artifact_sha256="different")
    with pytest.raises(PermissionError, match="does not approve"):
        require_approval(path, action="forecast_publication", artifact_sha256="abc123")


def test_approval_requires_named_reviewer(tmp_path: Path):
    path = tmp_path / "approval.json"
    write_approval(path, reviewer="")
    with pytest.raises(PermissionError, match="named reviewer"):
        require_approval(path, action="model_promotion", artifact_sha256="abc123")


def test_missing_approval_is_rejected(tmp_path: Path):
    with pytest.raises(PermissionError, match="not found"):
        require_approval(
            tmp_path / "missing.json",
            action="model_promotion",
            artifact_sha256="abc123",
        )


def test_approval_timestamp_requires_utc_offset(tmp_path: Path):
    path = tmp_path / "approval.json"
    write_approval(path, approved_at="2026-07-25T10:00:00")
    with pytest.raises(PermissionError, match="UTC offset"):
        require_approval(path, action="model_promotion", artifact_sha256="abc123")


def test_documented_approval_template_is_complete_and_inert():
    template = json.loads(APPROVAL_TEMPLATE.read_text(encoding="utf-8"))

    assert set(template) == {
        "schema_version",
        "action",
        "approved",
        "reviewer",
        "approved_at",
        "artifact_sha256",
    }
    assert template["schema_version"] == "1.0"
    assert template["approved"] is False
    assert all(
        str(template[field]).startswith("REPLACE_WITH_")
        for field in ("action", "reviewer", "approved_at", "artifact_sha256")
    )


def test_malformed_approval_preserves_existing_production(tmp_path: Path):
    candidate = tmp_path / "candidate.joblib"
    production = tmp_path / "production.joblib"
    approval_file = tmp_path / "approval.json"
    candidate.write_bytes(b"new candidate")
    production.write_bytes(b"current production")
    approval_file.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(PermissionError, match="unreadable or invalid JSON"):
        promote_approved_artifact(
            candidate,
            production,
            approval_file,
            action="model_promotion",
        )

    assert production.read_bytes() == b"current production"
    assert not (tmp_path / "production.joblib.part").exists()


def test_approval_record_must_be_a_json_object(tmp_path: Path):
    approval_file = tmp_path / "approval.json"
    approval_file.write_text("[]", encoding="utf-8")

    with pytest.raises(PermissionError, match="JSON object"):
        require_approval(
            approval_file,
            action="model_promotion",
            artifact_sha256="abc123",
        )


def test_promotion_copies_exact_approved_candidate(tmp_path: Path):
    candidate = tmp_path / "candidate.joblib"
    production = tmp_path / "production.joblib"
    approval_file = tmp_path / "approval.json"
    candidate_bytes = b"approved candidate bytes"
    candidate.write_bytes(candidate_bytes)
    production.write_bytes(b"previous production bytes")
    write_approval(approval_file, artifact_sha256=sha256(candidate_bytes).hexdigest())

    approval = promote_approved_artifact(
        candidate,
        production,
        approval_file,
        action="model_promotion",
    )

    assert production.read_bytes() == candidate_bytes
    assert approval["reviewer"] == "NYC Taxi maintainer"
    assert not (tmp_path / "production.joblib.part").exists()


def test_failed_promotion_preserves_existing_production(tmp_path: Path):
    candidate = tmp_path / "candidate.joblib"
    production = tmp_path / "production.joblib"
    approval_file = tmp_path / "approval.json"
    candidate.write_bytes(b"new candidate")
    production.write_bytes(b"current production")
    write_approval(approval_file, artifact_sha256="wrong-checksum")

    with pytest.raises(PermissionError, match="target artifact"):
        promote_approved_artifact(
            candidate,
            production,
            approval_file,
            action="model_promotion",
        )

    assert production.read_bytes() == b"current production"
    assert not (tmp_path / "production.joblib.part").exists()


def test_interrupted_copy_removes_partial_and_preserves_production(tmp_path: Path, monkeypatch):
    candidate = tmp_path / "candidate.joblib"
    production = tmp_path / "production.joblib"
    approval_file = tmp_path / "approval.json"
    candidate_bytes = b"new candidate"
    candidate.write_bytes(candidate_bytes)
    production.write_bytes(b"current production")
    write_approval(approval_file, artifact_sha256=sha256(candidate_bytes).hexdigest())

    def interrupt_copy(_source: Path, target: Path) -> None:
        Path(target).write_bytes(b"partial")
        raise OSError("simulated copy failure")

    monkeypatch.setattr(approvals.shutil, "copyfile", interrupt_copy)

    with pytest.raises(OSError, match="simulated copy failure"):
        promote_approved_artifact(
            candidate,
            production,
            approval_file,
            action="model_promotion",
        )

    assert production.read_bytes() == b"current production"
    assert not (tmp_path / "production.joblib.part").exists()
