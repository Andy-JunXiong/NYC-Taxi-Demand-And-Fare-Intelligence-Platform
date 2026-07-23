"""Input helpers for the historical NYC trip and fare files."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


PREFERRED_JOIN_KEYS = (
    "medallion",
    "hack_license",
    "vendor_id",
    "pickup_datetime",
)


def _read_csv(path: Path, nrows: int | None = None) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(f"Input file does not exist: {path}")
    return pd.read_csv(path, skipinitialspace=True, nrows=nrows)


def load_and_merge(
    trip_path: str | Path,
    fare_path: str | Path,
    *,
    nrows: int | None = None,
) -> pd.DataFrame:
    """Load trip/fare CSVs and merge them on stable shared trip identifiers."""
    trips = _read_csv(Path(trip_path), nrows=nrows)
    fares = _read_csv(Path(fare_path), nrows=nrows)
    keys = [key for key in PREFERRED_JOIN_KEYS if key in trips and key in fares]
    if not keys:
        raise ValueError("Trip and fare files do not share any supported join keys")

    for frame in (trips, fares):
        if "pickup_datetime" in frame:
            frame["pickup_datetime"] = pd.to_datetime(
                frame["pickup_datetime"], errors="coerce"
            )
    if "dropoff_datetime" in trips:
        trips["dropoff_datetime"] = pd.to_datetime(
            trips["dropoff_datetime"], errors="coerce"
        )

    return trips.merge(fares, on=keys, how="inner", validate="one_to_one")
