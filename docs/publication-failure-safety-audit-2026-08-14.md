# Publication Failure-Safety Audit — 2026-08-14

## Scope

This audit exercised the governed forecast publication path with synthetic data
and a valid synthetic approval. All files were created under temporary test
directories. No production artifact or external system was modified.

The current probe injects failures at three points:

1. writing lineage inside a private pending release;
2. writing the staged `latest.json`; and
3. atomically replacing the canonical `latest.json`.

The reproducible probe is
[`tests/publication_failure_probe.py`](../tests/publication_failure_probe.py),
with regression enforcement in
[`tests/test_publication_failure_safety.py`](../tests/test_publication_failure_safety.py).

## Initial finding and superseded remediation

The original mutable multi-file publication path could expose a new forecast
with old lineage or a new forecast and lineage with an old latest pointer. A
first remediation staged all files and attempted rollback after sequential
replacements. That made handled exceptions recoverable but still left a process
termination, power-loss, and concurrent-reader window between replacements.

## Current remediation

`src/nyc_taxi/prediction.py` now:

- writes forecast, lineage, and gate into a unique private pending directory;
- computes and records SHA-256 digests for all three artifacts;
- renames the complete directory to an immutable release ID;
- validates a staged pointer against the visible complete bundle; and
- changes canonical state with one atomic `latest.json` replacement.

`src/nyc_taxi/releases.py` confines pointer paths to the publication root and
declared release directory, verifies every artifact digest, binds lineage to the
release ID and forecast digest, and requires a passing gate. Default monitoring
and operational monitoring use that resolver. Explicit `--forecast` remains
available only for staging evaluation.

The former mutable forecast and lineage paths remain untouched during migration
and are noncanonical. Immutable release directories replace the old copy archive:
each successful release is already retained by content and release identity.

## Injected-failure evidence

All three failures preserve the previous canonical pointer:

| Failure | Pointer changed | Incomplete visible bundle | Expected orphan | Result |
|---|---:|---:|---:|---|
| Pending lineage write | No | No | No | Safe failure |
| Latest staging write | No | No | One complete bundle | Safe failure |
| Latest atomic replace | No | No | One complete bundle | Safe failure |

An orphan created after bundle finalization is complete but is not named by
`latest.json`, so it is not a published product. Pending directories and `.part`
files are cleaned for the injected handled exceptions.

## Interpretation boundary

The architecture removes sequential canonical-file replacement: a concurrent
consumer resolving `latest.json` sees either the complete prior release or the
complete new release. This relies on same-filesystem atomic rename semantics for
the pointer. Host filesystem behavior determines durability across abrupt power
loss, and the test does not claim to simulate every storage-device failure mode.

The approval, validation, routing, model, and artifact-binding semantics were
not weakened. This evidence does not authorize publication, promotion,
deployment, cleanup of orphan releases, or any external mutation.

## Validation

- Fault-injection probe: `safe_failure_behavior_observed` for all three scenarios.
- Focused release, publication, prediction, operations, and intervention tests:
  `30 passed`.
- Complete repository suite: `88 passed`, with one existing joblib/loky CPU-count
  warning.
- AgentGov repository check: `17 PASS`, `0 FAIL`, `1 WARN`, `4 ADVISORY`.
- AgentGov agent-skills check: `4 PASS`, `0 FAIL`.

These are dated verification results, not release authorization.
