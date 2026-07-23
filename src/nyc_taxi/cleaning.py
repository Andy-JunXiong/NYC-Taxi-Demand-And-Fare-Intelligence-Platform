"""Explicit, testable data-quality rules."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CleaningConfig:
    min_longitude: float = -74.3
    max_longitude: float = -72.9
    min_latitude: float = 40.5
    max_latitude: float = 41.8
    max_speed_mph: float = 100.0
    max_fare_per_minute: float = 3.0


REQUIRED_COLUMNS = {
    "pickup_datetime",
    "dropoff_datetime",
    "trip_distance",
    "pickup_longitude",
    "pickup_latitude",
    "dropoff_longitude",
    "dropoff_latitude",
    "fare_amount",
}


def clean_trips(
    frame: pd.DataFrame, config: CleaningConfig | None = None
) -> pd.DataFrame:
    """Return valid trips without mutating the input frame."""
    config = config or CleaningConfig()
    missing = REQUIRED_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    result = frame.copy()
    result["pickup_datetime"] = pd.to_datetime(result["pickup_datetime"], errors="coerce")
    result["dropoff_datetime"] = pd.to_datetime(result["dropoff_datetime"], errors="coerce")
    result["trip_time_in_secs"] = (
        result["dropoff_datetime"] - result["pickup_datetime"]
    ).dt.total_seconds()

    numeric = [
        "trip_distance",
        "pickup_longitude",
        "pickup_latitude",
        "dropoff_longitude",
        "dropoff_latitude",
        "fare_amount",
    ]
    for column in numeric:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    valid = result[numeric + ["trip_time_in_secs"]].notna().all(axis=1)
    valid &= result["trip_distance"].gt(0)
    valid &= result["trip_time_in_secs"].gt(0)
    valid &= result["fare_amount"].ge(0)
    for prefix in ("pickup", "dropoff"):
        valid &= result[f"{prefix}_longitude"].between(
            config.min_longitude, config.max_longitude
        )
        valid &= result[f"{prefix}_latitude"].between(
            config.min_latitude, config.max_latitude
        )
    valid &= (result["pickup_longitude"] != result["dropoff_longitude"]) | (
        result["pickup_latitude"] != result["dropoff_latitude"]
    )

    result = result.loc[valid].copy()
    result["drive_speed_mph"] = result["trip_distance"] / (
        result["trip_time_in_secs"] / 3600
    )
    result["fare_amount_per_minute"] = result["fare_amount"] / (
        result["trip_time_in_secs"] / 60
    )
    result = result.loc[
        result["drive_speed_mph"].le(config.max_speed_mph)
        & result["fare_amount_per_minute"].le(config.max_fare_per_minute)
    ]
    return result.reset_index(drop=True)
