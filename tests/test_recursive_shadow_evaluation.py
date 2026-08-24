from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nyc_taxi import model_validation


PLAN_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "recursive-evaluation-plan-2026-08-24.v1.json"
)
PLAN_SHA256 = "d510a9e49d417e194fbed4d1de9b5ba07ca6593365236c88cec5143f539e166d"


def canonical_plan_sha256(plan: dict) -> str:
    encoded = json.dumps(
        plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_test_plan(
    path: Path,
    candidate_sha256: str,
    *,
    first_start: str = "2024-05-27",
    first_end: str = "2024-06-19",
) -> tuple[dict, str]:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    plan["candidate_model_sha256"] = candidate_sha256
    plan["training_period_end"] = "2024-04-30"
    plan["blocks"][0] = {"id": "A", "start_date": first_start, "end_date": first_end}
    path.write_text(json.dumps(plan, indent=4) + "\n", encoding="utf-8")
    return plan, canonical_plan_sha256(plan)


class LagModel:
    def predict(self, features):
        return features["lag_1"].to_numpy(dtype=float) + 1.0


def hourly_fixture(
    start: str = "2024-05-20",
    end: str = "2024-05-31 23:00",
) -> pd.DataFrame:
    rows = []
    for hour_index, hour in enumerate(pd.date_range(start, end, freq="h")):
        for zone in (1, 132):
            rows.append({
                "pickup_zone_id": zone,
                "pickup_hour": hour,
                "trip_count": float(10 + zone % 10 + hour_index % 24 + hour_index // 24),
            })
    return pd.DataFrame(rows)


def artifact() -> dict:
    model = LagModel()
    return {
        "global_model": model,
        "airport_model": model,
        "event_model": model,
        "airport_zone_ids": [132],
        "features": ["lag_1"],
    }


def test_committed_evaluation_plan_has_reviewed_canonical_identity():
    plan, digest = model_validation._load_evaluation_plan(PLAN_PATH, PLAN_SHA256)

    assert digest == PLAN_SHA256
    assert plan["plan_id"] == "recursive-evaluation-2026-08-24-v1"
    assert plan["candidate_model_sha256"] == (
        "29354b382cd6761c3a307c76d821bb1855354cc87eb3c8f9b020cdf83134e334"
    )
    assert [block["id"] for block in plan["blocks"]] == ["A", "B", "C", "D"]


def test_plan_identity_is_stable_across_key_order_and_whitespace(tmp_path: Path):
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    reordered = dict(reversed(list(plan.items())))
    path = tmp_path / "reformatted-plan.json"
    path.write_text(json.dumps(reordered, separators=(",", ":")), encoding="utf-8")

    loaded, digest = model_validation._load_evaluation_plan(path, PLAN_SHA256)

    assert loaded == plan
    assert digest == PLAN_SHA256


def test_plan_identity_rejects_duplicate_keys_before_digest_comparison(tmp_path: Path):
    path = tmp_path / "duplicate-plan.json"
    path.write_text(
        '{"schema_version":"1.0","schema_version":"1.0"}',
        encoding="utf-8",
    )

    with np.testing.assert_raises_regex(ValueError, "Duplicate evaluation plan key"):
        model_validation._load_evaluation_plan(path, "0" * 64)


def test_plan_identity_rejects_malformed_expected_digest_before_file_read(
    tmp_path: Path,
):
    with np.testing.assert_raises_regex(ValueError, "64 lowercase hexadecimal"):
        model_validation._load_evaluation_plan(
            tmp_path / "missing-plan.json", "A" * 64
        )


def test_plan_identity_rejects_unknown_schema_field(tmp_path: Path):
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    plan["unreviewed_override"] = True
    path = tmp_path / "expanded-plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")

    with np.testing.assert_raises_regex(ValueError, "schema mismatch"):
        model_validation._load_evaluation_plan(path, "0" * 64)


def test_recursive_day_ignores_actuals_at_and_after_forecast_start():
    hourly = hourly_fixture()
    changed = hourly.copy()
    changed.loc[changed["pickup_hour"] >= pd.Timestamp("2024-05-29"), "trip_count"] = 99999.0

    original = model_validation._recursive_day_forecast(hourly, artifact(), pd.Timestamp("2024-05-29"))
    mutated = model_validation._recursive_day_forecast(changed, artifact(), pd.Timestamp("2024-05-29"))

    np.testing.assert_array_equal(
        original["predicted_trip_count"].to_numpy(),
        mutated["predicted_trip_count"].to_numpy(),
    )
    zone = original[original["pickup_zone_id"].eq(1)].sort_values("forecast_hour")
    assert zone["predicted_trip_count"].iloc[1] == zone["predicted_trip_count"].iloc[0] + 1.0


def test_recursive_forecast_preserves_non_midnight_origin_and_temporal_isolation():
    hourly = hourly_fixture()
    origin = pd.Timestamp("2024-05-29 05:00")
    changed = hourly.copy()
    changed.loc[changed["pickup_hour"] >= origin, "trip_count"] = 99999.0

    original = model_validation._recursive_day_forecast(hourly, artifact(), origin)
    mutated = model_validation._recursive_day_forecast(changed, artifact(), origin)

    assert original["forecast_hour"].min() == origin
    assert original["forecast_hour"].max() == origin + pd.Timedelta(hours=23)
    np.testing.assert_array_equal(
        original["predicted_trip_count"].to_numpy(),
        mutated["predicted_trip_count"].to_numpy(),
    )


def test_recursive_shadow_routes_memorial_weekend_to_event_specialist():
    hourly = hourly_fixture()

    eve = model_validation._recursive_day_forecast(
        hourly, artifact(), pd.Timestamp("2024-05-26")
    )
    holiday = model_validation._recursive_day_forecast(
        hourly, artifact(), pd.Timestamp("2024-05-27")
    )

    assert eve.loc[eve["pickup_zone_id"].eq(1), "is_event_window"].eq(1).all()
    assert eve.loc[eve["pickup_zone_id"].eq(1), "event_code"].eq(0).all()
    assert eve.loc[eve["pickup_zone_id"].eq(1), "model_type"].eq("event_specialist").all()
    assert holiday.loc[holiday["pickup_zone_id"].eq(1), "event_code"].eq(5).all()
    assert holiday.loc[holiday["pickup_zone_id"].eq(1), "model_type"].eq("event_specialist").all()


def test_shadow_report_is_observational_and_contains_required_evidence(tmp_path: Path, monkeypatch):
    hourly = hourly_fixture()
    model_path = tmp_path / "candidate.joblib"
    model_path.write_bytes(b"reviewed candidate")
    monkeypatch.setattr(model_validation, "load_hourly", lambda _path: hourly)
    monkeypatch.setattr(model_validation.joblib, "load", lambda _path: artifact())
    monkeypatch.setattr(
        model_validation,
        "promote_approved_artifact",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("shadow must not promote")),
    )

    report = model_validation.recursive_shadow_evaluation(
        tmp_path / "hourly.parquet",
        model_path,
        tmp_path / "evidence",
        start_date="2024-05-28",
        end_date="2024-05-29",
    )

    assert report["evaluation_type"] == "out_of_time_daily_24h_recursive_shadow"
    assert report["observational_only"] is True
    assert report["period"]["days"] == 2
    assert len(report["daily"]) == 2
    assert report["promotion"] == {
        "status": "not_permitted",
        "reason": "observational_shadow_only",
    }
    assert len(report["segments"]["recursive_horizon"]) == 24
    assert {row["segment"] for row in report["segments"]["market"]} == {"airport", "non_airport"}
    assert report["segments"]["worst_zones"]
    assert (tmp_path / "evidence" / "recursive_shadow.json").is_file()
    assert not (tmp_path / "evidence" / "production.joblib").exists()


def test_staggered_shadow_report_has_complete_horizon_clock_crossing(tmp_path: Path, monkeypatch):
    hourly = hourly_fixture(end="2024-06-20 23:00")
    model_path = tmp_path / "candidate.joblib"
    model_path.write_bytes(b"reviewed candidate")
    model_sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()
    plan_path = tmp_path / "evaluation-plan.json"
    _plan, plan_sha256 = write_test_plan(plan_path, model_sha256)
    monkeypatch.setattr(model_validation, "load_hourly", lambda _path: hourly)
    monkeypatch.setattr(model_validation.joblib, "load", lambda _path: artifact())

    report = model_validation.recursive_shadow_evaluation(
        tmp_path / "hourly.parquet",
        model_path,
        tmp_path / "evidence",
        evaluation_plan_path=plan_path,
        expected_evaluation_plan_sha256=plan_sha256,
        evaluation_block="A",
        expected_model_sha256=model_sha256,
    )

    expected_hours = [(5 * index) % 24 for index in range(24)]
    assert report["evaluation_type"] == "out_of_time_staggered_24h_recursive_shadow"
    assert [row["origin_hour_utc"] for row in report["daily"]] == expected_hours
    assert report["origin_schedule"] == {
        "strategy": "staggered_utc_hour",
        "hour_step": 5,
        "origins": [row["forecast_origin"] for row in report["daily"]],
        "unique_origin_hours": 24,
    }
    assert report["horizon_clock_crossing"] == {
        "observed_cells": 24 * 24,
        "expected_cells": 24 * 24,
        "complete": True,
    }
    assert len(report["segments"]["forecast_clock_hour"]) == 24
    assert len(report["segments"]["horizon_clock"]) == 24 * 24
    assert {row["rows"] for row in report["segments"]["horizon_clock"]} == {2}
    assert report["identity_binding"] == {
        "status": "verified",
        "plan_id": "recursive-evaluation-2026-08-24-v1",
        "block_id": "A",
        "evaluation_plan_sha256": plan_sha256,
        "candidate_model_sha256": model_sha256,
        "verified_before_model_load": True,
        "reverified_before_report_write": True,
    }


def test_unbound_staggered_shadow_is_rejected_before_model_or_data_load(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(
        model_validation,
        "load_hourly",
        lambda _path: (_ for _ in ()).throw(AssertionError("data must not load")),
    )
    monkeypatch.setattr(
        model_validation.joblib,
        "load",
        lambda _path: (_ for _ in ()).throw(AssertionError("model must not load")),
    )

    with np.testing.assert_raises_regex(PermissionError, "bound evaluation plan"):
        model_validation.recursive_shadow_evaluation(
            tmp_path / "hourly.parquet",
            tmp_path / "candidate.joblib",
            tmp_path / "evidence",
            start_date="2024-05-27",
            end_date="2024-06-19",
            origin_hour_step=5,
        )


def test_model_digest_mismatch_is_rejected_before_deserialization_and_data_load(
    tmp_path: Path, monkeypatch
):
    model_path = tmp_path / "candidate.joblib"
    model_path.write_bytes(b"unexpected model bytes")
    expected_model_sha256 = hashlib.sha256(b"reviewed model bytes").hexdigest()
    plan_path = tmp_path / "evaluation-plan.json"
    _plan, plan_sha256 = write_test_plan(plan_path, expected_model_sha256)
    evidence_path = tmp_path / "evidence" / "recursive_shadow.json"
    evidence_path.parent.mkdir()
    evidence_path.write_bytes(b"previous valid report")
    monkeypatch.setattr(
        model_validation,
        "load_hourly",
        lambda _path: (_ for _ in ()).throw(AssertionError("data must not load")),
    )
    monkeypatch.setattr(
        model_validation.joblib,
        "load",
        lambda _path: (_ for _ in ()).throw(AssertionError("model must not load")),
    )

    with np.testing.assert_raises_regex(PermissionError, "Model SHA-256 mismatch"):
        model_validation.recursive_shadow_evaluation(
            tmp_path / "hourly.parquet",
            model_path,
            evidence_path.parent,
            evaluation_plan_path=plan_path,
            expected_evaluation_plan_sha256=plan_sha256,
            evaluation_block="A",
            expected_model_sha256=expected_model_sha256,
        )

    assert evidence_path.read_bytes() == b"previous valid report"


def test_model_is_reverified_before_report_replacement(tmp_path: Path, monkeypatch):
    hourly = hourly_fixture()
    model_path = tmp_path / "candidate.joblib"
    model_path.write_bytes(b"reviewed model bytes")
    model_sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()
    plan_path = tmp_path / "evaluation-plan.json"
    _plan, plan_sha256 = write_test_plan(plan_path, model_sha256)
    evidence_path = tmp_path / "evidence" / "recursive_shadow.json"
    evidence_path.parent.mkdir()
    evidence_path.write_bytes(b"previous valid report")
    digest_calls = iter([model_sha256, "f" * 64])
    monkeypatch.setattr(model_validation, "sha256_file", lambda _path: next(digest_calls))
    monkeypatch.setattr(model_validation, "load_hourly", lambda _path: hourly)
    monkeypatch.setattr(model_validation.joblib, "load", lambda _path: artifact())
    monkeypatch.setattr(
        model_validation,
        "_recursive_origins",
        lambda *_args, **_kwargs: [pd.Timestamp("2024-05-29 05:00")],
    )

    with np.testing.assert_raises_regex(PermissionError, "changed during evaluation"):
        model_validation.recursive_shadow_evaluation(
            tmp_path / "hourly.parquet",
            model_path,
            evidence_path.parent,
            evaluation_plan_path=plan_path,
            expected_evaluation_plan_sha256=plan_sha256,
            evaluation_block="A",
            expected_model_sha256=model_sha256,
        )

    assert evidence_path.read_bytes() == b"previous valid report"
    assert not (evidence_path.parent / "recursive_shadow.json.part").exists()


def test_plan_is_reverified_before_report_replacement(tmp_path: Path, monkeypatch):
    hourly = hourly_fixture()
    model_path = tmp_path / "candidate.joblib"
    model_path.write_bytes(b"reviewed model bytes")
    model_sha256 = hashlib.sha256(model_path.read_bytes()).hexdigest()
    plan_path = tmp_path / "evaluation-plan.json"
    _plan, plan_sha256 = write_test_plan(plan_path, model_sha256)
    evidence_path = tmp_path / "evidence" / "recursive_shadow.json"
    evidence_path.parent.mkdir()
    evidence_path.write_bytes(b"previous valid report")

    def mutate_plan_then_return_one_origin(*_args, **_kwargs):
        changed = json.loads(plan_path.read_text(encoding="utf-8"))
        changed["plan_id"] = f'{changed["plan_id"]}-changed'
        plan_path.write_text(json.dumps(changed), encoding="utf-8")
        return [pd.Timestamp("2024-05-29 05:00")]

    monkeypatch.setattr(model_validation, "load_hourly", lambda _path: hourly)
    monkeypatch.setattr(model_validation.joblib, "load", lambda _path: artifact())
    monkeypatch.setattr(
        model_validation, "_recursive_origins", mutate_plan_then_return_one_origin
    )

    with np.testing.assert_raises_regex(PermissionError, "plan SHA-256 mismatch"):
        model_validation.recursive_shadow_evaluation(
            tmp_path / "hourly.parquet",
            model_path,
            evidence_path.parent,
            evaluation_plan_path=plan_path,
            expected_evaluation_plan_sha256=plan_sha256,
            evaluation_block="A",
            expected_model_sha256=model_sha256,
        )

    assert evidence_path.read_bytes() == b"previous valid report"
    assert not (evidence_path.parent / "recursive_shadow.json.part").exists()


def test_staggered_origin_step_must_cover_all_utc_hours():
    with np.testing.assert_raises_regex(ValueError, "coprime"):
        model_validation._recursive_origins(
            pd.Timestamp("2024-05-01"),
            pd.Timestamp("2024-05-24"),
            origin_hour_step=6,
        )


def test_shadow_rejects_incomplete_target_hour_coverage(tmp_path: Path, monkeypatch):
    hourly = hourly_fixture()
    hourly = hourly[hourly["pickup_hour"].ne(pd.Timestamp("2024-05-29 06:00"))]
    model_path = tmp_path / "candidate.joblib"
    model_path.write_bytes(b"reviewed candidate")
    monkeypatch.setattr(model_validation, "load_hourly", lambda _path: hourly)
    monkeypatch.setattr(model_validation.joblib, "load", lambda _path: artifact())

    with np.testing.assert_raises_regex(ValueError, "Incomplete actuals"):
        model_validation.recursive_shadow_evaluation(
            tmp_path / "hourly.parquet",
            model_path,
            tmp_path / "evidence",
            start_date="2024-05-29",
            end_date="2024-05-29",
        )


def test_cli_passes_identity_binding_to_shadow_evaluator(tmp_path: Path, monkeypatch):
    captured = {}

    def fake_shadow(*_args, **kwargs):
        captured.update(kwargs)
        return {"promotion": {"status": "not_permitted"}}

    monkeypatch.setattr(model_validation, "recursive_shadow_evaluation", fake_shadow)

    result = model_validation.main([
        "--shadow-model", str(tmp_path / "candidate.joblib"),
        "--evaluation-plan", str(tmp_path / "evaluation-plan.json"),
        "--expected-evaluation-plan-sha256", "a" * 64,
        "--evaluation-block", "A",
        "--expected-model-sha256", "b" * 64,
    ])

    assert result == 0
    assert captured == {
        "start_date": None,
        "end_date": None,
        "origin_hour_step": 0,
        "evaluation_plan_path": tmp_path / "evaluation-plan.json",
        "expected_evaluation_plan_sha256": "a" * 64,
        "evaluation_block": "A",
        "expected_model_sha256": "b" * 64,
    }


def test_shadow_requires_complete_pre_forecast_history(tmp_path: Path, monkeypatch):
    hourly = hourly_fixture()
    monkeypatch.setattr(model_validation, "load_hourly", lambda _path: hourly)

    with np.testing.assert_raises_regex(ValueError, "168 hours"):
        model_validation.recursive_shadow_evaluation(
            tmp_path / "hourly.parquet",
            tmp_path / "candidate.joblib",
            tmp_path / "evidence",
            start_date="2024-05-21",
            end_date="2024-05-21",
        )


def test_shadow_zone_segments_exclude_negligible_actual_demand():
    scored = pd.DataFrame({
        "pickup_zone_id": [1, 1, 2, 2],
        "trip_count": [60.0, 50.0, 1.0, 0.0],
        "predicted_trip_count": [55.0, 55.0, 100.0, 100.0],
        "previous_week": [58.0, 52.0, 0.0, 0.0],
    })

    segments = model_validation._shadow_segments(
        scored, "pickup_zone_id", min_actual=100.0
    )

    assert [row["segment"] for row in segments] == ["1"]
