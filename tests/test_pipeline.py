from pathlib import Path

import pandas as pd
import pytest

from nyc_taxi.cleaning import clean_trips
from nyc_taxi.features import add_trip_features
from nyc_taxi.io import load_and_merge
from nyc_taxi.pipeline import main


def valid_trip(**overrides):
    row = {
        "pickup_datetime": "2013-01-04 23:55:00",
        "dropoff_datetime": "2013-01-05 00:05:00",
        "trip_distance": 2.0,
        "pickup_longitude": -73.99,
        "pickup_latitude": 40.75,
        "dropoff_longitude": -73.97,
        "dropoff_latitude": 40.77,
        "fare_amount": 12.0,
        "surcharge": 0.5,
        "tip_amount": 2.0,
    }
    row.update(overrides)
    return row


def test_cleaning_uses_total_seconds_across_midnight():
    result = clean_trips(pd.DataFrame([valid_trip()]))
    assert result.loc[0, "trip_time_in_secs"] == 600


@pytest.mark.parametrize(
    "overrides",
    [
        {"trip_distance": 0},
        {"fare_amount": -1},
        {"pickup_longitude": 0},
        {"dropoff_datetime": "2013-01-04 22:00:00"},
    ],
)
def test_cleaning_rejects_invalid_rows(overrides):
    assert clean_trips(pd.DataFrame([valid_trip(**overrides)])).empty


def test_features_are_deterministic_and_do_not_mutate_input():
    source = clean_trips(pd.DataFrame([valid_trip()]))
    result = add_trip_features(source)
    assert "pickup_hour" not in source
    assert result.loc[0, "pickup_hour"] == 23
    assert bool(result.loc[0, "is_weekend"]) is False
    assert result.loc[0, "earning"] == 14.5


def test_load_merge_and_cli(tmp_path: Path):
    trip = pd.DataFrame([valid_trip() | {"medallion": "m1", "hack_license": "h1"}])
    fare = pd.DataFrame(
        [{
            "medallion": "m1",
            "hack_license": "h1",
            "pickup_datetime": "2013-01-04 23:55:00",
            "tip_amount": 2.0,
            "surcharge": 0.5,
        }]
    )
    trip = trip.drop(columns=["tip_amount", "surcharge"])
    trip_path, fare_path, output = tmp_path / "trips.csv", tmp_path / "fares.csv", tmp_path / "out.csv"
    trip.to_csv(trip_path, index=False)
    fare.to_csv(fare_path, index=False)
    assert len(load_and_merge(trip_path, fare_path)) == 1
    assert main(["--trips", str(trip_path), "--fares", str(fare_path), "--output", str(output)]) == 0
    assert output.is_file()
    assert len(pd.read_csv(output)) == 1
