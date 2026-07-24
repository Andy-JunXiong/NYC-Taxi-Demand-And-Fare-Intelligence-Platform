# Evaluation readiness policy

Evaluation readiness describes the evidence configuration around a capability.
It does not claim that the capability is accurate, safe, or production-ready.

Evaluation decisions are recorded separately. A bundle may be
`regression_ready` and still have a `rejected` decision because complete
evidence and an unfavorable result are not contradictory.

## States

| State | Meaning | Check outcome |
|---|---|---|
| `not_configured` | No usable evaluation bundle has been configured. | `WARN` |
| `schema_only` | Contracts exist, but evaluation cases are not yet curated. | `WARN` |
| `needs_seed_cases` | Evaluation work is acknowledged but still needs reviewed seed material. | `WARN` |
| `baseline_ready` | Reviewed seed, golden, and failure cases exist, with explicit human baseline approval and evidence. | `PASS` |
| `regression_ready` | Baseline requirements pass and one regression threshold form is configured. | `PASS` |

## Reverse burden of proof

A higher label must be supported by the artifacts it names. Missing or invalid
evidence is a `FAIL`, not an automatic downgrade. This prevents a manifest from
claiming `baseline_ready` while silently behaving as `schema_only`.

For `baseline_ready` and `regression_ready`, the bundle must include at least:

- one reviewed seed case;
- one human-approved golden example;
- one reviewed failure case with a regression assertion;
- a named baseline reviewer;
- one baseline evidence reference.

`regression_ready` additionally requires exactly one configured threshold:

- a `minimum_pass_rate` between `0` and `1`; or
- a `baseline_comparison` naming the baseline, metric, metric direction, and
  non-negative minimum improvement.

The checker verifies configuration, not the observed metric or pass rate.

## Evaluation decisions

The optional `decision` object records an outcome independently of readiness:

| Outcome | Meaning |
|---|---|
| `pending` | No completed evaluation decision is claimed. |
| `accepted` | A reviewer accepted the evaluated candidate. |
| `accepted_with_conditions` | A reviewer accepted it subject to recorded conditions. |
| `rejected` | A reviewer rejected the evaluated candidate. |

Every decision records a reason, reviewer, review date, and evidence references.
A completed decision requires at least one evidence reference. These fields
record the repository's claim; they do not prove that the judgment was sound or
authorize release or deployment.

## Evidence boundaries

- Production-derived material must be explicitly marked `sanitized=true`.
- Draft seed cases do not support baseline readiness.
- Golden examples require named human approval and rationale.
- Failure cases must describe observed failure, expected behavior, and a
  machine-inspectable regression assertion.
- Case references must remain relative to the bundle and cannot traverse out of
  it or use symbolic links.
- Seed and curated examples are not a held-out benchmark unless a separate
  benchmark protocol establishes that status.
- `reviewed_at` provides review context but does not create an implicit expiry
  period. Any freshness rule must be declared by repository policy.

## Non-goals

This policy does not run models, score semantics, compare providers, set product
risk tolerance, or replace human adjudication.
