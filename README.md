# NYC Taxi Demand & Fare Intelligence

An end-to-end analysis of the **2013 New York City yellow taxi trip dataset**. The project turns raw trip and fare records into operational insights for drivers and fleet owners, then compares regression models for fare and tip prediction.

> **Project status:** portfolio/archival analysis. The notebooks contain saved outputs, so the results can be reviewed directly on GitHub. The repository now uses relative data paths and environment-based credentials; re-running still requires downloading the large source archives.

## Results at a glance

| Business outcome | Result from the notebooks |
| --- | --- |
| Demand hotspot | Manhattan, with additional concentrations near JFK and LaGuardia |
| Peak trip demand | Evening commute, around 6 PM in the analyzed sample |
| Best fare model | Tuned Random Forest, test RMSE approximately **$0.899** |
| Best tip model | Tuned Random Forest, test RMSE approximately **$1.215** |
| Weekday fleet allocation | **6 day-shift / 4 night-shift taxis** |
| Weekend fleet allocation | **4 day-shift / 6 night-shift taxis** |

The model scores are reproduced from the saved notebook outputs. Because the original workflow uses a random split and post-trip features, they should be read as retrospective model results—not as evidence of live, pre-trip forecasting performance.

## What this project covers

The analysis addresses ten business questions:

1. When and where is taxi demand highest?
2. How are passenger count, payment type, fares, and tips distributed?
3. How do trip duration, distance, and fare relate?
4. Can drivers be segmented by working hours and daily income?
5. Which features have the greatest influence on fares and tips?
6. How accurately can fare and tip amounts be predicted?
7. How could an individual driver maximize daily earnings?
8. How could a 10-taxi fleet allocate vehicles to maximize earnings?
9. Which data-quality issues affect the analysis?
10. What are the limitations of the selected model, and which alternatives are worth exploring?

## Analysis workflow

```text
Raw trip records + raw fare records
                  │
                  ▼
      validation and data cleaning
                  │
                  ▼
 temporal, geographic, and earnings features
                  │
                  ▼
 borough/airport analysis and driver segmentation
                  │
                  ▼
 fare and tip models + operating recommendations
```

The notebooks cover:

- validation of passenger counts, rate codes, monetary fields, timestamps, trip distance, duration, speed, and coordinates;
- removal of invalid and extreme observations using geographic and domain-based rules;
- temporal features such as hour, weekday, date, and day/night shift;
- geographic features for NYC boroughs, Lower Manhattan, and airport trips;
- earnings-per-minute and earnings-per-mile metrics;
- K-means segmentation of drivers using average daily income and hours worked;
- comparison of a mean baseline, Linear Regression, Lasso, Ridge, and Random Forest regressors;
- fleet allocation recommendations for weekdays and weekends.

## Key findings

- **Demand:** Manhattan is the dominant pickup area, with additional concentrations around JFK and LaGuardia. Demand rises after the early-morning low and reaches its daily peak around the evening commute.
- **Earning efficiency:** the notebooks find the highest earnings per minute during late-night and early-morning hours, while daytime traffic reduces earning efficiency.
- **Driver behavior:** hours worked and daily income are positively related; a six-cluster K-means solution is used to describe driver groups.
- **Fare prediction:** Random Forest performs best among the tested models. The tuned model reports a test RMSE of approximately **0.899**, with trip distance and trip duration as the leading predictors.
- **Tip prediction:** Random Forest also has the lowest test error for tips, but the improvement over the baseline is modest. The tuned model reports an RMSE of approximately **1.215**, and fare amount is its most important feature.
- **Fleet strategy:** the analysis recommends a **6 day / 4 night** taxi split on weekdays and a **4 day / 6 night** split on weekends, with location choices guided by pickup demand and earning efficiency.

These findings are exploratory and are specific to the sampled 2013 data and the cleaning rules used in the notebooks. They should not be treated as current NYC operating recommendations.

## Repository contents

| File | Purpose |
| --- | --- |
| [`Taxi-NYC-EDA-Part1.ipynb`](Taxi-NYC-EDA-Part1.ipynb) | Loads and merges raw data, audits data quality, removes outliers, and engineers temporal, geographic, airport, and earnings features. |
| [`Taxi-NYC-EDA-Part2.ipynb`](Taxi-NYC-EDA-Part2.ipynb) | Adds borough and Lower Manhattan analysis and explores driver shift behavior. |
| [`Taxi-NYC-Question-1-To-6.ipynb`](Taxi-NYC-Question-1-To-6.ipynb) | Answers demand and distribution questions, clusters drivers, and builds fare/tip prediction models. |
| [`Taxi-NYC-Question-7.ipynb`](Taxi-NYC-Question-7.ipynb) | Develops an earning strategy for an individual taxi driver. |
| [`Taxi-NYC-Question-8-To-10.ipynb`](Taxi-NYC-Question-8-To-10.ipynb) | Proposes a 10-taxi fleet strategy and discusses data and model limitations. |
| [`Taxi.pptx`](Taxi.pptx) | Presentation summarizing the analysis and recommendations. |
| [`data/README.md`](data/README.md) | Documents the expected local data layout and generated artifacts. |
| [`requirements.txt`](requirements.txt) | Lists the Python packages required by the notebooks. |

## Data

The project uses NYC taxi trip and fare archives hosted by the Internet Archive:

- [Trip data archive (`trip_data.7z`)](https://archive.org/download/nycTaxiTripData2013/trip_data.7z)
- [Fare data archive (`trip_fare.7z`)](https://archive.org/download/nycTaxiTripData2013/trip_fare.7z)
- [Dataset collection page](https://archive.org/details/nycTaxiTripData2013)

The archives and generated CSV files are intentionally not stored in this repository. They are large, and the source data may be subject to external terms of use. Review those terms before redistributing it.

The analysis reads `data/raw/trip_data_1.csv` and `data/raw/trip_fare_1.csv`, merges them, and writes `data/processed/Training_FeatureEngineering(borough).2_0.csv`. The later notebooks depend on that generated file. See [`data/README.md`](data/README.md) for the complete layout.

## Running the notebooks

## Reproducible preprocessing pipeline

The reusable cleaning and feature-engineering code lives in `src/nyc_taxi` and can
be run independently of Jupyter. It validates the two source files, merges them on
shared trip identifiers, removes invalid records, and writes a feature-enriched CSV:

```bash
python -m src.nyc_taxi.pipeline
```

For a quick smoke test on a large local archive:

```bash
python -m src.nyc_taxi.pipeline --nrows 10000
```

The default output is `data/processed/trips_cleaned.csv`. Custom input and output
paths are available through `--trips`, `--fares`, and `--output`. Run the automated
tests with `python -m pytest -q` after installing `requirements-dev.txt`.

The historical notebooks remain unchanged so their saved analysis can still be
reviewed. New development should use the tested modules rather than duplicating
cleaning logic in additional notebooks.

### Large-data workflow

Current NYC TLC trip records can be handled without committing or loading an
entire year into memory. Download only explicitly selected months, then use DuckDB
to create a small deterministic sample or an hourly taxi-zone demand table:

```bash
python -m src.nyc_taxi.download --year 2024 --months 1 --dry-run
python -m src.nyc_taxi.download --year 2024 --months 1
python -m src.nyc_taxi.download --start 2025-06 --end 2026-05
python -m src.nyc_taxi.warehouse sample --rows 10000
python -m src.nyc_taxi.warehouse aggregate
```

Downloads are stored by trip type, year, and month under `data/raw/`. The downloader
uses atomic temporary files, retries failed transfers, skips existing files, and
records SHA-256 checksums in `data/raw/manifest.json`. Raw and generated datasets
remain ignored by Git; CI uses synthetic test fixtures instead.

The monthly Parquet URLs and schemas come from the official
[NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
catalog. Because schemas can vary between years, the aggregation command uses
name-based schema alignment.

### Demand forecasting MVP

After aggregating at least three calendar months, train and evaluate the hourly
zone-demand model with a strict chronological split:

```bash
python -m src.nyc_taxi.forecast
```

The feature table completes missing zone-hour combinations with zero demand and
uses lagged demand at 1, 2, 24, and 168 hours plus leakage-safe rolling averages.
The last month is held out for testing and the preceding month for validation.
Metrics include MAE, RMSE, WAPE, and high-demand precision/recall, compared with
previous-hour, previous-day, and previous-week baselines. Model artifacts and test
predictions are written below `models/demand_forecast/` and ignored by Git.

The first six-month experiment and its holdout results are documented in
[`docs/demand-forecast-mvp.md`](docs/demand-forecast-mvp.md).

### Data governance

The two historical EDA notebooks have been audited before migrating their rules.
See [`docs/eda-data-governance-audit.md`](docs/eda-data-governance-audit.md) for
cell-level findings, separate legacy/modern contracts, quality dimensions, product
eligibility rules, and release gates. Governed modern builds use:

```bash
python -m src.nyc_taxi.reference
python -m src.nyc_taxi.governance all
python -m src.nyc_taxi.governance all --start 2025-06 --end 2026-05
```

This produces immutable-checksummed Bronze lineage, row-preserving Silver data
with quality flags, monthly quality reports, and a product-specific Gold demand
table based on the official Taxi Zone dimension.

The first governed production run is summarized in
[`docs/data-quality-baseline-2024-h1.md`](docs/data-quality-baseline-2024-h1.md).

Run the reproducible governed EDA with:

```bash
python -m src.nyc_taxi.eda
```

The implemented NYC roadmap (EDA, forecast baselines, release gates, incremental
processing, and leakage-safe features) is documented in
[`docs/nyc-roadmap-1-to-5-delivery.md`](docs/nyc-roadmap-1-to-5-delivery.md).

Run a bounded monthly release with:

```bash
python -m src.nyc_taxi.monthly_pipeline --start 2024-01 --end 2024-06 --skip-download
```

Run expanding-window backtests, train the airport specialist, and apply model
release gates with:

```bash
python -m src.nyc_taxi.model_validation --first-test 2024-07 --max-iter 60
```

The accepted 2024 H2 release is documented in
[`docs/model-release-2024-h2.md`](docs/model-release-2024-h2.md).

Publish the governed next-24-hour forecast and monitor it after actuals arrive:

```bash
python -m src.nyc_taxi.prediction
python -m src.nyc_taxi.monitoring
```

Operational behavior and release gates are documented in
[`docs/forecast-operations.md`](docs/forecast-operations.md).

The first real forecast-to-actual closure, including the failed New Year's Day
drift gate, is documented in
[`docs/forecast-closure-2025-01-01.md`](docs/forecast-closure-2025-01-01.md).

The subsequent event-calendar expansion, specialist model, event baselines, and
approved replacement are documented in
[`docs/event-model-release-2025-01.md`](docs/event-model-release-2025-01.md).

Audited operation commands, automatic forecast archives, failure recovery,
scheduling, and the small-data CI workflow are documented in
[`docs/production-operations-runbook.md`](docs/production-operations-runbook.md).

Repository-native AI/ML governance for the hourly zone-demand forecast is
configured under `governance/` and `evaluation/`. The dated human decisions and
environment work still outstanding are tracked in
[`docs/governance-todo.md`](docs/governance-todo.md).

### Sydney localisation

The platform now includes a contract-first TfNSW Taxi Rank adapter. Sydney history
has a 15-minute rank-and-class grain: taxi and wheelchair-accessible taxi arrivals
are numeric, while passenger demand is an ordinal Low/Medium/High band. The adapter
therefore preserves these as different measures instead of treating them as NYC-like
trip counts.

Setup, source limitations, credentials, and commands are documented in
[`docs/sydney-localisation.md`](docs/sydney-localisation.md).

### 1. Create an environment

The notebooks were originally written against an older Python data-science stack. A practical starting environment is:

```bash
python -m venv .venv
```

Activate it, then install the declared dependencies:

```bash
python -m pip install -r requirements.txt
```

The requirements use bounded version ranges rather than a fully locked environment. Exact output may still vary between supported package versions.

### 2. Download and extract the data

Download both archives, extract the first trip and fare CSVs, and place them in a local data directory. For example:

```text
data/
└── raw/
    ├── trip_data_1.csv
    └── trip_fare_1.csv
```

### 3. Configure maps (optional)

The notebooks can be reviewed without a Google Maps key. To execute the interactive `gmaps` cells, copy `.env.example` to `.env`, create a restricted Google Maps key, and expose `GOOGLE_MAPS_API_KEY` in the environment from which Jupyter is started.

Never commit the populated `.env` file.

### 4. Run in this order

1. `Taxi-NYC-EDA-Part1.ipynb`
2. `Taxi-NYC-EDA-Part2.ipynb`
3. `Taxi-NYC-Question-1-To-6.ipynb`
4. `Taxi-NYC-Question-7.ipynb`
5. `Taxi-NYC-Question-8-To-10.ipynb`

Start Jupyter with:

```bash
jupyter notebook
```

The full dataset is large. Expect substantial memory use and long execution times for loading, mapping, grid search, and Random Forest training.

## Reproducibility and security notes

- Historical API keys have been removed from the current notebooks and replaced with `GOOGLE_MAPS_API_KEY`. Because secrets may remain in Git history, the old keys must still be treated as compromised and revoked at the provider.
- Static outputs can be inspected without configuring Google Maps. Interactive maps may require additional Jupyter widget setup.
- Legacy `plotly.plotly` imports have been replaced with Plotly's offline interface. Some older chart calls may still require adjustment on current releases.
- Deprecated Random Forest `max_features='auto'` values have been replaced with `1.0`, the equivalent regressor behavior in current scikit-learn.
- `Taxi-NYC-Question-8-To-10.ipynb` creates a local Spark context, although most of the analysis is performed with pandas.
- The repository now includes dependency ranges and portable data paths, but it does not yet include automated tests or a fully locked environment.

## Methodological limitations

- The data contains invalid coordinates, implausible passenger counts, zero-distance/zero-duration trips, and extreme fare, speed, and distance values.
- Rule-based outlier removal can discard legitimate rare trips and influence model performance.
- The train/test split is random rather than time-based, so it does not measure performance under temporal drift.
- Taxi demand, fares, regulations, traffic, and passenger behavior have changed since 2013.
- RMSE alone does not reveal performance differences by borough, time period, airport trip, or fare range.
- The earning recommendations do not fully model idle time, fuel, tolls, maintenance, driver availability, repositioning costs, or competition between vehicles.

## Suggested next steps

- Add a fully locked environment and a small, legally redistributable sample dataset for reproducible execution.
- Convert repeated notebook logic into tested Python modules and a command-line pipeline.
- Replace the legacy `gmaps` widget integration with a maintained map visualization approach.
- Use time-aware validation and compare gradient boosting models such as XGBoost, LightGBM, or HistGradientBoosting.
- Evaluate MAE and segment-level errors alongside RMSE.
- Rebuild the analysis on current NYC TLC trip records and taxi-zone identifiers.

## License

No license file is currently included. Unless a license is added, the repository's code and written material remain under the default copyright terms. The source dataset is governed separately by its provider's terms.
