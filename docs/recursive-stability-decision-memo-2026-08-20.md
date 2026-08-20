# Daily 24-hour recursive stability decision memo

Date: 2026-08-20
Status: metric roles accepted by maintainer; numeric gates not defined
Decision boundary: model-release evidence only

## Executive recommendation

Treat **daily win rate** and **worst-day relative degradation** as proposed
release criteria, treat **daily drift pass rate** as advisory release evidence,
and keep the current **horizon profile** diagnostic-only.

This recommendation assigns roles to the evidence but intentionally sets no new
numeric release threshold. The available recursive sample is one month, and the
current horizon field is perfectly aligned with UTC clock hour. Selecting a
cutoff from this sample or treating its horizon profile as pure recursive decay
would overfit the evidence.

Candidate v2 remains `HOLD`. This memo does not change the existing release
gate, approve a model, authorize promotion or publication, or modify a
production artifact.

## Maintainer disposition

On 2026-08-20, the authenticated maintainer accepted all four proposed evidence
roles:

| Evidence | Accepted role |
|---|---|
| Daily win rate vs previous week | Proposed release criterion |
| Worst-day relative degradation | Proposed release criterion |
| Daily drift pass rate | Advisory evidence |
| Current horizon profile | Diagnostic-only evidence |

Acceptance records the role of each metric. It does not define a numeric gate,
authorize a core-file change, or approve candidate v2.

## Evidence boundary

The reviewed evidence is the May 2026 out-of-time daily recursive shadow for
candidate v2. Each day forecasts 24 hours from observations available before
that day and feeds predictions back only inside that forecast. The evaluator is
observational-only and records promotion as `not_permitted`.

The durable summary is in
[`development-log/2026-08-09.md`](development-log/2026-08-09.md). The detailed
local report reviewed for this memo is ignored staging evidence at
`data/processed/staging/model-april-cutoff-v2/recursive_shadow.json`, with:

- report SHA-256
  `c93ca572823e6af413bccf2252cdc8ab12a366669f7709bea29cdf8c1378ed71`;
- model SHA-256
  `29354b382cd6761c3a307c76d821bb1855354cc87eb3c8f9b020cdf83134e334`;
- evaluation period 2026-05-01 through 2026-05-31; and
- 31 daily forecasts over 263 zones and 24 hours per day.

The report is local evidence rather than a committed release artifact. Its
derived facts are recorded below so that reviewers can distinguish the durable
decision rationale from the availability of ignored staging files.

The evaluation design is consistent with active invariant
[`TAXI-MODEL-001`](adr/INVARIANTS.md): training precedes the shadow period and
forecast features do not use observations at or after each forecast origin.
The existing deterministic release checks remain those described in
[`model-release-2024-h2.md`](model-release-2024-h2.md).

## Observed result

| Measure | Candidate v2 result | Interpretation |
|---|---:|---|
| Combined WAPE | 22.59% | Better than the previous-week baseline's 25.76% |
| Combined relative WAPE improvement | 12.32% | Aggregate improvement, not evidence of daily consistency |
| Combined bias | -0.35% | Aggregate bias is near zero |
| Daily baseline wins | 18/31 (58.1%) | Thirteen daily losses remain |
| Worst daily relative degradation | 29.79% worse | 2026-05-04: 25.21% candidate WAPE vs 19.43% baseline WAPE |
| Daily drift passes | 21/31 (67.7%) | Ten days failed at least one existing absolute drift check |
| Combined drift result | Passed | Demonstrates that an aggregate pass can mask daily failures |
| Horizon-hour baseline wins | 24/24 | Every aggregated horizon hour beat its corresponding previous-week baseline |
| Horizon-hour candidate WAPE range | 18.24% to 44.27% | Variation is not monotonic and is confounded with clock hour |

The daily drift checks reused by the shadow are WAPE below 25%, absolute bias
below 10%, and high-demand recall at least 90%. They answer an absolute
operational-quality question. Daily win rate and worst-day degradation answer a
different, comparative question: whether replacing the previous-week baseline
is consistently beneficial. A day may therefore beat the baseline and still
fail an absolute drift check, or lose to the baseline while passing all drift
checks.

## Metric classification

| Evidence | Proposed role | Rationale | Boundary before enforcement |
|---|---|---|---|
| Daily win rate vs previous week | **Proposed release criterion** | It measures how consistently a candidate adds value under the product's 24-hour recursive inference condition and complements aggregate WAPE. | Predeclare a threshold and evaluation windows before scoring another candidate; do not derive the threshold from May 2026. |
| Worst-day relative degradation | **Proposed release criterion** | It limits tail harm hidden by aggregate improvement and mirrors the intent of the existing worst-fold release protection. | Review the statistic together with absolute candidate and baseline WAPE and demand volume; calibrate a cap on multiple out-of-time windows. |
| Daily drift pass rate | **Advisory evidence** | It estimates how often a released model would cross existing monitoring boundaries, but mixes three absolute checks and does not measure improvement over the baseline. | Report the pass rate and each failed check separately. Do not create a release cutoff until maintainers decide how monitoring failures should affect release. |
| Horizon degradation/profile | **Diagnostic-only evidence** | All shadow forecasts start at midnight, so horizon 1 is always 00:00, horizon 2 is always 01:00, and so on. Clock-hour demand difficulty cannot be separated from recursive error accumulation. | Use staggered forecast origins or an equivalent clock-hour control before proposing a horizon release statistic or threshold. |

“Proposed release criterion” means the metric belongs in a future deterministic
release decision after its semantics, sample design, and threshold are approved.
It is not a gate today.

## Tradeoffs

- Daily win rate protects consistency but weights low- and high-volume days
  equally. It must be reviewed alongside aggregate demand-weighted WAPE.
- Worst-day degradation protects against severe harm but is sensitive to one
  unusual day and to a strong or low-error baseline. Absolute WAPE and demand
  volume keep the relative statistic interpretable.
- Daily drift pass rate maps directly to existing operational alerts, but a
  composite pass rate hides whether misses come from accuracy, bias, or
  high-demand recall.
- Horizon evidence is operationally important, but the present midnight-origin
  design cannot identify recursion as the cause of the observed hour-to-hour
  profile.
- Memorial Day improvement is useful event evidence, but it must not dominate a
  general release decision: v2 improved Memorial Day WAPE from 54.31% to 30.77%
  while its daily win count fell from 19 to 18.

## Evidence required before numeric gates

1. Freeze the candidate and evaluation plan before scoring multiple disjoint,
   out-of-time periods that cover ordinary, weekend, holiday, and event regimes.
2. Report aggregate WAPE, daily win distribution, worst-day relative and
   absolute performance, daily drift failures by check, and relevant demand
   denominators from the same forecast runs.
3. Diagnose losing days using only information available before each forecast;
   do not add an explanatory feature discovered from the held-out outcome and
   then reuse the same period as release evidence.
4. Separate horizon from clock hour through staggered forecast origins or a
   reviewed equivalent before defining horizon stability.
5. Review the proposed sample design and threshold-selection method before
   training or evaluating the next release candidate.

## Remaining decisions

The evaluation sample, staggered-origin design, and threshold-selection method
still require review before any numeric gate is implemented. Candidate v2
remains unpromoted and unpublished, and the existing deterministic release gate
remains unchanged.
