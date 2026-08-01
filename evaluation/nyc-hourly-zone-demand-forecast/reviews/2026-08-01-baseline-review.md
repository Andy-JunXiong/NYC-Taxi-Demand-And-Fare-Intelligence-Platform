# Baseline review - 2026-08-01

- Capability: `nyc-hourly-zone-demand-forecast`
- Reviewer: Jun Xiong
- Outcome: first evaluation baseline approved

## Approved scope

- A publishable forecast contains exactly one row for every requested
  zone-by-hour pair.
- JFK (Taxi Zone 132) and LaGuardia (Taxi Zone 138) use the airport specialist
  model.
- A negative predicted trip count blocks publication before the existing
  forecast product or lineage is replaced.

## Evidence

- `tests/test_prediction.py::test_forecast_publication_gate_checks_grid_and_routing`
- `tests/test_prediction.py::test_airport_specialist_routing_covers_jfk_and_laguardia`
- `tests/test_prediction.py::test_negative_prediction_does_not_replace_published_product`

## Verification

- Python 3.11.9 full suite: 251 passed, 1 skipped.
- AgentGov repository check: 17 passed, 1 warning, 0 failed. The remaining
  warning concerns optional capability artifacts, not evaluation readiness.
- AgentGov agent-skills check: 4 passed, 0 failed.
- `git diff --check`: passed.

This approval establishes evaluation evidence only. It does not authorize
model promotion, forecast publication, deployment, scheduling, or any external
system mutation.
