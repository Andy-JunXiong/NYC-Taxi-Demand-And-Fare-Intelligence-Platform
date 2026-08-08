# NYC Taxi Demand & Fare Intelligence Platform

A reproducible urban-mobility data platform that turns governed NYC TLC trip
records into auditable demand analytics, leakage-safe model evaluation, and
bounded next-day zone-hour forecasts.

[![AgentGov](https://github.com/Andy-JunXiong/NYC-Taxi-Demand-And-Fare-Intelligence-Platform/actions/workflows/agentgov.yml/badge.svg)](https://github.com/Andy-JunXiong/NYC-Taxi-Demand-And-Fare-Intelligence-Platform/actions/workflows/agentgov.yml)

[![NYC Taxi Intelligence — from 100M+ records to a governed decision system](showcase/public/og.png)](https://andy-junxiong.github.io/NYC-Taxi-Demand-And-Fare-Intelligence-Platform/)

<p align="center">
  <a href="https://andy-junxiong.github.io/NYC-Taxi-Demand-And-Fare-Intelligence-Platform/"><strong>Explore the interactive data story →</strong></a>
  &nbsp;·&nbsp;
  <a href="docs/production-operations-runbook.md">Operations runbook</a>
  &nbsp;·&nbsp;
  <a href="docs/eda-data-governance-audit.md">Governance audit</a>
</p>

> The showcase is a portfolio narrative over governed 2022–2025 evidence. It
> supports planning and technical review; it is not live dispatch advice or a
> claim about all NYC mobility.

## Results at a glance

| Product evidence | Result |
| --- | ---: |
| Governed source coverage | **37 monthly partitions** |
| Source scale | **100M+ public trip records** |
| Gold demand product | **2.92M zone-hour rows** |
| Forecast output | **6,312 zone-hour predictions** |
| Expanding-window evaluation | Candidate beat the previous-week baseline in **7/7 folds** |
| Release validation | **32/32 checks passed** |

## What the platform does

```text
Official TLC Parquet
        ↓
Immutable Bronze + checksums
        ↓
Observable Silver + quality flags
        ↓
Governed Gold zone-hour demand
        ↓
Global / airport / event-aware models
        ↓
Approval → publication → monitoring → archive
```

- Downloads bounded monthly inputs with resumable transfers and checksum lineage.
- Preserves source rows while separating quality flags from product eligibility.
- Produces reproducible EDA and governed zone-hour demand tables.
- Evaluates forecasts with chronological expanding windows rather than random splits.
- Routes airport and known-event demand through specialist models.
- Protects publication with approval, quality, model, and monitoring gates.
- Preserves failed releases and last-known-good artifacts for audit and recovery.

## Decision boundary

The forecast supports next-day fleet-capacity planning and analyst review at the
Taxi Zone × hour level. It does not assign individual vehicles, guarantee
revenue, infer causal demand drivers, or represent rideshare, transit, walking,
cycling, and every NYC traveller.

## Repository map

| Path | Purpose |
| --- | --- |
| [`src/nyc_taxi/`](src/nyc_taxi/) | NYC ingestion, governance, forecasting, release, and monitoring workflows |
| [`src/sydney_taxi/`](src/sydney_taxi/) | Contract-first TfNSW Taxi Rank localisation |
| [`contracts/`](contracts/) | Governed data and publication contracts |
| [`docs/`](docs/) | Architecture evidence, model releases, audits, and operational guidance |
| [`showcase/`](showcase/) | Interactive portfolio case study and social preview |
| [`tests/`](tests/) | Functional, policy, release-gate, and recovery tests |
| Historical notebooks | Preserved 2013 exploratory evidence; not production entry points |

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

This produces a candidate; promotion additionally requires a named human
approval record bound to its SHA-256. The accepted 2024 H2 release is documented in
[`docs/model-release-2024-h2.md`](docs/model-release-2024-h2.md).

Publish the governed next-24-hour forecast and monitor it after actuals arrive:

```bash
python -m src.nyc_taxi.prediction --approval-file <forecast-approval.json>
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
[`docs/governance-todo.md`](docs/governance-todo.md). The
[2026-08-02 development record](docs/development-log/2026-08-02.md) separates
today's completed work from external operations, and the
[remaining development plan](docs/development-plan.md) orders the next slices.

### AgentGov governance visibility

AgentGov turns those repository files into an executable, review-visible contract:

- [governance/capabilities/nyc-hourly-zone-demand-forecast.json](governance/capabilities/nyc-hourly-zone-demand-forecast.json) declares the governed capability, owner, risk, callers, and evidence.
- [governance/controls/nyc-hourly-zone-demand-forecast.json](governance/controls/nyc-hourly-zone-demand-forecast.json) maps applicable controls and their evidence.
- [evaluation/](evaluation/) holds evaluation readiness and reviewed evidence rather than runtime model output.
- [.github/workflows/agentgov.yml](.github/workflows/agentgov.yml) runs the published AgentGov release on every pull request and push, writes the Markdown result to the GitHub Actions job summary, and uploads JSON, Markdown, and update-state artifacts.

Run the same deterministic repository validation locally with:

```powershell
agentgov check repository .
agentgov report repository . --format markdown --output agentgov-report.md
```

With the workflow present, broken governance references, invalid contracts, and
readiness regressions become visible during code review instead of depending on a
maintainer remembering a manual command. Advisory findings remain advisory, and
AgentGov does not approve evidence, merge changes, release, or deploy the platform.

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
- The repository now includes dependency ranges and portable data paths, but it does not yet include a fully locked environment.

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
