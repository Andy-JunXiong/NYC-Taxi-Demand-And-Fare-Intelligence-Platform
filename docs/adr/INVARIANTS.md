# Architecture invariants - NYC Taxi Demand and Fare Intelligence Platform

## Purpose

This register lists constraints that ordinary feature work must preserve. It
does not duplicate every ADR or coding convention. Each invariant must identify
its authority, enforcement point, and verification method.

## Status semantics

- `proposed`: under review and not yet an enforced project constraint;
- `active`: approved and currently enforced;
- `deprecated`: still visible during migration but must not be used for new
  work;
- `retired`: no longer enforced; replacement or retirement evidence is linked.

## Enforcement semantics

- `deterministic`: code, schema, configuration, or a repeatable check can decide
  pass or fail;
- `review`: a named human review is required because the boundary cannot be
  reduced to a reliable static check;
- `hybrid`: deterministic checks cover part of the boundary and review covers
  the remainder.

Do not label a judgment-based rule as deterministic merely because a document
contains matching words.

---

## TAXI-DATA-001 - Non-destructive governed data layers

- Status: `active`
- Owner: Repository maintainers
- Authority: `docs/eda-data-governance-audit.md`
- Enforcement: `hybrid`

### Statement

Bronze preserves immutable source identity, Silver retains source rows while
adding quality flags, and a row may be excluded only by a named Gold product's
eligibility contract.

### Rationale

Silent destructive cleaning would erase observed demand, weaken lineage, and
make quality and model results irreproducible.

### Applies to

- `src/nyc_taxi/governance.py`
- `src/nyc_taxi/monthly_pipeline.py`
- modern NYC monthly data products

### Does not apply to

- Historical notebooks remain research evidence and are not production
  implementations of this invariant.

### Enforcement points

- `contracts/`
- `src/nyc_taxi/governance.py`
- `tests/test_governance.py`
- `tests/test_ci_sample.py`

### Verification

- Automated: `python -m pytest -q tests/test_governance.py tests/test_ci_sample.py`
- Review: Repository maintainer reviews changes to product eligibility.
- Passing evidence: row reconciliation passes and the Gold lineage references
  governed Silver inputs.

### Failure response

Block publication, preserve the last valid product, and require maintainer
review of any eligibility-contract change.

### Change history

| Date | Change | Authority |
|---|---|---|
| 2026-07-24 | Adapted from the implemented data-governance audit | `docs/eda-data-governance-audit.md` |

## TAXI-MODEL-001 - Leakage-safe chronological evaluation

- Status: `active`
- Owner: Repository maintainers
- Authority: `docs/demand-forecast-mvp.md`
- Enforcement: `hybrid`

### Statement

Demand models use chronological validation and test windows; lag and rolling
features may use only demand available before the predicted hour.

### Rationale

Random splits or target-inclusive rolling windows would overstate forecast
quality and could admit an unsafe model release.

### Applies to

- `src/nyc_taxi/features.py`
- `src/nyc_taxi/forecast.py`
- `src/nyc_taxi/model_validation.py`

### Does not apply to

- Historical notebook scores, which are explicitly retrospective.

### Enforcement points

- feature construction and expanding-window backtests;
- model release gates documented in `docs/model-release-2024-h2.md`.

### Verification

- Automated: `python -m pytest -q tests/test_forecast.py tests/test_quality_gates.py`
- Review: Repository maintainer reviews changes to split or release semantics.
- Passing evidence: all folds use earlier training periods and the release
  gate passes without target leakage.

### Failure response

Reject the candidate model and retain the last approved production artifact.

### Change history

| Date | Change | Authority |
|---|---|---|
| 2026-07-24 | Recorded implemented forecast boundary | `docs/demand-forecast-mvp.md` |

## TAXI-PUBLISH-001 - Fail-closed forecast publication

- Status: `active`
- Owner: Repository maintainers
- Authority: `docs/forecast-operations.md`
- Enforcement: `deterministic`

### Statement

A forecast becomes canonical only after the Zone-by-hour grid, key uniqueness,
prediction validity, and model-routing gates pass; a complete immutable release
bundle is verified; and `latest.json` is atomically replaced to name that bundle.

### Rationale

Partial or incorrectly routed forecasts can mislead downstream operational
decisions and must not overwrite the last known-good product.

### Applies to

- `src/nyc_taxi/prediction.py`
- `src/nyc_taxi/releases.py`
- `src/nyc_taxi/monitoring.py`
- `src/nyc_taxi/operations.py`
- `data/processed/forecasts/` runtime products

### Does not apply to

- Unpublished research outputs under ignored local model directories.

### Enforcement points

- `src/nyc_taxi/prediction.py`
- `src/nyc_taxi/releases.py`
- default monitoring resolution through `data/processed/forecasts/latest.json`
- `tests/test_prediction.py`, `tests/test_releases.py`, and
  `tests/test_publication_failure_safety.py`

### Verification

- Automated: `python -m pytest -q tests/test_prediction.py tests/test_releases.py tests/test_publication_failure_safety.py`
- Review: Not applicable for the deterministic publication gate.
- Passing evidence: `validate_forecast` returns `passed=true`, the release
  resolver verifies all three artifact digests, and injected pre-pointer-swap
  failures leave the previous pointer canonical.

### Failure response

Raise an error and leave `latest.json` unchanged. A complete bundle finalized
before a failed pointer swap may remain as noncanonical evidence; incomplete
staging directories must not be addressable through the pointer. Record the
blocked or failed run in the operational ledger.

### Change history

| Date | Change | Authority |
|---|---|---|
| 2026-07-24 | Recorded implemented publication boundary | `docs/forecast-operations.md` |
| 2026-08-14 | Replaced mutable multi-file publication with immutable release bundles and one canonical pointer | Authenticated maintainer approval for this adaptation |
