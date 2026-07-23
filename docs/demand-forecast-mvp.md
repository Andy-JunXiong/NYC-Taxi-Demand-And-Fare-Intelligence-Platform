# Hourly zone-demand forecast MVP

## Scope

This experiment predicts the number of Yellow Taxi pickups in each NYC Taxi Zone
for the next hour. It uses official January-June 2024 monthly Parquet files and a
complete zone-hour grid, including hours with zero observed pickups.

The source data contained 20,331,944 valid January-June pickups after enforcing
the calendar-month boundary represented by each source filename. The compact input
contains 509,668 observed zone-hour groups; feature generation expands this into a
complete grid before constructing historical features.

## Evaluation design

| Partition | Period | Feature rows |
| --- | --- | ---: |
| Training | January-April 2024 | 716,832 |
| Validation | May 2024 | 194,928 |
| Test | June 2024 | 188,640 |

No random split is used. Features include calendar values, cyclic hour/day
encodings, demand lags at 1, 2, 24, and 168 hours, and rolling means over the prior
3, 6, and 24 hours. Rolling windows are shifted before calculation so the target
hour is never included.

## June 2024 holdout results

| Model | MAE | RMSE | WAPE | High-demand precision | High-demand recall |
| --- | ---: | ---: | ---: | ---: | ---: |
| Previous hour | 4.965 | 15.701 | 26.46% | 91.39% | 91.50% |
| Previous day | 5.800 | 20.794 | 30.92% | 90.77% | 91.42% |
| Previous week | 4.490 | 15.047 | 23.93% | 94.26% | 92.49% |
| HistGradientBoosting | **3.350** | **10.683** | **17.86%** | **95.51%** | **95.35%** |

High demand is defined using the training-set 90th percentile: 50 pickups per zone
per hour. Model selection is performed on May; June remains untouched until final
evaluation.

## Interpretation and limitations

- The model improves materially over all three seasonal baselines, including the
  previous-week baseline.
- This is a one-hour-ahead evaluation: lag features use demand that would be known
  at prediction time. It is not evidence of accurate recursive multi-hour forecasts.
- Taxi Zone ID is currently represented numerically. A future model should use
  native categorical handling, spatial embeddings, or geographic attributes.
- Six months do not cover annual seasonality, major concept drift, or unusual
  weather and event regimes.
- Weather, holidays, congestion, nearby-zone demand, and event calendars are not
  yet included.
- Aggregate accuracy can hide weak performance in low-volume zones. The generated
  `metrics.json` therefore also reports errors by hour and the ten worst zones by
  MAE.

## Reproduction

```bash
python -m src.nyc_taxi.download --year 2024 --months 1 2 3 4 5 6
python -m src.nyc_taxi.warehouse aggregate
python -m src.nyc_taxi.forecast
```

Generated models, predictions, raw files, and processed data are intentionally
excluded from Git.
