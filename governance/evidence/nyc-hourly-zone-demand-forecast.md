# NYC hourly zone-demand forecast implementation evidence

## Capability boundary

`src/nyc_taxi/prediction.py` publishes pickup-count forecasts for each available
NYC Taxi Zone for a caller-selected horizon of 1 to 168 hours. The normal
operational horizon is 24 hours. It consumes governed hourly Gold demand and the
release-gated model bundle; it does not ingest raw trip rows or make dispatch,
fare, tip, or fleet-allocation decisions.

## Inputs and model routing

- Gold history supplies `pickup_zone_id`, `pickup_hour`, and `trip_count`.
- `models/demand_release/production.joblib` supplies the global model, feature
  contract, approved specialist models, and release metadata.
- JFK and LaGuardia use the airport specialist. Configured event windows use the
  event specialist outside airport zones. Remaining rows use the global model.

## Output and controls

The Parquet product records generation and forecast times, zone, non-negative
predicted pickup count, model type and version, and event code. Before atomic
publication, `validate_forecast` requires:

- the exact Zone-by-hour grid for the requested horizon;
- unique `(pickup_zone_id, forecast_hour)` keys;
- no missing or negative predictions;
- correct airport, event, and global routing.

Lineage records Gold, model, and output checksums plus the gate result. A failed
gate raises an error before replacing the published product. Existing releases
are archived, and the operations layer records completed, blocked, or failed
runs.

## Evaluation evidence

- `docs/demand-forecast-mvp.md` records the initial chronological holdout.
- `docs/model-release-2024-h2.md` records expanding-window model admission.
- `docs/forecast-closure-2025-01-01.md` records a detected event-regime failure.
- `docs/event-model-release-2025-01.md` records the subsequent specialist model
  evaluation and approved replacement.
- `tests/test_prediction.py` exercises grid, validity, and routing gates.

The AgentGov evaluation bundle has a maintainer-approved first baseline. It
contains reviewed complete-grid and JFK/LaGuardia routing seeds, an approved
complete-grid golden example, and a reviewed negative-prediction failure case
whose regression test verifies that a rejected publication does not replace
the existing forecast product or lineage.

## Approval and escalation boundary

AgentGov checks validate repository declarations and references only. Passing
them does not authorize model release, forecast publication, deployment,
scheduling, or external mutation.

The deterministic model gate produces `candidate.joblib` but does not itself
authorize promotion. Replacing `production.joblib` requires a separate
`model_promotion` approval record naming a reviewer and binding approval to the
candidate SHA-256. Forecast publication separately requires a
`forecast_publication` approval bound to the production model SHA-256. Scheduled
operations stop after validation and cannot automatically cross either human
checkpoint.

The dated review queue for evaluation readiness, Python environment repair, and
capability artifacts is maintained in
`docs/governance-todo.md`.
