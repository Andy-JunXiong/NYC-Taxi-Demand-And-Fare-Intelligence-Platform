# EDA-to-data-governance audit

## Purpose and evidence

This document audits `Taxi-NYC-EDA-Part1.ipynb` and
`Taxi-NYC-EDA-Part2.ipynb` as historical research artifacts. The notebooks are
evidence of intended business semantics, but they are not treated as executable
data contracts. Saved cell sources, Markdown claims, and outputs were compared
cell by cell.

## Semantics worth preserving

- Trip and fare records represent a trip-level grain and were joined using their
  shared trip identifiers.
- Pickup time supports calendar features and day/night analysis.
- Source duration and timestamp-derived duration are separate observations that
  should be reconciled, not silently collapsed.
- Passenger count, rate code, monetary values, duration, distance, speed, and
  geography are important quality dimensions.
- Airport trips have different fare behavior and should be a governed segment,
  not automatically treated as generic outliers.
- Earnings-per-time and earnings-per-distance are downstream business metrics,
  not source-system facts.
- Geography, shift behavior, driver activity, demand, fare, and earnings are
  distinct data products with different eligibility rules.

## Findings that prevent direct rule migration

| Notebook evidence | Finding | Governance decision |
| --- | --- | --- |
| Part 1 cells 13-14 | `train[pd.isnull(train)].sum()` does not produce a reliable null-count profile. | Profile nulls explicitly per column before filtering. |
| Part 1 cells 31-32 | Timestamp duration uses `timedelta.seconds`; 3,971,232 rows disagree with the supplied duration. | Preserve both durations, calculate with `total_seconds`, and emit a disagreement flag and distribution. |
| Part 1 cell 34 | Labels for distance/time checks are swapped and both expressions inspect time fields. | Contract tests must bind every rule to its named column. |
| Part 1 cells 35-36 | `time_max` only removes the single observed maximum and has no business meaning. | Use documented plausibility flags; never use sample maxima as contracts. |
| Part 1 cells 37-40 | A 30 mph street limit is used as a universal trip-average deletion threshold, removing 475,780 rows. | Treat speed as a quality signal; use a configurable physical-plausibility threshold and retain the raw row. |
| Part 1 cells 47-52 | A rectangle requires both endpoints inside NYC, excluding legitimate boundary and external trips. | Use official Taxi Zone dimensions for modern data; retain out-of-area trips with flags for legacy data. |
| Part 1 cells 59-61 | Fare-per-minute `<=3` is inferred from a simplified tariff and speed assumption. | Keep as an exploratory feature, not a universal validity rule. |
| Part 1 cells 65-69 | Earnings-per-minute thresholds are successively changed from 30 to 22 to 15 without a selected-rule rationale. | Threshold changes require versioned configuration, impact counts, and approval. |
| Part 1 cells 75-77 | Fare-per-mile filtering and saved counts are not fully reconcilable from notebook state. | Every Silver build emits row-count reconciliation. |
| Part 1 cell 85 | Six sequential assignments overwrite the airport/outlier flag; the final state does not implement the Markdown rule. | Airport membership and fare anomaly are independent flags; no sequential overwrites. |
| Part 1 cells 81-84 | Airport rectangles require roughly one hour of row-wise processing per airport pair. | Use vectorized spatial/dimension joins. |
| Part 1 cells 104-105 | `log(tip_amount)` includes zero tips, producing non-finite values. | Transformations declare zero/null behavior and are tested. |
| Part 2 cells 6-8, 29-31 | Overlapping borough rectangles are resolved by dictionary order. | Use the official Taxi Zone lookup/polygon dimension. |
| Part 2 cells 11-12 | Chart labels say “by Hour” while grouping by borough; online Plotly creates an external side effect. | Gold metric names and dimensions are contract-tested; pipelines do not publish externally. |
| Part 2 cells 49-54 | “Night shift percentage” is the percentage of trips at night, not identified work shifts. | Name it `night_trip_ratio`; shift metrics require driver sessionization. |
| Part 2 cells 51-56 | A calendar date with any trip is counted as a workday; income excludes some monetary fields and cash tips are not fully observed. | Driver-income products require an explicit revenue definition, session rules, and measurement-bias warning. |

Additional reproducibility evidence: Part 1's displayed pre-save columns do not
show borough fields while Part 2 loads a file that already contains them; Part 1
also references undeclared `train_3`, and Part 2 deletes undeclared `JFK_data`.
Saved notebook state therefore cannot establish lineage by itself.

## Governed architecture

```text
Bronze: immutable official files + source URL + SHA-256
   |
   v
Contract validation: schema, types, partition identity
   |
   v
Silver: source columns + normalized names + official zone attributes
        + non-destructive quality flags + row reconciliation
   |                          |
   v                          v
Gold demand                 Gold fare / operations
minimal eligibility         product-specific eligibility
   |
   v
Feature and model datasets with lineage to Gold and Bronze checksums
```

The 2013 coordinate/driver schema and modern Taxi Zone schema have separate
contracts. They may support comparable business questions but must not be silently
unioned.

## Quality dimensions

Every monthly build reports, at minimum:

- source and Silver row counts;
- schema/type contract result;
- missing pickup/dropoff timestamps;
- pickups outside the filename month;
- unknown pickup/dropoff zone IDs against the official dimension;
- nonpositive duration;
- negative distance, fare, or total;
- physically implausible average speed;
- candidate duplicate count;
- demand-eligible and fare-eligible counts;
- source and output SHA-256 values.

Rules create flags in Silver. Rows are removed only when a named Gold product's
eligibility contract requires it.

## Data-product boundaries

### Demand

Requires only a pickup timestamp belonging to the source month and a valid official
pickup zone. Negative fare or bad dropoff data does not erase evidence that a pickup
occurred.

### Fare and operational efficiency

Requires valid demand fields plus positive duration and nonnegative distance, fare,
and total. Extreme values remain flagged for sensitivity analysis rather than being
silently deleted.

### Driver behavior

Only the legacy dataset exposes driver hashes. This product must remain isolated,
must not enter public samples, and requires sessionization before using the word
“shift.” Cash-tip under-observation must be stated explicitly.

## Release gates

A monthly partition fails closed when required columns/types are incompatible,
the official zone dimension is missing, row reconciliation fails, or a source file
checksum differs from its manifest. Quality-rate changes are reported separately;
threshold-based release blocking should be introduced only after several months
establish a baseline.
