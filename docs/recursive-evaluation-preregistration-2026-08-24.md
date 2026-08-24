# Recursive evaluation pre-registration

Date frozen: 2026-08-24
Status: proposed for maintainer review; no evaluation authorized or run
Decision boundary: observational model-release evidence only

## Purpose and non-goals

This specification freezes the next confirmatory evaluation design before its
outcomes are available. It tests whether candidate v2's daily recursive result
generalizes beyond the May 2026 design sample and removes the perfect alignment
between recursive horizon and UTC clock hour.

The specification does not define a numeric release threshold, change the
existing release gate, authorize model training, approve candidate v2, or
authorize promotion, forecast publication, deployment, or scheduling. May 2026
remains hypothesis-forming evidence and will not be pooled into the
confirmatory results.

## Frozen candidate and evidence boundary

The only eligible candidate is the existing April-cutoff candidate v2 with:

- model SHA-256
  `29354b382cd6761c3a307c76d821bb1855354cc87eb3c8f9b020cdf83134e334`;
- training data ending no later than 2026-04-30; and
- the feature, airport-zone, event-calendar, and model-routing semantics stored
  in that exact artifact.

A missing artifact or any digest mismatch stops the evaluation. Rebuilding a
semantically similar model does not make it eligible. The governed input must
name every evaluated source partition and its digest, pass the existing data
quality gates, and include at least 168 hours before every origin, the full
24-hour target, and the previous-week baseline hours. Input validation may
inspect schema, lineage, timestamps, row coverage, and digests, but it must not
summarize target-period demand or model outcomes before the design is frozen.

The currently governed Gold lineage ends at 2026-05. Later partitions must be
acquired and governed through the existing data workflow under separate
authority; this document does not authorize that operation.

## Pre-selected out-of-time blocks

The four blocks were selected from the calendar and candidate training cutoff,
without inspecting their demand or forecast outcomes:

| Block | Origin dates, inclusive | Origins | Pre-selected coverage role |
|---|---|---:|---|
| A | 2026-06-01 through 2026-06-24 | 24 | ordinary weekdays and weekends; no configured major-event route |
| B | 2026-06-29 through 2026-07-22 | 24 | ordinary days, weekends, and the Independence Day route |
| C | 2026-11-09 through 2026-12-02 | 24 | ordinary days, weekends, and the Thanksgiving route |
| D | 2026-12-15 through 2027-01-07 | 24 | ordinary days, weekends, Christmas, and the New Year route |

The blocks do not overlap and contribute 96 forecast-origin units. Calendar
labels describe deterministic feature coverage, not expected performance. A
block is not silently replaced because data are surprising, incomplete, or
unfavorable. A source-integrity problem pauses that block until corrected by
the governed workflow and is recorded as a deviation.

## Staggered-origin design

Each origin date contributes one 24-hour recursive forecast. Within every
block, number origin dates from `j = 0` through `23` and set the UTC-naive
origin hour to:

```text
origin_hour = (5 * j) mod 24
```

The resulting sequence is:

```text
00, 05, 10, 15, 20, 01, 06, 11, 16, 21, 02, 07,
12, 17, 22, 03, 08, 13, 18, 23, 04, 09, 14, 19
```

Because 5 and 24 are coprime, every block uses each origin hour exactly once.
Each origin forecasts horizons 1 through 24, so every `(horizon_hour,
clock_hour)` pair appears exactly once per block and four times overall. This is
a complete crossed design for descriptive clock-hour and horizon effects. It
does not assume that overlapping target hours are statistically independent.

Each origin may use only timestamps strictly earlier than the origin. Recursive
predictions may feed later horizons inside that origin but may not be shared
between origins. Candidate and previous-week baseline are scored on the exact
same zone-hour rows.

## Frozen measures and reporting roles

All ratios use unrounded components. Presentation rounding occurs only after
the measures are calculated.

For origin `i`, with actual demand `y`, candidate prediction `c`, and
previous-week prediction `b` over all eligible zones and 24 horizons:

```text
candidate_wape_i = sum(abs(y - c)) / sum(y)
baseline_wape_i  = sum(abs(y - b)) / sum(y)
relative_improvement_i = (baseline_wape_i - candidate_wape_i) / baseline_wape_i
candidate_won_i = candidate_wape_i < baseline_wape_i
relative_degradation_i = (candidate_wape_i - baseline_wape_i) / baseline_wape_i
```

If `sum(y)` or `baseline_wape_i` is zero, the affected comparative statistic is
undefined and the evaluation cannot claim complete confirmatory evidence; no
epsilon or substituted denominator may be introduced after unblinding.

| Evidence | Frozen report | Role in this evaluation |
|---|---|---|
| Daily win rate | wins, ties, losses, rate, and all 96 origin records; ties are not wins | proposed release criterion, with no pass threshold |
| Worst-day degradation | maximum relative degradation plus candidate WAPE, baseline WAPE, absolute-error difference, demand, block, origin, and calendar route | proposed release criterion, with no cap |
| Aggregate accuracy | pooled candidate and baseline WAPE, relative improvement, bias, high-demand recall, and demand denominator, overall and by block | contextual release evidence |
| Daily drift | pass rate plus separate counts for WAPE below 25%, absolute bias below 10%, and high-demand recall at least 90% | advisory evidence only |
| Horizon and clock | complete horizon-by-clock cells, actual demand, candidate and baseline WAPE, excess absolute error, and block count | diagnostic only |

The daily drift checks retain their existing strict comparison semantics. The
high-demand threshold is calculated by the existing scorer for each complete
origin unit and must not be fitted across the held-out blocks.

Results are reported overall, for every block, and for ordinary weekday,
ordinary weekend, holiday, configured event-window, airport, non-airport,
global, airport-specialist, and event-specialist segments when their actual
demand denominator is non-zero. Empty segments are shown as not observed rather
than treated as passes.

No significance test or confidence interval may assume the overlapping
24-hour origins are independent. Block-level variation and the full origin
distribution are the required uncertainty presentation.

## Clock-hour and horizon diagnostic

For every origin and horizon, aggregate zone-level actual demand, absolute
candidate error, and absolute baseline error while retaining block, origin
hour, forecast clock hour, and horizon hour. Publish the full 24 by 24 cell
table and four block replicates.

Report descriptive marginal profiles for horizon after equally representing
all 24 clock hours, and for clock hour after equally representing all 24
horizons. A two-way additive summary may be included only with block, clock
hour, and horizon as categorical terms and with no causal or monotonic claim.
This run cannot create a horizon release threshold; changing the current
diagnostic-only role requires a later maintainer decision.

## Pre-registered hypothesis diagnostics

These diagnostics test the May hypotheses without changing features or routing:

1. **Ordinary global path.** Report candidate-minus-baseline absolute error and
   WAPE for the ordinary non-airport global route versus all other routes, with
   actual demand for each denominator.
2. **Manhattan and volume.** Before any target outcomes are scored, freeze zone
   borough from the official taxi-zone lookup and assign non-airport zones to
   volume quartiles using total demand over the candidate's training period
   only. Record the lookup digest, training-input digest, quartile boundaries,
   and exact zone membership. Report every borough-by-volume stratum and the
   pre-specified Manhattan/top-quartile global stratum; do not select zones by
   held-out error.
3. **Recent demand.** At each origin, calculate prior-day total demand,
   prior-seven-day mean and coefficient of variation, and final-three-days
   divided by the prior-seven-day mean from timestamps strictly before the
   origin. Report their overall and per-block Spearman associations with
   relative improvement. These are descriptive associations, not feature
   selection, causal evidence, or thresholds.

May 2026 values are shown separately as design history if needed and are never
included in the confirmatory numerator, denominator, ranking, or association.

## Required evidence packet

The observational output must be written to a noncanonical staging location
and contain:

- the specification version or digest, code commit, dirty-worktree state,
  Python and serialization environment, candidate digest, governed Gold and
  source digests, and zone-lookup digest;
- the 96 planned origins, their status, forecast bounds, completeness checks,
  and any deviations before any performance summary;
- per-origin raw measure components and the summary tables defined above;
- the complete horizon-by-clock table and pre-registered hypothesis tables;
- an explicit statement that May was excluded from confirmation;
- `observational_only: true`; and
- `promotion.status: not_permitted`.

The report is incomplete if an origin, zone-hour grid, required segment,
identity field, or raw metric component is silently omitted. Incomplete
evidence is not converted into a pass/fail release result.

## Freeze, deviations, and stop conditions

After maintainer acceptance, any change to candidate identity, blocks, origin
schedule, eligibility, metric formulas, segment definitions, or missing-data
handling must be recorded before outcomes are inspected. A post-outcome change
creates a new exploratory analysis and cannot reuse these blocks as fresh
confirmation.

Stop without evaluating or publishing a release decision on:

- candidate, input, lookup, or specification identity mismatch;
- training data at or after an evaluation origin;
- actual or baseline coverage gaps;
- failure of the governed data or forecast-grid checks;
- unavailable pre-origin features or target leakage;
- an attempt to change a numeric threshold after viewing results; or
- any request to promote, publish, deploy, or schedule without separate human
  authorization.

## Review and implementation boundary

Maintainer review is requested for the four blocks, staggered-origin formula,
metric definitions, subgroup freeze, and evidence packet. Acceptance of this
document would freeze the evaluation design only; it would not authorize an
evaluation run or any production operation.

The current evaluator normalizes every origin to midnight, so implementing this
design requires a later, specifically approved edit to the protected core file
`src/nyc_taxi/model_validation.py`, with matched changes in
`tests/test_recursive_shadow_evaluation.py`. The proposed implementation
validation is:

```text
python -m pytest -q tests/test_recursive_shadow_evaluation.py tests/test_forecast.py tests/test_quality_gates.py
python -m pytest -q
```

No core file, contract, active ADR, model artifact, governed dataset, or
external system was changed while preparing this specification.
