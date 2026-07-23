# Data directory

The full NYC taxi archives and generated datasets are not committed because of their size.

Place the extracted January 2013 source files here:

```text
data/
├── raw/
│   ├── trip_data_1.csv
│   └── trip_fare_1.csv
├── interim/
└── processed/
```

Running `Taxi-NYC-EDA-Part1.ipynb` writes:

```text
data/processed/Training_FeatureEngineering(borough).2_0.csv
```

Running `Taxi-NYC-EDA-Part2.ipynb` also writes:

```text
data/processed/Visualisation.2_0.csv
```

The tested command-line pipeline writes `data/processed/trips_cleaned.csv` by
default. Use `python -m src.nyc_taxi.pipeline --help` to see path and sampling
options.

## Modern TLC data workflow

Official monthly Parquet files are downloaded into partitioned folders below
`data/raw/<trip-type>/year=YYYY/month=MM/`. A local `manifest.json` records each
file's URL, byte size, SHA-256 checksum, and download time.

```bash
python -m src.nyc_taxi.download --year 2024 --months 1 --dry-run
python -m src.nyc_taxi.download --year 2024 --months 1
python -m src.nyc_taxi.warehouse sample --rows 10000
python -m src.nyc_taxi.warehouse aggregate
```

The final command writes a compact zone-by-hour table to
`data/processed/hourly_zone_demand.parquet`. Raw, processed, manifest, and generated
sample files remain excluded from Git.

## Governed Bronze, Silver, and Gold builds

The notebook audit and governance decisions are recorded in
`docs/eda-data-governance-audit.md`. Download the official zone dimension, then
build non-destructive Silver partitions and the product-specific Gold demand table:

```bash
python -m src.nyc_taxi.reference
python -m src.nyc_taxi.governance all
```

Silver retains every Bronze row and adds official zone attributes plus `dq_*`
flags. Each monthly quality report reconciles row counts and records source/output
checksums. Gold demand includes only rows satisfying the demand product contract;
fare-quality failures do not erase valid pickup events.

Download links and execution instructions are provided in the repository README.
