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

The AgentGov evaluation bundle begins with draft synthetic cases. They require
maintainer review before the readiness level can advance.

## Approval and escalation boundary

AgentGov checks validate repository declarations and references only. Passing
them does not authorize model release, forecast publication, deployment,
scheduling, or external mutation.

The current implementation has a deterministic release path:
`rolling_backtest` replaces `production.joblib` when all model gates pass, and
the scheduled operations workflow can then publish a forecast. It does not
implement a separate per-release human approval checkpoint. Adding such a
runtime or workflow gate is an unresolved architecture decision and requires
explicit maintainer approval before changing `src/nyc_taxi/model_validation.py`
or `.github/workflows/operations.yml`.

The dated review queue for this decision, evaluation readiness, Python
environment repair, and capability artifacts is maintained in
`docs/governance-todo.md`.
