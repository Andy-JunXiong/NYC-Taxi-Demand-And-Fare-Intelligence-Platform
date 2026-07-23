# Event-aware demand model release

## Decision

**Approved.** The event-aware candidate passed the expanded release gate after seven expanding-window folds from 2024-07 through 2025-01. Production was replaced atomically only after the second candidate passed every ordinary-day, event, airport, and New Year condition.

## Training data and event calendar

Governed history now spans 2022-01 through 2025-01: 37 monthly partitions and 2,916,955 Gold Zone-hour rows. The deterministic calendar represents New Year, Independence Day, Thanksgiving, and Christmas with event identity, event eve, event overnight, New Year's window, and capped hours-to/hours-since-event features.

The event specialist trains only on major-event windows outside JFK/LGA. High-demand and historical New Year rows receive additional training weight. Airport zones retain their airport specialist, which also receives the calendar features.

## Baselines and results

Each event window is compared with previous week and the same event/hour in the previous year. Overall monthly WAPE remained below its previous-week baseline in all seven folds.

| Test month | Previous-week WAPE | Candidate WAPE | Event candidate | Previous-year event |
|---|---:|---:|---:|---:|
| 2024-07 | 31.27% | 19.47% | 28.02% | 37.92% |
| 2024-08 | 23.20% | 19.08% | — | — |
| 2024-09 | 24.28% | 18.49% | — | — |
| 2024-10 | 21.07% | 17.40% | — | — |
| 2024-11 | 27.03% | 18.82% | 23.83% | 88.66% |
| 2024-12 | 35.17% | 19.19% | 25.49% | 30.28% |
| 2025-01 | 29.18% | 20.89% | 27.54% | 27.07% |

For the 2025 New Year window, candidate WAPE is **33.82%** and high-demand recall is **81.87%**. The first unweighted candidate reached only 78.36% recall and was rejected; the gate was not relaxed.

## Release policy

The model must pass all existing monthly and airport checks plus:

- at least three event folds;
- positive median event WAPE improvement versus previous year;
- no ordinary-day fold degradation beyond 2%;
- New Year WAPE better than previous week;
- New Year high-demand recall of at least 80%.

The accepted artifact contains global, airport, and event models plus its feature contract and release decision. Inference routes event windows to the event specialist, except airport zones, which remain with the airport specialist.

## Current forecast

The previously scored 2025-01-01 forecast and lineage were archived under `data/processed/forecasts/archive`. The new production model published a governed forecast for 2025-02-01, covering 263 zones and 6,312 rows; every publication gate passed.
