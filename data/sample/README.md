# Sample data

Generate a deterministic sample after downloading one or more official monthly
Yellow Taxi Parquet files:

```bash
python -m src.nyc_taxi.warehouse sample --rows 10000
```

`yellow_taxi_sample.parquet` is the reviewed CI fixture: 10,000 deterministic
records sampled from the governed 2024 H1 official TLC files. It contains the
published trip-record fields, no direct passenger or driver identifiers, and is
explicitly allowed by `.gitignore`. Other generated samples remain ignored.
