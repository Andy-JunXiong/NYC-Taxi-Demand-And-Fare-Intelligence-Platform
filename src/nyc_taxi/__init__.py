"""Reusable data pipeline for the NYC taxi analysis.

Public analysis helpers are loaded lazily so standard-library-only commands such
as the raw downloader do not require the full notebook environment.
"""

from __future__ import annotations

from typing import Any

__all__ = ["CleaningConfig", "add_trip_features", "clean_trips", "load_and_merge"]


def __getattr__(name: str) -> Any:
    if name in {"CleaningConfig", "clean_trips"}:
        from .cleaning import CleaningConfig, clean_trips

        return {"CleaningConfig": CleaningConfig, "clean_trips": clean_trips}[name]
    if name == "add_trip_features":
        from .features import add_trip_features

        return add_trip_features
    if name == "load_and_merge":
        from .io import load_and_merge

        return load_and_merge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
