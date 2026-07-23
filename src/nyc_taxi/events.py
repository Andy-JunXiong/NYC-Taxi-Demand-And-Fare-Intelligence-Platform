"""Deterministic major-event calendar features for NYC demand models."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd


EVENT_CODES = {"none": 0, "new_year": 1, "independence_day": 2, "thanksgiving": 3, "christmas": 4}


def thanksgiving(year: int) -> date:
    first = date(year, 11, 1)
    return first + timedelta(days=(3 - first.weekday()) % 7 + 21)


def event_dates(year: int) -> dict[date, int]:
    return {
        date(year, 1, 1): EVENT_CODES["new_year"],
        date(year, 7, 4): EVENT_CODES["independence_day"],
        thanksgiving(year): EVENT_CODES["thanksgiving"],
        date(year, 12, 25): EVENT_CODES["christmas"],
    }


def event_features(timestamp: pd.Series) -> pd.DataFrame:
    """Return event identity, phase, and proximity without using future demand."""
    values = pd.to_datetime(timestamp)
    unique = pd.DatetimeIndex(values.drop_duplicates().sort_values())
    cache = {}
    for ts in unique:
        events = {}
        for year in range(ts.year - 1, ts.year + 2):
            events.update(event_dates(year))
        today = ts.date()
        tomorrow = today + timedelta(days=1)
        code = events.get(today, 0)
        is_eve = tomorrow in events
        new_year_window = (ts.month == 12 and ts.day == 31 and ts.hour >= 18) or (
            ts.month == 1 and ts.day == 1 and ts.hour <= 6
        )
        event_times = sorted(pd.Timestamp(day) for day in events)
        future = [event for event in event_times if event >= ts]
        past = [event for event in event_times if event <= ts]
        to_event = min(168.0, (future[0] - ts).total_seconds() / 3600) if future else 168.0
        since_event = min(168.0, (ts - past[-1]).total_seconds() / 3600) if past else 168.0
        cache[ts] = (
            code, int(code > 0 or new_year_window), int(is_eve),
            int(ts.month == 1 and ts.day == 1 and ts.hour <= 5), int(new_year_window),
            float(max(to_event, 0)), float(max(since_event, 0)),
        )
    mapped = [cache[pd.Timestamp(ts)] for ts in values]
    return pd.DataFrame(mapped, index=timestamp.index, columns=[
        "event_code", "is_event_window", "is_event_eve", "is_event_overnight",
        "is_new_year_window", "hours_to_major_event", "hours_since_major_event",
    ])
