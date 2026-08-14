import json
from hashlib import sha256
from pathlib import Path

import pytest

from nyc_taxi.releases import load_latest_release


def digest(content: bytes) -> str:
    return sha256(content).hexdigest()


def write_release(root: Path) -> tuple[Path, dict]:
    release_id = "20260814T000000000000Z-abcdef123456"
    release = root / "releases" / release_id
    release.mkdir(parents=True)
    forecast = b"immutable forecast"
    gate = {"passed": True, "checks": {"complete": True}}
    lineage = {
        "product": "hourly_zone_demand_forecast",
        "status": "published",
        "release_id": release_id,
        "output_sha256": digest(forecast),
        "generated_at": "2026-08-14T00:00:00+00:00",
        "forecast_start": "2026-08-15 00:00:00",
        "production_model_sha256": "a" * 64,
        "gate": gate,
    }
    (release / "forecast.parquet").write_bytes(forecast)
    (release / "lineage.json").write_text(json.dumps(lineage), encoding="utf-8")
    (release / "gate.json").write_text(json.dumps(gate), encoding="utf-8")
    relative = f"releases/{release_id}"
    pointer = {
        "schema_version": "1.0",
        "product": "hourly_zone_demand_forecast",
        "release_id": release_id,
        "release": relative,
        "forecast": f"{relative}/forecast.parquet",
        "lineage": f"{relative}/lineage.json",
        "gate": f"{relative}/gate.json",
        "output_sha256": digest(forecast),
        "lineage_sha256": digest((release / "lineage.json").read_bytes()),
        "gate_sha256": digest((release / "gate.json").read_bytes()),
        "generated_at": lineage["generated_at"],
        "forecast_start": lineage["forecast_start"],
        "model_sha256": lineage["production_model_sha256"],
    }
    latest = root / "latest.json"
    latest.write_text(json.dumps(pointer), encoding="utf-8")
    return latest, pointer


def test_load_latest_release_verifies_complete_bundle(tmp_path: Path):
    latest, pointer = write_release(tmp_path)

    release = load_latest_release(latest)

    assert release["release_id"] == pointer["release_id"]
    assert release["forecast_path"].read_bytes() == b"immutable forecast"
    assert release["lineage_record"]["release_id"] == pointer["release_id"]
    assert release["gate_record"]["passed"] is True


def test_load_latest_release_rejects_tampered_artifact(tmp_path: Path):
    latest, pointer = write_release(tmp_path)
    forecast = tmp_path / pointer["forecast"]
    forecast.write_bytes(b"tampered forecast")

    with pytest.raises(ValueError, match="does not match latest pointer digest"):
        load_latest_release(latest)


def test_load_latest_release_rejects_path_outside_bundle(tmp_path: Path):
    latest, pointer = write_release(tmp_path)
    pointer["forecast"] = "releases/outside.parquet"
    latest.write_text(json.dumps(pointer), encoding="utf-8")

    with pytest.raises(ValueError, match="outside the declared bundle"):
        load_latest_release(latest)


def test_load_latest_release_rejects_incomplete_bundle(tmp_path: Path):
    latest, pointer = write_release(tmp_path)
    (tmp_path / pointer["gate"]).unlink()

    with pytest.raises(FileNotFoundError, match="release gate not found"):
        load_latest_release(latest)
