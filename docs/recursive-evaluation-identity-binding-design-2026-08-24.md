# Recursive evaluation identity-binding design

Date: 2026-08-24
Status: proposed for maintainer review; no core implementation authorized
Decision boundary: observational staggered evaluation only

## Decision

Require every future staggered recursive evaluation to bind, before model
deserialization or outcome access, to:

1. the exact candidate model byte digest;
2. one canonical executable evaluation-plan digest;
3. a named block inside that plan; and
4. the plan's frozen origin schedule and evidence boundary.

Legacy midnight recursive shadows remain available as explicitly unbound,
exploratory evidence. A non-zero `origin_hour_step` may not run through the
unbound path after this design is implemented.

This binding is not a human approval record. It permits generation of
observational staging evidence only and must continue to emit
`promotion.status = not_permitted`.

## Why the Markdown file is not the executable identity

The review document remains the human-readable rationale, but its raw bytes can
change across checkouts when line endings are normalized. A raw Markdown file
SHA would therefore bind formatting and platform behavior rather than only the
reviewed evaluation semantics.

The executable identity should instead be a small JSON plan under
`evaluation/`. Its digest is computed from canonical parsed content:

```text
UTF-8 JSON
→ reject duplicate object keys
→ validate the closed schema
→ serialize with sorted keys, no insignificant whitespace, UTF-8 characters
→ SHA-256
```

The plan links to the Markdown rationale. The raw Markdown SHA may be recorded
as provenance, but it is not the deterministic gate.

## Proposed executable plan

Proposed file:

```text
evaluation/recursive-evaluation-plan-2026-08-24.v1.json
```

Required closed fields:

```json
{
  "schema_version": "1.0",
  "plan_id": "recursive-evaluation-2026-08-24-v1",
  "rationale": "docs/recursive-evaluation-preregistration-2026-08-24.md",
  "candidate_model_sha256": "29354b382cd6761c3a307c76d821bb1855354cc87eb3c8f9b020cdf83134e334",
  "training_period_end": "2026-04-30",
  "horizon_hours": 24,
  "origin_hour_step": 5,
  "observational_only": true,
  "promotion_permitted": false,
  "blocks": [
    {"id": "A", "start_date": "2026-06-01", "end_date": "2026-06-24"},
    {"id": "B", "start_date": "2026-06-29", "end_date": "2026-07-22"},
    {"id": "C", "start_date": "2026-11-09", "end_date": "2026-12-02"},
    {"id": "D", "start_date": "2026-12-15", "end_date": "2027-01-07"}
  ],
  "metric_roles": {
    "daily_win_rate": "proposed_release_criterion",
    "worst_day_degradation": "proposed_release_criterion",
    "daily_drift": "advisory",
    "horizon_clock": "diagnostic_only"
  }
}
```

Schema validation must reject unknown fields, duplicate block IDs, overlapping
blocks, blocks other than exactly 24 inclusive origin dates, a non-coprime
origin step, a horizon other than 24, malformed lowercase SHA-256, training at
or after the first block, or any plan that permits promotion.

## Proposed evaluator interface

Confirmation-mode CLI:

```text
python -m src.nyc_taxi.model_validation \
  --input <governed-gold> \
  --output-dir <noncanonical-staging> \
  --shadow-model <candidate-v2> \
  --evaluation-plan evaluation/recursive-evaluation-plan-2026-08-24.v1.json \
  --expected-evaluation-plan-sha256 <reviewed-canonical-sha256> \
  --evaluation-block A \
  --expected-model-sha256 29354b382cd6761c3a307c76d821bb1855354cc87eb3c8f9b020cdf83134e334
```

In confirmation mode, dates, horizon, and `origin_hour_step` come only from the
verified plan. Supplying `--shadow-start`, `--shadow-end`, or
`--shadow-origin-hour-step` at the same time is rejected rather than silently
overridden.

The existing date/step interface remains for midnight exploratory shadows.
After this binding is implemented, a non-zero step on that unbound interface
must fail and direct the caller to confirmation mode.

## Verification order

The evaluator must perform these checks in order and produce no new report on
failure:

1. validate expected digest syntax;
2. read, duplicate-key check, schema-validate, and canonicalize the plan;
3. compare the canonical plan digest with the reviewed expected digest;
4. select and validate the named block;
5. verify that the plan candidate digest equals the separately supplied
   expected model digest;
6. hash the model bytes and compare them with both expected identities;
7. only then call `joblib.load`;
8. load governed demand and run the already implemented chronological and
   coverage checks;
9. generate observational evidence; and
10. re-hash the plan and model before atomically replacing the staging report.

Hashing the model before `joblib.load` is mandatory because joblib artifacts
must not be deserialized before their exact reviewed identity is established.
The final re-hash detects replacement during evaluation.

## Evidence shape

A bound report adds:

```json
{
  "identity_binding": {
    "status": "verified",
    "plan_id": "recursive-evaluation-2026-08-24-v1",
    "block_id": "A",
    "evaluation_plan_sha256": "<canonical digest>",
    "candidate_model_sha256": "29354b382cd6761c3a307c76d821bb1855354cc87eb3c8f9b020cdf83134e334",
    "verified_before_model_load": true,
    "reverified_before_report_write": true
  }
}
```

An old midnight shadow reports `identity_binding.status = unbound_exploratory`.
It cannot claim confirmation and cannot be pooled with bound block results.

## Failure matrix

| Condition | Required result |
|---|---|
| Any confirmation identity argument missing | Reject before reading outcomes |
| Malformed expected digest | Reject before reading the plan or model |
| Duplicate/unknown/malformed plan field | Reject before loading the model |
| Canonical plan digest mismatch | Reject before loading the model |
| Plan candidate and expected candidate disagree | Reject before loading the model |
| Actual model bytes disagree | Reject before `joblib.load` |
| Unknown block or block semantics invalid | Reject before loading governed demand |
| Unbound non-zero origin step | Reject and require confirmation mode |
| Plan or model changes during evaluation | Do not replace the prior staging report |
| Any identity failure | Never promote, publish, or write an approval record |

Errors should name the failed identity class without printing model bytes,
private data, or complete external payloads.

## Compatibility and non-goals

- Existing midnight calls with no identity arguments remain exploratory and
  retain their prior date interface.
- Existing release and publication gates are unchanged.
- The plan adds no numeric model-release threshold.
- This design does not authorize creation of later governed data, execution of
  Blocks A-D, model training, promotion, publication, deployment, or scheduling.
- This design does not make rebuilt joblib bytes equivalent to the frozen
  candidate.

## Proposed implementation scope and validation

Implementation would require separate approval for exactly:

- `src/nyc_taxi/model_validation.py`;
- `tests/test_recursive_shadow_evaluation.py`; and
- new `evaluation/recursive-evaluation-plan-2026-08-24.v1.json`.

Proposed validation:

```text
python -m pytest -q tests/test_recursive_shadow_evaluation.py
python -m pytest -q tests/test_recursive_shadow_evaluation.py tests/test_forecast.py tests/test_quality_gates.py
python -m pytest -q
```

Matched tests must prove verification happens before `joblib.load`, every
failure leaves an existing staging report byte-identical, canonical digesting
is insensitive to insignificant JSON formatting and key order, duplicate keys
are rejected, unbound staggered runs are rejected, and the bound plan reproduces
the reviewed four blocks and step-five schedule.
