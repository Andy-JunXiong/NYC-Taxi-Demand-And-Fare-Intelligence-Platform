import json
from datetime import datetime
from pathlib import Path

import duckdb
import pytest

from mobility_core.time import classify_local_time, utc_to_local
from sydney_taxi.capture import load_env_file, resolve_url
from sydney_taxi.governance import build_history_silver, normalize_history


def history_payload():
    base = {
        "rank_id": "P2P0003",
        "tsn": "275077",
        "comments": "Penrith Station, Stand C",
        "total_bays": "2",
        "start_time": "2024-06-24T23:45:00.000Z",
        "end_time": "2024-06-25T00:00:00.000Z",
        "average_wait": "100",
    }
    return {
        "rank_history": [
            base | {"class": "taxi", "from_previous_count": "4", "total": "10", "new_arrivals": "6"},
            base | {"class": "passenger", "from_previous_count": "Low", "total": "Medium", "new_arrivals": "High"},
            base | {"class": "wat", "from_previous_count": "0", "total": "1", "new_arrivals": "1"},
        ]
    }


def test_sydney_dst_classification_and_utc_conversion():
    assert classify_local_time(datetime(2024, 10, 6, 2, 30), "Australia/Sydney") == "nonexistent"
    assert classify_local_time(datetime(2024, 4, 7, 2, 30), "Australia/Sydney") == "ambiguous"
    local = utc_to_local(datetime.fromisoformat("2024-06-25T00:00:00+00:00"), "Australia/Sydney")
    assert local.hour == 10


def test_historical_url_is_configured_not_guessed(monkeypatch):
    monkeypatch.setenv(
        "TFNSW_TAXI_RANK_HISTORICAL_URL_TEMPLATE",
        "https://example.test/history/{rank_id}/{date}",
    )
    assert resolve_url("historical", rank_id="P2P0003", day="2024-06-25") == (
        "https://example.test/history/P2P0003/2024-06-25"
    )
    with pytest.raises(ValueError):
        resolve_url("historical", rank_id="P2P0003", day=None)


def test_env_file_does_not_override_existing_secret(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("TFNSW_API_KEY=file-secret\nTFNSW_AUTH_SCHEME=apikey\n")
    monkeypatch.setenv("TFNSW_API_KEY", "process-secret")
    monkeypatch.delenv("TFNSW_AUTH_SCHEME", raising=False)
    load_env_file(env_file)
    import os
    assert os.environ["TFNSW_API_KEY"] == "process-secret"
    assert os.environ["TFNSW_AUTH_SCHEME"] == "apikey"


def test_passenger_bands_are_never_coerced_to_counts(tmp_path: Path):
    source = tmp_path / "history.json"
    source.write_text(json.dumps(history_payload()), encoding="utf-8")
    frame = normalize_history([source])
    passenger = frame.loc[frame["class"] == "passenger"].iloc[0]
    taxi = frame.loc[frame["class"] == "taxi"].iloc[0]
    assert passenger["new_arrivals_band"] == 2
    assert passenger["new_arrivals_count"] != passenger["new_arrivals_count"]  # NaN
    assert taxi["new_arrivals_count"] == 6
    assert passenger["start_time_sydney"].hour == 9


def test_sydney_silver_reconciles(tmp_path: Path):
    source = tmp_path / "history.json"
    source.write_text(json.dumps(history_payload()), encoding="utf-8")
    output, report = tmp_path / "history.parquet", tmp_path / "quality.json"
    result = build_history_silver([source], output, report)
    assert result["bronze_rows"] == result["silver_rows"] == 3
    assert result["class_counts"] == {"taxi": 1, "passenger": 1, "wat": 1}
    assert all(value == 0 for value in result["quality_counts"].values())
    assert duckdb.connect().execute(
        f"SELECT count(*) FROM read_parquet('{output.as_posix()}')"
    ).fetchone()[0] == 3
