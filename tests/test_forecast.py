from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from nyc_taxi.forecast import make_feature_table, metrics, time_split, train_forecast
from nyc_taxi.events import EVENT_CODES, event_features


def hourly_fixture():
    hours = pd.date_range("2024-01-01", "2024-03-31 23:00", freq="h")
    rows = []
    for zone in (1, 2):
        for timestamp in hours:
            demand = zone + timestamp.hour + (5 if timestamp.dayofweek < 5 else 0)
            rows.append((zone, timestamp, demand))
    return pd.DataFrame(rows, columns=["pickup_zone_id", "pickup_hour", "trip_count"])


def test_features_use_only_past_values_and_fill_grid():
    source = hourly_fixture().iloc[1:].copy()
    result = make_feature_table(source)
    row = result.loc[
        (result["pickup_zone_id"] == 1)
        & (result["pickup_hour"] == pd.Timestamp("2024-01-09 00:00"))
    ].iloc[0]
    original = hourly_fixture().set_index(["pickup_zone_id", "pickup_hour"])
    assert row["lag_24"] == original.loc[(1, pd.Timestamp("2024-01-08 00:00")), "trip_count"]
    assert {"is_us_holiday", "is_airport_zone", "weather_missing"}.issubset(result.columns)


def test_event_calendar_marks_new_year_phases():
    timestamps = pd.Series(pd.to_datetime(["2024-12-31 20:00", "2025-01-01 03:00", "2025-01-02 03:00"]))
    result = event_features(timestamps)
    assert result.iloc[0]["is_new_year_window"] == 1
    assert result.iloc[1]["event_code"] == EVENT_CODES["new_year"]
    assert result.iloc[1]["is_event_overnight"] == 1
    assert result.iloc[2]["is_event_window"] == 0


def test_event_calendar_routes_memorial_day_weekend_window():
    timestamps = pd.Series(pd.to_datetime([
        "2026-05-23 12:00", "2026-05-24 12:00", "2026-05-25 12:00", "2026-05-26 12:00"
    ]))

    result = event_features(timestamps)

    assert result.iloc[0]["is_event_window"] == 0
    assert result.iloc[1]["event_code"] == EVENT_CODES["none"]
    assert result.iloc[1]["is_event_eve"] == 1
    assert result.iloc[1]["is_event_window"] == 1
    assert result.iloc[2]["event_code"] == EVENT_CODES["memorial_day"]
    assert result.iloc[2]["is_event_window"] == 1
    assert result.iloc[3]["is_event_window"] == 0


def test_time_split_uses_last_two_months():
    train, validation, test, split = time_split(make_feature_table(hourly_fixture()))
    assert split.validation_month == "2024-02"
    assert split.test_month == "2024-03"
    assert train["pickup_hour"].max() < validation["pickup_hour"].min()
    assert validation["pickup_hour"].max() < test["pickup_hour"].min()


def test_metrics_are_zero_for_perfect_prediction():
    truth = pd.Series([0.0, 2.0, 10.0])
    result = metrics(truth, truth.to_numpy(), high_threshold=5)
    assert result["mae"] == 0
    assert result["rmse"] == 0
    assert result["wape"] == 0
    assert result["high_demand_precision"] == 1


def test_training_writes_artifacts(tmp_path: Path):
    source = tmp_path / "hourly.parquet"
    frame = hourly_fixture()
    connection = duckdb.connect()
    connection.register("hourly", frame)
    connection.execute(f"COPY hourly TO '{source.as_posix()}' (FORMAT PARQUET)")
    connection.close()
    output = tmp_path / "model"
    report = train_forecast(source, output, max_iter=5)
    assert report["split"]["test_month"] == "2024-03"
    assert (output / "demand_forecast.joblib").is_file()
    assert (output / "metrics.json").is_file()
    assert (output / "test_predictions.parquet").is_file()
