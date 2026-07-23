from pathlib import Path

import duckdb

from nyc_taxi.governance import build_gold_demand, build_silver_partition, load_contract, validate_schema
from nyc_taxi.quality_gates import run_gates


def test_reviewed_sample_runs_bronze_silver_gate_gold(tmp_path: Path):
    reviewed = Path("data/sample/yellow_taxi_sample.parquet")
    assert reviewed.is_file()
    validate_schema(reviewed, load_contract())

    bronze = tmp_path / "raw/yellow/year=2024/month=01/yellow_tripdata_2024-01.parquet"
    bronze.parent.mkdir(parents=True)
    zones = tmp_path / "taxi_zone_lookup.csv"
    connection = duckdb.connect()
    connection.execute(
        f"COPY (SELECT * EXCLUDE (month, year) FROM read_parquet('{reviewed.resolve().as_posix()}') "
        "WHERE tpep_pickup_datetime >= TIMESTAMP '2024-01-01' "
        "AND tpep_pickup_datetime < TIMESTAMP '2024-02-01') "
        f"TO '{bronze.as_posix()}' (FORMAT PARQUET)"
    )
    ids = connection.execute(
        f"SELECT DISTINCT id FROM (SELECT PULocationID id FROM read_parquet('{bronze.as_posix()}') "
        f"UNION SELECT DOLocationID FROM read_parquet('{bronze.as_posix()}')) WHERE id IS NOT NULL ORDER BY id"
    ).fetchall()
    connection.close()
    zones.write_text(
        "LocationID,Borough,Zone,service_zone\n"
        + "".join(f"{int(row[0])},Sample,Zone {int(row[0])},Sample\n" for row in ids),
        encoding="utf-8",
    )
    silver = tmp_path / "silver/yellow/year=2024/month=01/trips.parquet"
    quality_root = tmp_path / "quality"
    build_silver_partition(bronze, zones, silver, quality_root / "yellow_2024-01.json")
    gate = run_gates(quality_root, ["2024-01"], tmp_path / "gate.json", product="demand")
    assert gate["passed"]
    lineage = build_gold_demand(
        tmp_path / "silver", tmp_path / "gold.parquet", tmp_path / "lineage.json"
    )
    assert lineage["rows"] > 0
    assert lineage["trips"] > 0
