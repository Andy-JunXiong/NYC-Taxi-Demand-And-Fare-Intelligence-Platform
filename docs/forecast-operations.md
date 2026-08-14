# Governed 24-hour forecast operations

## Published product

The production inference job creates a recursive 24-hour forecast for every
governed Taxi Zone. JFK (132) and LaGuardia (138) are automatically routed to
the airport specialist. Non-airport zones in an event window use the event
specialist when the approved model artifact includes one; all remaining zones
use the global model.

The first published run covers 2025-01-01 00:00–23:00: 263 zones, 24 hours, and
6,312 unique rows. Each row contains forecast generation time, forecast hour,
pickup zone, predicted trips, model type, and model version.

```powershell
python -m src.nyc_taxi.prediction --approval-file <forecast-approval.json>
```

The product is written as an immutable bundle under
`data/processed/forecasts/releases/<release-id>/`. Its lineage records Gold and
model checksums, output checksum, horizon, coverage, approval, and gate decision.
`data/processed/forecasts/latest.json` is atomically replaced only after the
complete bundle and all three artifact digests verify; it is the canonical route
to the current product. Older mutable forecast and lineage paths are legacy and
are not updated.

## Staging forecast closure

A release-gate-passing model candidate can be evaluated against later actuals
without promoting the model or publishing a forecast. Use a cutoff Gold artifact
that ends immediately before the forecast window, the exact candidate named by
its `rolling_backtest.json`, and an output directory below
`data/processed/staging/`:

```powershell
python -m src.nyc_taxi.operations --ledger <staging-output>/runs.sqlite forecast-candidate `
  --input <cutoff-gold.parquet> `
  --model <candidate.joblib> `
  --model-report <rolling_backtest.json> `
  --output-dir <staging-output>

python -m src.nyc_taxi.operations --ledger <staging-output>/runs.sqlite monitor `
  --forecast <staging-output>/forecast.parquet `
  --actual <full-gold-with-matured-actuals.parquet> `
  --output <staging-output>/monitoring.json
```

The candidate command verifies the model report's passing release gate,
`awaiting_human_approval` status, and exact candidate SHA-256. It writes only
`forecast.parquet`, `lineage.json`, and `gate.json` inside the staging output.
Candidate lineage uses `status: candidate` and `source_model`; it does not claim
that the model is production, consume a publication approval, publish a release
bundle, or update `latest.json`.

A scored drift failure is a stop condition. It must be reported and investigated;
it does not authorize threshold changes, model promotion, or forecast publication.

## Publication gates

A run is published only when it has the exact Zone-by-hour grid, unique keys, no
missing or negative predictions, and correct airport/event/global model routing.
Forecast, lineage, and gate are completed in a private directory; the finalized
immutable release becomes current through one atomic latest-pointer replacement.

## Monitoring

After actual Gold hours arrive, run:

```powershell
python -m src.nyc_taxi.monitoring
```

Monitoring reports MAE, RMSE, WAPE, signed bias, and high-demand precision/recall.
It segments performance by month, hour, airport market, and Taxi Zone. Drift
gates require WAPE below 25%, absolute bias below 10%, and high-demand recall of
at least 90%.

With no `--forecast` override, monitoring resolves `latest.json`, confines all
artifact paths to the named release directory, verifies the forecast, lineage,
and gate digests, and records the source release ID in its report. An explicit
`--forecast` is reserved for staging closure workflows.

If actuals have not reached the forecast window, status is
`waiting_for_actuals`; the system does not treat missing future observations as
zero demand. A scored drift failure returns a non-zero process status for
scheduler alerting.

## Current state

January 2025 actuals exposed a New Year's Day failure in the original model. An
event-aware replacement subsequently passed expanded release gates and published
the 2025-02-01 forecast. See
[`forecast-closure-2025-01-01.md`](forecast-closure-2025-01-01.md) and
[`event-model-release-2025-01.md`](event-model-release-2025-01.md).
