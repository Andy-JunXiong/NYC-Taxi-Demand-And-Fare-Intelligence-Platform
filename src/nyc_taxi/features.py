"""Feature engineering shared by analysis and model code."""

from __future__ import annotations

import pandas as pd


def add_trip_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Add temporal and earnings features without mutating the input."""
    if "pickup_datetime" not in frame:
        raise ValueError("Missing required column: pickup_datetime")
    result = frame.copy()
    pickup = pd.to_datetime(result["pickup_datetime"], errors="coerce")
    result["pickup_date"] = pickup.dt.date
    result["pickup_hour"] = pickup.dt.hour
    result["pickup_day"] = pickup.dt.day
    result["pickup_day_of_week"] = pickup.dt.day_name()
    result["pickup_month"] = pickup.dt.month
    result["pickup_year"] = pickup.dt.year
    result["is_weekend"] = pickup.dt.dayofweek.ge(5)

    money_columns = [c for c in ("fare_amount", "surcharge", "tip_amount") if c in result]
    if money_columns:
        result["earning"] = result[money_columns].fillna(0).sum(axis=1)
        if "trip_time_in_secs" in result:
            result["earning_per_minute"] = result["earning"] / (
                result["trip_time_in_secs"] / 60
            )
        if "trip_distance" in result:
            result["earning_per_mile"] = result["earning"] / result["trip_distance"]
    return result
