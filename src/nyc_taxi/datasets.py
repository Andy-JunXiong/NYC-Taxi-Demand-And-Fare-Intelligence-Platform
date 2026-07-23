"""Dataset naming and schema conventions for official TLC Parquet files."""

from __future__ import annotations

from pathlib import Path


SUPPORTED_TRIP_TYPES = {"yellow", "green"}
TLC_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"


def validate_period(year: int, month: int, trip_type: str) -> None:
    if trip_type not in SUPPORTED_TRIP_TYPES:
        raise ValueError(f"Unsupported trip type: {trip_type}")
    if not 2009 <= year <= 2100:
        raise ValueError("year must be between 2009 and 2100")
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")


def parquet_name(year: int, month: int, trip_type: str = "yellow") -> str:
    validate_period(year, month, trip_type)
    return f"{trip_type}_tripdata_{year}-{month:02d}.parquet"


def parquet_url(year: int, month: int, trip_type: str = "yellow") -> str:
    return f"{TLC_BASE_URL}/{parquet_name(year, month, trip_type)}"


def raw_path(root: Path, year: int, month: int, trip_type: str = "yellow") -> Path:
    return root / trip_type / f"year={year}" / f"month={month:02d}" / parquet_name(
        year, month, trip_type
    )
