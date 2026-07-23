"""Explicit timezone and daylight-saving handling for mobility events."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def utc_to_local(value: datetime, zone: str) -> datetime:
    """Convert an aware UTC timestamp to a named local timezone."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo(zone))


def classify_local_time(value: datetime, zone: str) -> str:
    """Classify a naive local wall time as normal, ambiguous, or nonexistent."""
    if value.tzinfo is not None:
        raise ValueError("classify_local_time expects a naive wall time")
    tz = ZoneInfo(zone)
    valid_folds = []
    offsets = []
    for fold in (0, 1):
        candidate = value.replace(tzinfo=tz, fold=fold)
        round_trip = candidate.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)
        if round_trip == value:
            valid_folds.append(fold)
            offsets.append(candidate.utcoffset())
    if not valid_folds:
        return "nonexistent"
    if len(valid_folds) == 2 and offsets[0] != offsets[1]:
        return "ambiguous"
    return "normal"
