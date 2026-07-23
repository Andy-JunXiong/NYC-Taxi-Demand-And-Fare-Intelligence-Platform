# NYC roadmap 1–5: delivered foundation

## 1. Governed EDA

The EDA now covers monthly and weekday-hour demand, borough and zone concentration, airport demand, weekday/weekend daily intensity, distance-band fares, payment types, and non-destructive quality flags. It reads only checksum-verified inputs declared by Gold lineage.

Current findings include 20.33 million eligible pickups in 2024 H1, 1.56 million JFK/LGA pickups, and a Thursday 18:00 demand peak. The generated tables and charts live in `docs/assets/eda`.

## 2. Forecast baselines

The forecast uses calendar-month splits: training through April, validation in May, and an untouched June test. It compares previous-hour, previous-day, previous-week, Ridge, and histogram gradient boosting baselines.

On June 2024, histogram gradient boosting achieved MAE 3.31, RMSE 10.49, and WAPE 17.65%. The previous-week baseline produced WAPE 23.93%. Airport zones 132 and 138 have the largest absolute errors, so airport demand is the clearest next modeling target.

## 3. Quality release gates

`python -m src.nyc_taxi.quality_gates --periods ...` checks report completeness, row reconciliation, month leakage, unknown pickup zones, duplicate candidates, negative fares, implausible speeds, and demand eligibility. A failed gate returns a non-zero status and prevents the monthly orchestrator from rebuilding Gold.

The 2024 H1 release passes the configured baseline thresholds. Thresholds are explicit policy and should be tightened only after monitoring several new months.

## 4. Incremental monthly pipeline

`python -m src.nyc_taxi.monthly_pipeline --start YYYY-MM --end YYYY-MM` performs idempotent download, Silver processing, quality gating, and Gold publication. Existing raw and governed partitions are skipped unless `--force` is supplied. `--skip-download` supports already staged files.

The command is intentionally bounded to a supplied period and does not scan every historical partition into a release.

## 5. Analysis feature table

The leakage-safe zone-hour feature table includes hour/day/month cycles, weekend and US-holiday indicators, airport-zone identity, lags at 1/2/24/168 hours, and shifted rolling means at 3/6/24 hours. Optional weather CSV input adds hourly temperature and precipitation; missing weather is represented explicitly rather than silently dropping rows.

Expected weather columns are `pickup_hour`, `temperature_c`, and `precipitation_mm`.
