import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import nyc_taxi.prediction as prediction
from nyc_taxi.forecast import AIRPORT_ZONE_IDS
from nyc_taxi.monitoring import score_frames
from nyc_taxi.prediction import publish_forecast, validate_forecast, write_forecast_candidate


def forecast_fixture():
    rows = []
    for hour in pd.date_range("2025-01-01", periods=2, freq="h"):
        for zone in (1, 132):
            rows.append({
                "pickup_zone_id": zone, "forecast_hour": hour,
                "predicted_trip_count": 10.0,
                "model_type": "airport_specialist" if zone == 132 else "global",
                "event_code": 0,
            })
    return pd.DataFrame(rows)


def test_forecast_publication_gate_checks_grid_and_routing():
    frame = forecast_fixture()
    assert validate_forecast(frame, {1, 132}, 2, {132})["passed"]
    broken = frame.iloc[:-1]
    assert not validate_forecast(broken, {1, 132}, 2, {132})["passed"]


def test_airport_specialist_routing_covers_jfk_and_laguardia():
    assert set(AIRPORT_ZONE_IDS) == {132, 138}
    frame = pd.DataFrame({
        "pickup_zone_id": [132, 138],
        "forecast_hour": [pd.Timestamp("2025-01-01")] * 2,
        "predicted_trip_count": [10.0, 10.0],
        "model_type": ["airport_specialist", "airport_specialist"],
        "event_code": [0, 0],
    })
    result = validate_forecast(frame, {132, 138}, 1, set(AIRPORT_ZONE_IDS))
    assert result["passed"]
    assert result["checks"]["airport_model_routing"]


def test_forecast_publication_gate_blocks_negative_prediction():
    frame = forecast_fixture()
    frame.loc[0, "predicted_trip_count"] = -1.0
    result = validate_forecast(frame, {1, 132}, 2, {132})
    assert not result["passed"]
    assert not result["checks"]["no_negative_predictions"]


def test_forecast_publication_requires_matching_approval_before_writes(tmp_path: Path):
    model = tmp_path / "production.joblib"
    model.write_bytes(b"model placeholder")
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "schema_version": "1.0",
        "action": "forecast_publication",
        "approved": True,
        "reviewer": "NYC Taxi maintainer",
        "approved_at": "2026-07-25T10:00:00+10:00",
        "artifact_sha256": "wrong-checksum",
    }), encoding="utf-8")
    output = tmp_path / "forecast.parquet"
    lineage = tmp_path / "lineage.json"
    gate = tmp_path / "gate.json"

    with pytest.raises(PermissionError, match="target artifact"):
        publish_forecast(
            tmp_path / "hourly.parquet",
            model,
            output,
            lineage,
            gate,
            approval_file=approval,
        )

    assert not output.exists()
    assert not lineage.exists()
    assert not gate.exists()


def test_negative_prediction_does_not_replace_published_product(tmp_path: Path, monkeypatch):
    class ConstantModel:
        def __init__(self, value: float):
            self.value = value

        def predict(self, frame):
            return np.full(len(frame), self.value)

    hours = pd.date_range("2025-01-01", periods=168, freq="h")
    hourly = pd.DataFrame([
        {"pickup_zone_id": zone, "pickup_hour": hour, "trip_count": 10.0}
        for hour in hours
        for zone in (1, 132)
    ])
    artifact = {
        "features": [],
        "global_model": ConstantModel(-1.0),
        "airport_model": ConstantModel(10.0),
        "airport_zone_ids": [132, 138],
    }
    monkeypatch.setattr(prediction.joblib, "load", lambda _: artifact)
    monkeypatch.setattr(prediction, "load_hourly", lambda _: hourly)
    monkeypatch.setattr(prediction.np, "clip", lambda values, *_: values)

    model = tmp_path / "production.joblib"
    model_bytes = b"approved model placeholder"
    model.write_bytes(model_bytes)
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({
        "schema_version": "1.0",
        "action": "forecast_publication",
        "approved": True,
        "reviewer": "NYC Taxi maintainer",
        "approved_at": "2026-08-01T10:00:00+10:00",
        "artifact_sha256": sha256(model_bytes).hexdigest(),
    }), encoding="utf-8")
    output = tmp_path / "forecast.parquet"
    lineage = tmp_path / "lineage.json"
    gate = tmp_path / "gate.json"
    output.write_bytes(b"existing published forecast")
    lineage.write_text("existing lineage", encoding="utf-8")

    with pytest.raises(RuntimeError, match="publication gate failed"):
        publish_forecast(
            tmp_path / "hourly.parquet",
            model,
            output,
            lineage,
            gate,
            horizon=1,
            approval_file=approval,
        )

    assert output.read_bytes() == b"existing published forecast"
    assert lineage.read_text(encoding="utf-8") == "existing lineage"
    assert json.loads(gate.read_text(encoding="utf-8"))["checks"]["no_negative_predictions"] is False


def test_staging_candidate_is_generated_without_publication_side_effects(tmp_path: Path, monkeypatch):
    class ConstantModel:
        def __init__(self, value: float):
            self.value = value

        def predict(self, frame):
            return np.full(len(frame), self.value)

    hours = pd.date_range("2026-04-24", periods=168, freq="h")
    hourly = pd.DataFrame([
        {"pickup_zone_id": zone, "pickup_hour": hour, "trip_count": 10.0}
        for hour in hours
        for zone in (1, 132)
    ])
    artifact = {
        "features": [],
        "global_model": ConstantModel(8.0),
        "airport_model": ConstantModel(12.0),
        "airport_zone_ids": [132],
    }
    monkeypatch.setattr(prediction.joblib, "load", lambda _: artifact)
    monkeypatch.setattr(prediction, "load_hourly", lambda _: hourly)

    model = tmp_path / "candidate.joblib"
    model.write_bytes(b"reviewed model")
    model_sha256 = sha256(model.read_bytes()).hexdigest()
    report = tmp_path / "rolling_backtest.json"
    report.write_text("{}", encoding="utf-8")
    gold = tmp_path / "gold.parquet"
    gold.write_bytes(b"cutoff gold")
    output_dir = tmp_path / "forecast-candidate"

    lineage = write_forecast_candidate(
        gold,
        model,
        report,
        output_dir,
        horizon=24,
        expected_model_sha256=model_sha256,
    )

    assert lineage["status"] == "candidate"
    assert lineage["forecast_start"] == "2026-05-01 00:00:00"
    assert lineage["source_model_sha256"] == model_sha256
    assert "production_model" not in lineage
    assert "publication_approval" not in lineage
    assert (output_dir / "forecast.parquet").is_file()
    assert json.loads((output_dir / "gate.json").read_text(encoding="utf-8"))["passed"]
    assert not (output_dir / "latest.json").exists()
    assert not (output_dir / "archive").exists()


def test_failed_staging_candidate_writes_only_gate_evidence(tmp_path: Path, monkeypatch):
    class ConstantModel:
        def __init__(self, value: float):
            self.value = value

        def predict(self, frame):
            return np.full(len(frame), self.value)

    hours = pd.date_range("2026-04-24", periods=168, freq="h")
    hourly = pd.DataFrame([
        {"pickup_zone_id": zone, "pickup_hour": hour, "trip_count": 10.0}
        for hour in hours
        for zone in (1, 132)
    ])
    artifact = {
        "features": [],
        "global_model": ConstantModel(-1.0),
        "airport_model": ConstantModel(12.0),
        "airport_zone_ids": [132],
    }
    monkeypatch.setattr(prediction.joblib, "load", lambda _: artifact)
    monkeypatch.setattr(prediction, "load_hourly", lambda _: hourly)
    monkeypatch.setattr(prediction.np, "clip", lambda values, *_: values)
    model = tmp_path / "candidate.joblib"
    model.write_bytes(b"reviewed model")
    report = tmp_path / "rolling_backtest.json"
    report.write_text("{}", encoding="utf-8")
    gold = tmp_path / "gold.parquet"
    gold.write_bytes(b"cutoff gold")
    output_dir = tmp_path / "forecast-candidate"

    with pytest.raises(RuntimeError, match="candidate gate failed"):
        write_forecast_candidate(
            gold,
            model,
            report,
            output_dir,
            horizon=1,
            expected_model_sha256=sha256(model.read_bytes()).hexdigest(),
        )

    assert json.loads((output_dir / "gate.json").read_text(encoding="utf-8"))["checks"]["no_negative_predictions"] is False
    assert not (output_dir / "forecast.parquet").exists()
    assert not (output_dir / "lineage.json").exists()
    assert not (output_dir / "latest.json").exists()


def test_monitor_scores_zero_filled_zone_hours():
    forecast = forecast_fixture()
    actual = pd.DataFrame({
        "pickup_zone_id": [1, 132],
        "pickup_hour": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-01-01 01:00")],
        "trip_count": [10.0, 10.0],
    })
    result = score_frames(forecast, actual)
    assert result["status"] == "scored"
    assert result["scored_rows"] == 4


def test_monitor_waits_when_actuals_have_not_arrived():
    actual = pd.DataFrame({
        "pickup_zone_id": [1], "pickup_hour": [pd.Timestamp("2024-12-31")], "trip_count": [1.0]
    })
    assert score_frames(forecast_fixture(), actual)["status"] == "waiting_for_actuals"
