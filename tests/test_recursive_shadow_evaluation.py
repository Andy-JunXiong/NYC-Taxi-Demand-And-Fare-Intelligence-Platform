from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from nyc_taxi import model_validation


class LagModel:
    def predict(self, features):
        return features["lag_1"].to_numpy(dtype=float) + 1.0


def hourly_fixture() -> pd.DataFrame:
    rows = []
    for hour_index, hour in enumerate(pd.date_range("2024-05-20", "2024-05-31 23:00", freq="h")):
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
