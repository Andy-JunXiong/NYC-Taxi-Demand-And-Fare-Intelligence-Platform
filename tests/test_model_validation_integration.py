import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import nyc_taxi.model_validation as model_validation
from nyc_taxi.forecast import MODEL_FEATURES


CANDIDATE_BYTES = b"deterministic candidate artifact"


class FakeModel:
    def fit(self, _features, _target, sample_weight=None):
        return self

    def predict(self, features):
        return np.full(len(features), 5.0)


def feature_table() -> pd.DataFrame:
    rows = []
    for pickup_hour in (pd.Timestamp("2024-06-01"), pd.Timestamp("2024-07-01")):
        for pickup_zone_id, is_event_window in ((1, 1), (132, 0)):
            row = {feature: 0 for feature in MODEL_FEATURES}
            row.update(
                {
                    "pickup_hour": pickup_hour,
                    "pickup_zone_id": pickup_zone_id,
                    "trip_count": 5,
                    "lag_168": 5,
                    "is_event_window": is_event_window,
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def configure_backtest(monkeypatch, *, gate_passed: bool) -> None:
    features = feature_table()
    monkeypatch.setattr(model_validation, "load_hourly", lambda _path: pd.DataFrame())
    monkeypatch.setattr(model_validation, "make_feature_table", lambda _hourly: features)
    monkeypatch.setattr(model_validation, "_model", lambda _max_iter: FakeModel())
    monkeypatch.setattr(
        model_validation,
        "release_decision",
        lambda _folds: {"passed": gate_passed, "checks": {}},
    )
    monkeypatch.setattr(
        model_validation.joblib,
        "dump",
        lambda _artifact, path: Path(path).write_bytes(CANDIDATE_BYTES),
    )


def write_approval(path: Path, artifact_sha256: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "action": "model_promotion",
                "approved": True,
                "reviewer": "NYC Taxi maintainer",
                "approved_at": "2026-08-05T10:00:00+10:00",
                "artifact_sha256": artifact_sha256,
            }
        ),
        encoding="utf-8",
    )


def test_rolling_backtest_waits_for_approval_after_passed_gate(tmp_path: Path, monkeypatch):
    configure_backtest(monkeypatch, gate_passed=True)

    report = model_validation.rolling_backtest(
        tmp_path / "hourly.parquet",
        tmp_path,
        first_test="2024-07",
    )

    candidate_sha256 = sha256(CANDIDATE_BYTES).hexdigest()
    assert report["promotion"] == {
        "status": "awaiting_human_approval",
        "candidate_sha256": candidate_sha256,
    }
    assert (tmp_path / "candidate.joblib").read_bytes() == CANDIDATE_BYTES
    assert not (tmp_path / "production.joblib").exists()
    assert json.loads((tmp_path / "rolling_backtest.json").read_text(encoding="utf-8"))["promotion"] == report["promotion"]


def test_rolling_backtest_promotes_exact_approved_candidate(tmp_path: Path, monkeypatch):
    configure_backtest(monkeypatch, gate_passed=True)
    approval_file = tmp_path / "approval.json"
    candidate_sha256 = sha256(CANDIDATE_BYTES).hexdigest()
    write_approval(approval_file, candidate_sha256)

    report = model_validation.rolling_backtest(
        tmp_path / "hourly.parquet",
        tmp_path,
        first_test="2024-07",
        approval_file=approval_file,
    )

    assert report["promotion"] == {
        "status": "promoted",
        "reviewer": "NYC Taxi maintainer",
        "approved_at": "2026-08-05T10:00:00+10:00",
        "candidate_sha256": candidate_sha256,
    }
    assert (tmp_path / "production.joblib").read_bytes() == CANDIDATE_BYTES
    assert not (tmp_path / "production.joblib.part").exists()
    assert json.loads((tmp_path / "rolling_backtest.json").read_text(encoding="utf-8"))["promotion"] == report["promotion"]


def test_rolling_backtest_rejects_checksum_mismatch_without_replacing_production(tmp_path: Path, monkeypatch):
    configure_backtest(monkeypatch, gate_passed=True)
    approval_file = tmp_path / "approval.json"
    write_approval(approval_file, "0" * 64)
    production = tmp_path / "production.joblib"
    production.write_bytes(b"current production")

    with pytest.raises(PermissionError, match="target artifact"):
        model_validation.rolling_backtest(
            tmp_path / "hourly.parquet",
            tmp_path,
            first_test="2024-07",
            approval_file=approval_file,
        )

    assert production.read_bytes() == b"current production"
    assert not (tmp_path / "production.joblib.part").exists()
    persisted = json.loads((tmp_path / "rolling_backtest.json").read_text(encoding="utf-8"))
    assert persisted["promotion"]["status"] == "awaiting_human_approval"


def test_rolling_backtest_failed_gate_never_promotes(tmp_path: Path, monkeypatch):
    configure_backtest(monkeypatch, gate_passed=False)
    approval_file = tmp_path / "approval.json"
    write_approval(approval_file, sha256(CANDIDATE_BYTES).hexdigest())
    production = tmp_path / "production.joblib"
    production.write_bytes(b"current production")

    report = model_validation.rolling_backtest(
        tmp_path / "hourly.parquet",
        tmp_path,
        first_test="2024-07",
        approval_file=approval_file,
    )

    assert report["promotion"] == {"status": "blocked", "reason": "release_gate_failed"}
    assert production.read_bytes() == b"current production"
    assert not (tmp_path / "production.joblib.part").exists()
