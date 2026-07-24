---
adr: "<ADR_NUMBER>"
title: "<ADR_TITLE>"
status: Proposed
created: "<YYYY-MM-DD>"
owners:
  - "<DECISION_OWNER>"
related:
  - "<RELATED_DECISION_OR_DOC>"
---

# ADR-<ADR_NUMBER>: <ADR_TITLE>

## Decision gate

Create or retain this ADR only when all answers are yes:

- [ ] Reversing the decision later would have meaningful cost.
- [ ] Future maintainers would lose important context without this record.
- [ ] At least two plausible alternatives have a real tradeoff.

If the gate does not pass, record the choice in an ordinary design note or
task instead.

## Context

Describe the observed problem, current constraints, and evidence that makes a
durable decision necessary. Separate verified repository facts from assumptions
and expected future pressure.

## Decision

State the chosen rule or architecture in direct language. Identify what becomes
required, allowed, forbidden, or explicitly deferred.

## Owns

- <BOUNDARY_OWNED_BY_THIS_ADR>

## Does not own

- <RELATED_BUT_SEPARATE_BOUNDARY>

## Invariants created or changed

- Invariant record: `<INVARIANT_ID_OR_NONE>`
- Enforcement point: `<CODE_POLICY_OR_REVIEW_GATE>`

Use `none` when the decision creates no durable invariant. Do not invent an
invariant merely to make the section non-empty.

## Consequences

### Benefits

- <EXPECTED_BENEFIT>

### Costs and risks

- <KNOWN_COST_OR_RISK>

### Operational impact

- <DEPLOYMENT_MONITORING_OR_SUPPORT_IMPACT>

## Alternatives considered

### <ALTERNATIVE_NAME>

Describe the alternative, why it was plausible, and why it was not selected.

## Implementation plan

1. <SMALLEST_IMPLEMENTATION_STEP>
2. <VALIDATION_OR_MIGRATION_STEP>

List separate approval gates explicitly. An accepted ADR does not itself grant
permission to edit protected files, mutate external systems, or release code.

## Validation

- Automated: `<AUTOMATED_VALIDATION_COMMAND>`
- Manual: <MANUAL_VALIDATION_OR_NOT_REQUIRED>
- Success signal: <BINARY_ACCEPTANCE_SIGNAL>

## Rollback or replacement

Describe how the decision can be superseded, what state must be migrated, and
which invariant or enforcement point must be removed or replaced.

## Open questions

- <OPEN_QUESTION_OR_NONE>
