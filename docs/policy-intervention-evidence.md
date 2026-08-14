# Policy Intervention Evidence

This record summarizes controlled behavioral comparisons for the NYC release
controls. It complements unit and integration coverage by showing the decision
delta associated with each controlled input change.

The tests call the production approval, promotion, forecast-generation, and
publication functions with synthetic data in isolated temporary directories.
They do not add or use a production switch that disables a release gate.

## Evidence matrix

| Mechanism | Governed observation | Controlled comparison | Observed decision delta | Automated evidence |
|---|---|---|---|---|
| Approval requirement | Missing approval raises `PermissionError`; the last-known-good model remains unchanged. | A matching named approval promotes the exact same candidate bytes. | `BLOCK` → `PROMOTE` | `test_approval_requirement_changes_promotion_outcome` |
| SHA-256 artifact binding | Approval for model A is rejected when presented with changed model B; production remains unchanged. | Approval containing model B's current digest promotes model B. | `REJECT` → `PROMOTE` | `test_digest_binding_rejects_stale_approval_and_preserves_production` |
| Forecast validation | A synthetic negative forecast fails the publication gate and leaves the published forecast unchanged. | A valid synthetic forecast with the same release prerequisites is published. | `BLOCK` → `PUBLISH` | `test_validation_gate_changes_publication_outcome_and_preserves_old_product` |
| Airport/event/global routing | During an event window, an airport zone uses the airport specialist while a non-airport zone uses the event specialist. | In the following ordinary hour, the same non-airport zone uses the global model; the airport remains on the airport specialist. | `EVENT` → `GLOBAL`, with `AIRPORT` precedence preserved | `test_airport_event_global_routing_changes_decision_path` |

All automated evidence is implemented in
[`tests/test_policy_interventions.py`](../tests/test_policy_interventions.py).
The models used by the routing scenario return distinct values, so an incorrect
route cannot pass merely because two model outputs happen to be equal.

## Interpretation boundary

These results demonstrate deterministic enforcement and behavioral sensitivity
under controlled test conditions. They do not establish real-world causal model
effects, authorize publication, or replace human approval. Canonical publication
uses a complete immutable three-artifact bundle and one atomic latest-pointer
replacement rather than claiming a multi-file filesystem transaction.

## Reproduction

Run the focused evidence suite:

```text
python -m pytest -q tests/test_policy_interventions.py
```

Run the repository acceptance suite:

```text
python -m pytest -q
```

Last locally observed on 2026-08-14: `4 passed` in the focused suite and
`88 passed` in the complete suite. These counts are dated evidence, not release
authorization.
