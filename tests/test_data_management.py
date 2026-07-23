import json
from pathlib import Path

import duckdb

from nyc_taxi.datasets import parquet_name, parquet_url, raw_path
from nyc_taxi.download import main as download_main, month_range, parse_month, sha256_file, update_manifest
from nyc_taxi.warehouse import aggregate_hourly_demand, build_sample, discover_parquet


def make_parquet(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute(
        f"""COPY (
            SELECT * FROM (VALUES
              (TIMESTAMP '2024-01-01 10:05:00', TIMESTAMP '2024-01-01 10:20:00', 100, 101, 10.0, 2.0),
              (TIMESTAMP '2024-01-01 10:30:00', TIMESTAMP '2024-01-01 10:40:00', 100, 102, 12.0, 3.0),
              (TIMESTAMP '2024-01-02 11:00:00', TIMESTAMP '2024-01-02 11:15:00', 200, 201, 15.0, 4.0),
              (TIMESTAMP '2002-01-01 11:00:00', TIMESTAMP '2002-01-01 11:15:00', 200, 201, 15.0, 4.0)
            ) AS t(tpep_pickup_datetime, tpep_dropoff_datetime, PULocationID, DOLocationID, fare_amount, trip_distance)
        ) TO '{path.as_posix()}' (FORMAT PARQUET)"""
    )
    connection.close()


def test_dataset_paths_are_predictable(tmp_path):
    assert parquet_name(2024, 1) == "yellow_tripdata_2024-01.parquet"
    assert parquet_url(2024, 1).endswith("/yellow_tripdata_2024-01.parquet")
    assert "year=2024" in raw_path(tmp_path, 2024, 1).as_posix()


def test_cross_year_month_range_and_dry_run(capsys):
    assert month_range(parse_month("2025-11"), parse_month("2026-02")) == [
        (2025, 11), (2025, 12), (2026, 1), (2026, 2)
    ]
    assert download_main(["--start", "2025-11", "--end", "2026-02", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "yellow_tripdata_2025-11.parquet" in output
    assert "yellow_tripdata_2026-02.parquet" in output


def test_manifest_replaces_existing_record(tmp_path):
    source = tmp_path / "file.bin"
    source.write_bytes(b"taxi")
    manifest = tmp_path / "manifest.json"
    record = {"path": "data/raw/file", "sha256": sha256_file(source), "bytes": 4}
    update_manifest(manifest, record)
    update_manifest(manifest, record | {"bytes": 5})
    data = json.loads(manifest.read_text())
    assert len(data["files"]) == 1
    assert data["files"][0]["bytes"] == 5


def test_sample_and_aggregate(tmp_path):
    source = raw_path(tmp_path / "raw", 2024, 1)
    make_parquet(source)
    inputs = discover_parquet(tmp_path / "raw")
    assert inputs == [source]
    assert build_sample(inputs, tmp_path / "sample.parquet", rows=2) == 2
    output = tmp_path / "hourly.parquet"
    assert aggregate_hourly_demand(inputs, output) == 2
    rows = duckdb.connect().execute(
        f"SELECT trip_count FROM read_parquet('{output.as_posix()}') ORDER BY trip_count DESC"
    ).fetchall()
    assert rows == [(2,), (1,)]


def test_partition_month_filters_bad_timestamps(tmp_path):
    invalid = tmp_path / "unknown.parquet"
    make_parquet(invalid)
    import pytest
    from nyc_taxi.warehouse import build_sample
    with pytest.raises(ValueError, match="Cannot infer year and month"):
        build_sample([invalid], tmp_path / "bad.parquet", 1)
