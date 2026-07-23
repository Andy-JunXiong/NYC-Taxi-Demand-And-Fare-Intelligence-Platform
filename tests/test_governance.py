import json
from pathlib import Path

import duckdb

from nyc_taxi.download import sha256_file
from nyc_taxi.eda import _lineage_inputs
from nyc_taxi.governance import build_gold_demand, build_silver_partition


def test_eda_uses_only_checksum_verified_lineage_sources(tmp_path: Path):
    gold = tmp_path / "gold.parquet"
    gold.write_bytes(b"gold")
    silver = tmp_path / "silver/year=2024/month=01/trips.parquet"
    silver.parent.mkdir(parents=True)
    silver.write_bytes(b"silver")
    extra = tmp_path / "silver/year=2025/month=01/trips.parquet"
    extra.parent.mkdir(parents=True)
    extra.write_bytes(b"must not be discovered")
    lineage = tmp_path / "lineage.json"
    lineage.write_text(json.dumps({
        "output_sha256": sha256_file(gold),
        "sources": [{"path": str(silver), "sha256": sha256_file(silver)}],
    }), encoding="utf-8")

    sources, periods = _lineage_inputs(lineage, gold)

    assert sources == [silver]
    assert periods == ["2024-01"]


def make_bronze(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute(
        f"""
        COPY (
          SELECT * FROM (VALUES
            (1, TIMESTAMP '2024-01-01 10:00:00', TIMESTAMP '2024-01-01 10:10:00', 1, 2.0, 1, 1, 2, 1, 10.0, 2.0, 0.0, 12.5),
            (1, TIMESTAMP '2024-01-02 11:00:00', TIMESTAMP '2024-01-02 10:00:00', 1, -1.0, 1, 999, 2, 1, -5.0, 0.0, 0.0, -5.0),
            (1, TIMESTAMP '2002-01-01 12:00:00', TIMESTAMP '2002-01-01 12:10:00', 1, 1.0, 1, 1, 2, 1, 5.0, 0.0, 0.0, 5.0)
          ) AS t(VendorID, tpep_pickup_datetime, tpep_dropoff_datetime,
            passenger_count, trip_distance, RatecodeID, PULocationID,
            DOLocationID, payment_type, fare_amount, tip_amount,
            tolls_amount, total_amount)
        ) TO '{path.as_posix()}' (FORMAT PARQUET)
        """
    )
    connection.close()


def test_silver_is_non_destructive_and_gold_is_product_specific(tmp_path: Path):
    bronze = tmp_path / "raw/yellow/year=2024/month=01/yellow_tripdata_2024-01.parquet"
    make_bronze(bronze)
    zones = tmp_path / "zones.csv"
    zones.write_text(
        "LocationID,Borough,Zone,service_zone\n"
        "1,Manhattan,Alpha,Yellow Zone\n"
        "2,Queens,Beta,Boro Zone\n",
        encoding="utf-8",
    )
    silver = tmp_path / "silver/yellow/year=2024/month=01/trips.parquet"
    quality = tmp_path / "quality.json"
    report = build_silver_partition(bronze, zones, silver, quality)
    assert report["counts"]["source_rows"] == 3
    assert report["counts"]["pickup_outside_partition"] == 1
    assert report["counts"]["unknown_pickup_zone"] == 1
    assert report["counts"]["demand_eligible"] == 1
    assert json.loads(quality.read_text())["reconciled"] is True

    gold = tmp_path / "gold.parquet"
    lineage = tmp_path / "lineage.json"
    result = build_gold_demand(tmp_path / "silver", gold, lineage)
    assert result["trips"] == 1
    assert duckdb.connect().execute(
        f"SELECT pickup_borough, trip_count FROM read_parquet('{gold.as_posix()}')"
    ).fetchone() == ("Manhattan", 1)
