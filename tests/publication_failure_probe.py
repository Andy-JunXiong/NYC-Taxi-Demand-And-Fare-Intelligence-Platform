"""Probe immutable forecast publication under injected write failures."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import duckdb
import joblib
import pandas as pd
from sklearn.dummy import DummyRegressor

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from nyc_taxi.prediction import publish_forecast
from nyc_taxi.releases import load_latest_release


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def constant_model(value: float) -> DummyRegressor:
    features = pd.DataFrame({"hour": [0, 1]})
    model = DummyRegressor(strategy="constant", constant=value)
    model.fit(features, [value, value])
    return model


def write_initial_release(published: Path) -> Path:
    release_id = "20260813T000000000000Z-oldrelease000"
    release = published / "releases" / release_id
    release.mkdir(parents=True)
    forecast = release / "forecast.parquet"
    lineage = release / "lineage.json"
    gate = release / "gate.json"
    forecast.write_bytes(b"last known good canonical forecast")
    gate_record = {"passed": True}
    lineage_record = {
        "product": "hourly_zone_demand_forecast",
        "status": "published",
        "release_id": release_id,
        "output_sha256": sha256_file(forecast),
        "generated_at": "2026-08-13T00:00:00+00:00",
        "forecast_start": "2026-08-13 01:00:00",
        "production_model_sha256": "a" * 64,
        "gate": gate_record,
    }
    lineage.write_text(json.dumps(lineage_record), encoding="utf-8")
    gate.write_text(json.dumps(gate_record), encoding="utf-8")
    relative = f"releases/{release_id}"
    latest = published / "latest.json"
    latest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "product": "hourly_zone_demand_forecast",
                "release_id": release_id,
                "release": relative,
                "forecast": f"{relative}/forecast.parquet",
                "lineage": f"{relative}/lineage.json",
                "gate": f"{relative}/gate.json",
                "output_sha256": sha256_file(forecast),
                "lineage_sha256": sha256_file(lineage),
                "gate_sha256": sha256_file(gate),
                "generated_at": lineage_record["generated_at"],
                "forecast_start": lineage_record["forecast_start"],
                "model_sha256": lineage_record["production_model_sha256"],
            }
        ),
        encoding="utf-8",
    )
    return latest


def prepare_case(root: Path) -> dict[str, Path]:
    inputs = root / "inputs"
    published = root / "published"
    inputs.mkdir(parents=True)
    published.mkdir(parents=True)

    hours = pd.date_range("2026-08-07", periods=168, freq="h")
    hourly = pd.DataFrame(
        [
            {"pickup_zone_id": zone, "pickup_hour": hour, "trip_count": 10.0}
            for hour in hours
            for zone in (1, 132)
        ]
    )
    hourly_path = inputs / "hourly.parquet"
    connection = duckdb.connect()
    try:
        connection.register("hourly", hourly)
        connection.execute(
            f"COPY hourly TO '{hourly_path.resolve().as_posix()}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        connection.close()

    model_path = inputs / "production.joblib"
    joblib.dump(
        {
            "features": ["hour"],
            "global_model": constant_model(10.0),
            "event_model": constant_model(20.0),
            "airport_model": constant_model(30.0),
            "airport_zone_ids": [132],
        },
        model_path,
    )
    approval = inputs / "approval.json"
    approval.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "action": "forecast_publication",
                "approved": True,
                "reviewer": "Synthetic failure probe",
                "approved_at": "2026-08-14T10:00:00+10:00",
                "artifact_sha256": sha256_file(model_path),
            }
        ),
        encoding="utf-8",
    )
    output = published / "forecast.parquet"
    lineage = published / "lineage.json"
    output.write_bytes(b"legacy forecast remains noncanonical")
    lineage.write_text("legacy lineage remains noncanonical", encoding="utf-8")
    return {
        "hourly": hourly_path,
        "model": model_path,
        "approval": approval,
        "output": output,
        "lineage": lineage,
        "latest": write_initial_release(published),
        "gate": published / "gate.json",
    }


def bundle_is_complete(release: Path) -> bool:
    forecast = release / "forecast.parquet"
    lineage = release / "lineage.json"
    gate = release / "gate.json"
    if not all(path.is_file() for path in (forecast, lineage, gate)):
        return False
    lineage_record = json.loads(lineage.read_text(encoding="utf-8"))
    gate_record = json.loads(gate.read_text(encoding="utf-8"))
    return (
        lineage_record.get("product") == "hourly_zone_demand_forecast"
        and lineage_record.get("status") == "published"
        and lineage_record.get("release_id") == release.name
        and lineage_record.get("output_sha256") == sha256_file(forecast)
        and gate_record.get("passed") is True
        and lineage_record.get("gate") == gate_record
    )


def run_scenario(root: Path, failure_point: str) -> dict:
    paths = prepare_case(root)
    before = {
        name: sha256_file(paths[name])
        for name in ("output", "lineage", "latest")
    }
    previous_release_id = load_latest_release(paths["latest"])["release_id"]
    latest_part = paths["latest"].with_suffix(".json.part")
    original_write_text = Path.write_text
    original_replace = Path.replace

    def injected_write_text(path: Path, *args, **kwargs):
        is_lineage_stage = path.name == "lineage.json.part" and path.parent.name.startswith(".pending-")
        if (failure_point == "lineage_write" and is_lineage_stage) or (
            failure_point == "latest_write" and path.resolve() == latest_part.resolve()
        ):
            raise OSError(f"injected {failure_point} failure")
        return original_write_text(path, *args, **kwargs)

    def injected_replace(path: Path, target: Path):
        if failure_point == "latest_replace" and path.resolve() == latest_part.resolve():
            raise OSError(f"injected {failure_point} failure")
        return original_replace(path, target)

    caught = None
    with patch.object(Path, "write_text", injected_write_text), patch.object(
        Path, "replace", injected_replace
    ):
        try:
            publish_forecast(
                paths["hourly"],
                paths["model"],
                paths["output"],
                paths["lineage"],
                paths["gate"],
                horizon=1,
                approval_file=paths["approval"],
            )
        except OSError as exc:
            caught = str(exc)

    changed = {
        name: sha256_file(paths[name]) != before[name]
        for name in ("output", "lineage", "latest")
    }
    current = load_latest_release(paths["latest"])
    releases_root = paths["latest"].parent / "releases"
    visible_releases = [
        path
        for path in releases_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    ]
    pending = [path for path in releases_root.iterdir() if path.name.startswith(".pending-")]
    residue = [
        path.relative_to(paths["latest"].parent).as_posix()
        for path in paths["latest"].parent.rglob("*.part")
    ] + [path.relative_to(paths["latest"].parent).as_posix() for path in pending]
    orphan_count = len(visible_releases) - 1
    result = {
        "failure_point": failure_point,
        "exception": caught,
        "canonical_files_changed": changed,
        "previous_pointer_preserved": current["release_id"] == previous_release_id,
        "all_visible_bundles_complete": all(bundle_is_complete(path) for path in visible_releases),
        "orphan_release_count": orphan_count,
        "temporary_residue": residue,
        "gate_passed": json.loads(paths["gate"].read_text(encoding="utf-8"))["passed"],
    }
    result["safe_failure"] = (
        caught is not None
        and not any(changed.values())
        and result["previous_pointer_preserved"]
        and result["all_visible_bundles_complete"]
        and not residue
        and orphan_count == (0 if failure_point == "lineage_write" else 1)
    )
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="nyc-publication-failure-") as temporary:
        root = Path(temporary)
        scenarios = [
            run_scenario(root / "lineage-write", "lineage_write"),
            run_scenario(root / "latest-write", "latest_write"),
            run_scenario(root / "latest-replace", "latest_replace"),
        ]
    gap_confirmed = any(not scenario["safe_failure"] for scenario in scenarios)
    print(
        json.dumps(
            {
                "status": "gap_confirmed" if gap_confirmed else "safe_failure_behavior_observed",
                "scenarios": scenarios,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
