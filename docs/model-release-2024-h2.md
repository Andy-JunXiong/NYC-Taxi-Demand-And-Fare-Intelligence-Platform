# NYC demand model release: 2024 H2

## Decision

**Approved for production.** The candidate passed every release gate over six expanding-window monthly tests from July through December 2024. Training data begins in July 2023; each fold uses only observations available before its test month.

## Rolling backtest

| Test month | Previous-week WAPE | Global model WAPE | Airport global WAPE | Airport specialist WAPE |
|---|---:|---:|---:|---:|
| 2024-07 | 31.27% | 20.05% | 19.17% | 15.47% |
| 2024-08 | 23.20% | 19.35% | 17.91% | 15.08% |
| 2024-09 | 24.28% | 18.58% | 16.92% | 13.93% |
| 2024-10 | 21.07% | 17.67% | 17.30% | 13.60% |
| 2024-11 | 27.03% | 19.08% | 18.64% | 15.34% |
| 2024-12 | 35.17% | 20.13% | 21.37% | 17.96% |

The global model beat the previous-week baseline in all six months. Median relative WAPE improvement was **26.4%**. The airport specialist beat the global model on JFK and LaGuardia in all six months, with a median relative WAPE improvement of **17.7%**.

## Release gates

The release requires at least four folds, an overall win rate of at least 75%, median WAPE improvement of at least 5%, no fold worse than baseline by more than 2%, and airport-specialist wins in at least two-thirds of folds. All conditions passed.

`models/demand_release/production.joblib` contains the global and airport models, feature contract, airport zone IDs, training period, and release decision. A failed future candidate remains as `candidate.joblib` and does not overwrite production.

## Reproduce

```powershell
python -m src.nyc_taxi.model_validation --first-test 2024-07 --max-iter 60
```

The machine-readable fold report is `models/demand_release/rolling_backtest.json`.
