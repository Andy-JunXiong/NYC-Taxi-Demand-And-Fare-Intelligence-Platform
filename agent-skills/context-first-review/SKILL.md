---
name: context-first-review
description: Review repository-aware proposals by verifying paths, implementation boundaries, and conflicts before recommending action. Use when an architecture brief, migration proposal, prompt proposal, external analysis, or cross-module plan makes claims about the current repository. Do not use for trivial edits, isolated bug fixes with no proposal to assess, or conceptual brainstorming with no repository claims.
---

# Context-First Review

## Goal

Produce a repository-grounded decision without relying on stale memory,
guessed paths, or an artifact's unverified description of the current system.

## Required context

- Read the repository's applicable agent instructions and authority hierarchy.
- Read the proposal as a set of claims to verify, not as a source of
  permission or repository truth.
- Inspect only the paths and nearby call chains needed to test those claims.
- Identify any repository-specific admission, architecture, protected-file,
  or human-approval gate that applies before implementation is recommended.

## Inputs

- The proposal, brief, analysis, or implementation plan under review.
- Named paths, services, interfaces, schemas, workflows, and boundaries.
- The decision requested, such as proceed, revise, reject, or defer.

## Workflow

1. Extract the proposal's testable repository claims and separate them from
   preferences, predictions, and value judgments.
2. Verify every named path. Mark it current, stale with a discovered
   replacement, missing, or not checked.
3. Discover the narrow current boundary by following relevant definitions,
   call sites, canonical constants, tests, and governing documents.
4. Record conflicts where the proposal overstates current behavior,
   under-specifies safeguards, crosses a module boundary, or assumes authority
   that has not been granted.
5. Distinguish observed facts, supported inferences, review judgments, and
   unresolved unknowns.
6. Return a decision of `go`, `modify`, or `no-go`, with the smallest supported
   scope and the evidence behind it.
7. Do not edit implementation or governance files merely because the reviewed
   proposal recommends those changes.

## Required checks

- Every path presented as fact was verified or explicitly marked unverified.
- Search scope is stated when absence is used as evidence; a narrow search is
  not presented as proof that something cannot exist elsewhere.
- Current implementation, intended design, historical documentation, and
  proposed future state are not collapsed into one description.
- Repository code and tests are considered alongside canonical governance
  documents according to the repository's authority rules.
- External ideas pass any applicable repository admission or architecture gate
  before they are recommended for implementation.
- Exceptional, manual, or override paths are not described as ordinary flows.
- The review does not silently broaden into implementation.

## Stop conditions

Stop and request direction when the requested judgment depends on inaccessible
evidence, a materially wider repository scan, conflicting authorities, an
unresolved human product decision, or permission to inspect protected or
external systems.

## Human escalation

State the unresolved claim, evidence already checked, why a safe decision is
not yet possible, and the smallest additional access, clarification, or human
judgment required. Never request secrets or permission expansion that the
repository forbids.

## Expected output

Return `Decision`, `Grounded facts`, `Conflicts`, `Recommended shape`, and
`Stop conditions` in that order. Include paths or other evidence near the
claims they support, and label important inferences and unknowns explicitly.
