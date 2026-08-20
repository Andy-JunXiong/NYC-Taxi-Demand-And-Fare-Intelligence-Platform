# Candidate-v2 recursive loss-day attribution

Date: 2026-08-20
Status: completed descriptive diagnosis
Decision boundary: observational model evidence only

## Executive finding

The 13 candidate-v2 daily losses are concentrated in ordinary, non-airport
demand rather than the airport specialist or Memorial Day event route:

- all 13 losses occurred on or before 2026-05-20, in four clusters; the model
  then recorded 11 consecutive wins from 2026-05-21 through 2026-05-31;
- 11 losses were ordinary weekdays, two were ordinary weekend days, and neither
  of the two Memorial Day event-window days lost;
- across the losing days, the airport specialist produced 2,045 fewer absolute
  errors than the previous-week baseline, while non-airport predictions
  produced 36,902 more; and
- the ten largest zone contributions were all Manhattan non-airport zones, led
  by Upper East Side South, Upper East Side North, Midtown Center, and Midtown
  East.

This localizes the observed weakness to the ordinary global-model path. It does
not establish why that path lost, prove a weekday effect, or identify a safe new
feature. Candidate v2 remains `HOLD`.

## Evidence identity and leakage boundary

The outcome label and candidate errors come from the accepted May 2026
recursive shadow evidence:

- shadow report:
  `data/processed/staging/model-april-cutoff-v2/recursive_shadow.json`, SHA-256
  `c93ca572823e6af413bccf2252cdc8ab12a366669f7709bea29cdf8c1378ed71`;
- candidate model SHA-256:
  `29354b382cd6761c3a307c76d821bb1855354cc87eb3c8f9b020cdf83134e334`;
- hourly governed demand SHA-256:
  `463c141b9bdaad657d580990a108d1142b8ac44fb396bc4f68a6c15cbdaab4b9`;
  and
- taxi-zone lookup SHA-256:
  `1a99e105092230f8620f301edcca7f80d3080642ff404d28ed957d3fa222c8ed`.

For forecast day `D`, every explanatory field in this report is calculated
from deterministic calendar information or demand timestamps strictly earlier
than `D`:

- previous-day demand: `[D-1 day, D)`;
- previous-week same-day demand: `[D-7 days, D-6 days)`;
- prior-seven-day mean and coefficient of variation: `[D-7 days, D)`;
- recent trend: the final three pre-forecast daily totals divided by the
  prior-seven-day mean; and
- airport share: airport demand divided by total demand over `[D-7 days, D)`.

Target-day actuals are used only after the fact to define win/loss and localize
absolute error. They are not treated as predictors. The process therefore
preserves active invariant [`TAXI-MODEL-001`](adr/INVARIANTS.md).

## Pre-forecast comparison

| Median pre-forecast field | 18 wins | 13 losses |
|---|---:|---:|
| Previous-day demand | 140,254 | 132,286 |
| Previous-week same-day demand | 136,662 | 135,716 |
| Prior-seven-day mean demand | 132,383 | 129,817 |
| Prior-seven-day demand CV | 10.4% | 8.7% |
| Recent three days vs prior-seven-day mean | +2.54% | +0.85% |
| Prior-seven-day airport share | 6.23% | 6.24% |

The groups have similar previous-week demand and airport share. Losses occur
with somewhat lower recent demand and lower seven-day variability, but the
sample is too small and temporally clustered to treat either difference as
causal. Among the inspected numeric fields, prior-seven-day variability had the
largest exploratory Spearman association with relative improvement (`rho =
0.463`); this is a hypothesis for later out-of-time evaluation, not a selected
feature or threshold.

## Temporal and calendar pattern

| Period | Losses / days |
|---|---:|
| 2026-05-01 through 2026-05-10 | 8/10 |
| 2026-05-11 through 2026-05-20 | 5/10 |
| 2026-05-21 through 2026-05-31 | 0/11 |

The loss clusters were May 1; May 3-9; May 11-12; and May 18-20. Monday and
Tuesday each lost on three of four occurrences, but their final occurrences
fell after the last loss and won. Date order and weekday are therefore
confounded in this single month.

| Calendar route | Losses / days |
|---|---:|
| Ordinary weekday | 11/20 |
| Ordinary weekend | 2/9 |
| Memorial Day event window | 0/2 |

The event result supports the Memorial Day routing correction but supplies only
two event-window observations. It cannot establish general event performance.

## Losing-day record

Relative degradation is the amount by which candidate WAPE exceeded the
previous-week baseline WAPE.

| Date | Day | Prior-day demand | Prior-7d CV | Recent 3d vs 7d | Relative degradation | Drift passed |
|---|---|---:|---:|---:|---:|---|
| 2026-05-01 | Fri | 140,092 | 12.63% | +0.85% | 14.92% | yes |
| 2026-05-03 | Sun | 135,716 | 9.29% | +8.01% | 8.84% | yes |
| 2026-05-04 | Mon | 121,701 | 8.54% | +2.43% | 29.79% | no |
| 2026-05-05 | Tue | 106,299 | 9.01% | -5.73% | 14.15% | yes |
| 2026-05-06 | Wed | 129,295 | 8.65% | -8.19% | 3.33% | yes |
| 2026-05-07 | Thu | 138,901 | 8.82% | -4.05% | 15.09% | yes |
| 2026-05-08 | Fri | 138,094 | 8.66% | +4.32% | 10.45% | yes |
| 2026-05-09 | Sat | 135,230 | 8.43% | +6.25% | 1.84% | yes |
| 2026-05-11 | Mon | 121,767 | 8.33% | +0.92% | 4.71% | yes |
| 2026-05-12 | Tue | 123,429 | 4.82% | -3.95% | 1.25% | yes |
| 2026-05-18 | Mon | 132,286 | 9.03% | +1.35% | 21.76% | yes |
| 2026-05-19 | Tue | 124,877 | 8.78% | -5.85% | 6.69% | yes |
| 2026-05-20 | Wed | 144,846 | 8.67% | -8.55% | 10.50% | yes |

Twelve of the 13 comparative losses still passed all three absolute drift
checks. Conversely, nine of the 18 baseline wins failed at least one absolute
drift check. This supports the accepted decision to use daily drift pass rate as
advisory evidence rather than as a substitute for comparative release criteria.

## Outcome localization

Outcome localization uses target-day actuals only to identify where error was
observed. It is not pre-forecast explanatory evidence.

| Market | Actual trips | Candidate WAPE | Baseline WAPE | Excess absolute error vs baseline |
|---|---:|---:|---:|---:|
| Airport | 108,271 | 15.90% | 17.79% | -2,045 |
| Non-airport | 1,623,516 | 21.80% | 19.52% | +36,902 |

Non-airport excess dominated every losing day; the airport specialist partly
offset it in ten of the 13 days. The largest zone contributions were:

| Zone | Name | Excess absolute error |
|---:|---|---:|
| 237 | Upper East Side South | 8,511 |
| 236 | Upper East Side North | 5,875 |
| 161 | Midtown Center | 5,428 |
| 162 | Midtown East | 3,651 |
| 79 | East Village | 1,791 |
| 249 | West Village | 1,645 |
| 262 | Yorkville East | 1,643 |
| 230 | Times Sq/Theatre District | 1,607 |
| 140 | Lenox Hill East | 1,276 |
| 234 | Union Sq | 1,077 |

These ten zones contributed 32,504 excess absolute errors, or 93.2% of the net
excess across all losing days. This concentration warrants a Manhattan/global
model hypothesis, but high-volume zones naturally contribute more absolute
error and must not be converted directly into a zone-specific release rule.

The largest clock-hour excesses occurred at horizon/UTC hours 22, 18, 24, 20,
and 19. Because every forecast starts at midnight, clock hour and horizon remain
identical. The result localizes error to later hours on the losing days but does
not prove recursive accumulation.

## Supported and unsupported conclusions

Supported by this sample:

- candidate-v2's remaining comparative weakness is in the ordinary non-airport
  global-model path, concentrated in high-volume Manhattan zones;
- the airport specialist is not the source of aggregate degradation on the 13
  losing days;
- the two Memorial Day event-window days are not among the losses; and
- absolute drift checks and comparative daily wins measure different risks.

Not supported by this sample:

- a causal weekday, demand-level, volatility, Manhattan, or clock-hour effect;
- a claim that error necessarily increases with recursive horizon;
- a weather explanation, because this evaluation path supplies no observed
  weather signal; or
- any new numeric release threshold or feature change.

## Next evidence boundary

Before evaluating another candidate, pre-register multiple disjoint
out-of-time periods and staggered forecast origins. The design should preserve
the accepted daily win and worst-day roles, report drift by component, separate
clock hour from horizon, and test the Manhattan/global-model hypothesis without
reusing May 2026 as both feature-discovery and release evidence.

No part of this report authorizes a core-file edit, model training, promotion,
publication, deployment, or scheduling action.
