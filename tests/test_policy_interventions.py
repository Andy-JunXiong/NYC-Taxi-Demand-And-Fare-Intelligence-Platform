"""Controlled behavioral comparisons for the highest-value release policies.

These tests vary policy inputs in isolated temporary directories. They do not
add or exercise a production bypass for approval, digest, or validation gates.
"""

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import nyc_taxi.prediction as prediction
from nyc_taxi.approvals import promote_approved_artifact
from nyc_taxi.prediction import publish_forecast
from nyc_taxi.releases import load_latest_release


APPROVED_AT = "2026-08-14T10:00:00+10:00"


def write_approval(path: Path, *, action: str, artifact_sha256: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "action": action,
                "approved": True,
                "reviewer": "NYC Taxi maintainer",
                "approved_at": APPROVED_AT,
                "artifact_sha256": artifact_sha256,
            }
        ),
        encoding="utf-8",
    )


def prepare_promotion_case(root: Path, candidate_bytes: bytes) -> tuple[Path, Path, Path]:
    root.mkdir()
    candidate = root / "candidate.joblib"
    production = root / "production.joblib"
    approval = root / "approval.json"
    candidate.write_bytes(candidate_bytes)
    production.write_bytes(b"last known good model")
    return candidate, production, approval


def test_approval_requirement_changes_promotion_outcome(tmp_path: Path):
    candidate_bytes = b"reviewed candidate"
    approved = prepare_promotion_case(tmp_path / "approved", candidate_bytes)
    missing = prepare_promotion_case(tmp_path / "missing", candidate_bytes)
    write_approval(
        approved[2],
        action="model_promotion",
        artifact_sha256=sha256(candidate_bytes).hexdigest(),
    )

    promote_approved_artifact(*approved, action="model_promotion")
    with pytest.raises(PermissionError, match="not found"):
        promote_approved_artifact(*missing, action="model_promotion")

    observed = {
        "approval_present": approved[1].read_bytes(),
        "approval_missing": missing[1].read_bytes(),
    }
    assert observed == {
        "approval_present": candidate_bytes,
        "approval_missing": b"last known good model",
    }


def test_digest_binding_rejects_stale_approval_and_preserves_production(tmp_path: Path):
    original_candidate = b"forecast model A"
    changed_candidate = b"forecast model B"
    current = prepare_promotion_case(tmp_path / "current-approval", changed_candidate)
    stale = prepare_promotion_case(tmp_path / "stale-approval", changed_candidate)
    write_approval(
        current[2],
        action="model_promotion",
        artifact_sha256=sha256(changed_candidate).hexdigest(),
    )
    write_approval(
        stale[2],
        action="model_promotion",
        artifact_sha256=sha256(original_candidate).hexdigest(),
    )

    promote_approved_artifact(*current, action="model_promotion")
    with pytest.raises(PermissionError, match="target artifact"):
        promote_approved_artifact(*stale, action="model_promotion")

    observed = {
        "current_digest": current[1].read_bytes(),
        "stale_digest": stale[1].read_bytes(),
    }
    assert observed == {
        "current_digest": changed_candidate,
        "stale_digest": b"last known good model",
    }


class ConstantModel:
    def __init__(self, value: float):
        self.value = value

    def predict(self, frame):
        return np.full(len(frame), self.value)


def forecast_model(value: float) -> dict:
    return {
        "features": [],
        "global_model": ConstantModel(value),
        "airport_model": ConstantModel(12.0),
        "airport_zone_ids": [132],
    }


def prepare_publication_case(root: Path, model_bytes: bytes) -> dict[str, Path]:
    root.mkdir()
    paths = {
        "model": root / "production.joblib",
        "approval": root / "approval.json",
        "output": root / "forecast.parquet",
        "lineage": root / "lineage.json",
        "gate": root / "gate.json",
    }
    paths["model"].write_bytes(model_bytes)
    write_approval(
        paths["approval"],
        action="forecast_publication",
        artifact_sha256=sha256(model_bytes).hexdigest(),
    )
    paths["output"].write_bytes(b"last known good forecast")
    paths["lineage"].write_text(
        json.dumps(
            {
                "generated_at": "2026-08-13T00:00:00+00:00",
                "forecast_start": "2026-08-13 01:00:00",
            }
        ),
        encoding="utf-8",
    )
    return paths


def test_validation_gate_changes_publication_outcome_and_preserves_old_product(
    tmp_path: Path,
    monkeypatch,
):
    hours = pd.date_range("2026-08-07", periods=168, freq="h")
    hourly = pd.DataFrame(
        [
            {"pickup_zone_id": zone, "pickup_hour": hour, "trip_count": 10.0}
            for hour in hours
            for zone in (1, 132)
        ]
    )
    model_bytes = b"same reviewed forecast model"
    valid = prepare_publication_case(tmp_path / "valid", model_bytes)
    invalid = prepare_publication_case(tmp_path / "invalid", model_bytes)
    hourly_path = tmp_path / "hourly.parquet"
    hourly_path.write_bytes(b"synthetic governed hourly input")

    monkeypatch.setattr(prediction, "load_hourly", lambda _: hourly)
    monkeypatch.setattr(prediction.np, "clip", lambda values, *_: values)
    monkeypatch.setattr(
        prediction.joblib,
        "load",
        lambda path: forecast_model(-1.0 if Path(path).parent.name == "invalid" else 10.0),
    )

    released = publish_forecast(
        hourly_path,
        valid["model"],
        valid["output"],
        valid["lineage"],
        valid["gate"],
        horizon=1,
        approval_file=valid["approval"],
    )
    with pytest.raises(RuntimeError, match="publication gate failed"):
        publish_forecast(
            hourly_path,
            invalid["model"],
            invalid["output"],
            invalid["lineage"],
            invalid["gate"],
            horizon=1,
            approval_file=invalid["approval"],
        )

    observed = {
        "valid_forecast": released["gate"]["passed"],
        "invalid_forecast": json.loads(invalid["gate"].read_text(encoding="utf-8"))["passed"],
        "invalid_output": invalid["output"].read_bytes(),
    }
    assert observed == {
        "valid_forecast": True,
        "invalid_forecast": False,
        "invalid_output": b"last known good forecast",
    }
    assert valid["output"].read_bytes() == b"last known good forecast"
    latest_path = valid["output"].parent / "latest.json"
    resolved = load_latest_release(latest_path)
    published_lineage = resolved["lineage_record"]
    assert resolved["forecast_path"].read_bytes() != b"last known good forecast"
    assert published_lineage["output_sha256"] == sha256(
        resolved["forecast_path"].read_bytes()
    ).hexdigest()
    assert resolved["output_sha256"] == published_lineage["output_sha256"]
    assert published_lineage["previous_release_id"] is None
    assert not (valid["output"].parent / "archive").exists()
    assert not list(valid["output"].parent.rglob("*.part"))


def test_airport_event_global_routing_changes_decision_path(tmp_path: Path, monkeypatch):
    hours = pd.date_range("2026-08-07", periods=168, freq="h")
    hourly = pd.DataFrame(
        [
            {"pickup_zone_id": zone, "pickup_hour": hour, "trip_count": 10.0}
            for hour in hours
            for zone in (1, 132)
        ]
    )
    model = tmp_path / "production.joblib"
    model.write_bytes(b"routing model placeholder")
    artifact = {
        "features": [],
        "global_model": ConstantModel(10.0),
        "event_model": ConstantModel(20.0),
        "airport_model": ConstantModel(30.0),
        "airport_zone_ids": [132],
    }

    def controlled_event_features(timestamps: pd.Series) -> pd.DataFrame:
        forecast_hour = pd.Timestamp(timestamps.iloc[0])
        return pd.DataFrame(
            [{"event_code": 0, "is_event_window": int(forecast_hour.hour == 0)}]
        )

    monkeypatch.setattr(prediction, "load_hourly", lambda _: hourly)
    monkeypatch.setattr(prediction.joblib, "load", lambda _: artifact)
    monkeypatch.setattr(prediction, "event_features", controlled_event_features)

    frame, gate, _, _ = prediction.generate_forecast(
        tmp_path / "hourly.parquet",
        model,
        horizon=2,
        expected_model_sha256=sha256(model.read_bytes()).hexdigest(),
    )

    observed = {
        (row.forecast_hour.hour, row.pickup_zone_id): (
            row.model_type,
            row.predicted_trip_count,
        )
        for row in frame.itertuples()
    }
    assert observed == {
        (0, 1): ("event_specialist", 20.0),
        (0, 132): ("airport_specialist", 30.0),
        (1, 1): ("global", 10.0),
        (1, 132): ("airport_specialist", 30.0),
    }
    assert frame["event_code"].eq(0).all()
    assert gate["passed"]
    assert gate["checks"]["airport_model_routing"]
    assert gate["checks"]["event_model_routing"]
    assert gate["checks"]["global_model_routing"]
