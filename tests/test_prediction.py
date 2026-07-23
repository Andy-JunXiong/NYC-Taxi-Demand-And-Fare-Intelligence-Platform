import pandas as pd

from nyc_taxi.monitoring import score_frames
from nyc_taxi.prediction import validate_forecast


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
