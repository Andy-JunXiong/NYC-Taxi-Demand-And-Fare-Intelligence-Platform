# NYC Taxi remaining development plan

Updated 2026-08-09. Completed work stays in the development record; this page
contains the ordered work that remains.

## Product delivery status

The project is a governed pre-production MVP preparing for an operational
pilot, not a continuously scheduled production service.

- Product Phase 1, repository closeout: implementation and local validation are
  complete. Version-control closeout remains pending because commit and push
  require separate human instructions.
- Product Phase 2, continuous demand-data staging: complete locally for all 53
  months from 2022-01 through 2026-05. The demand quality gate passed every
  partition. Negative-fare warnings for 2025-01 through 2025-11 are
  non-blocking for demand and remain open for any future fare product.
- Product Phase 3, controlled release: the 22-fold staging backtest passed all
  release checks. Candidate SHA-256
  `00a1d628acc7e53d527ddd9be23cb664eb8098def9dd433408e176cd407c5eae`
  remains in `awaiting_human_approval`; it has not been promoted or published.

The next product decision is whether an authenticated human approves promotion
of that exact candidate. If approved, forecast generation for 2026-05-01,
forecast publication, and monitoring against May actuals remain distinct steps;
publication requires its own approval bound to the promoted model SHA. The
evidence and exact stop point are recorded in
[`development-log/2026-08-09.md`](development-log/2026-08-09.md).

## P0 — close the approval-gate slice

The non-core closure completed on 2026-08-05: the repository now has an inert,
checked approval template; `rolling_backtest` integration coverage for the
awaiting, approved, checksum-mismatch, and failed-model-gate paths; and
regressions proving malformed JSON and interrupted copies preserve production
and remove partial files.

The retention-location decision was documented on 2026-08-09. Exact approval
record bytes are retained outside the repository checkout under
`C:\ProgramData\NYCTaxi\approval-records\`, with pending, consumed, and rejected
states linked to the operational ledger run ID. This documentation does not
create the directory, change its permissions, or authorize an external action.

1. When self-hosted runner setup is separately authorized, create the approved
   retention root and apply the documented Windows filesystem permissions.
2. Verify workflow-dispatch behavior on the self-hosted Windows runner without
   executing production publication, including safe handling of the
   checkout-external approval path.
3. If either remaining check requires a core-file change, obtain specific human
   approval for the proposed files and validation plan before editing.

Acceptance signals:

- only the exact approved bytes can replace production;
- rejected or interrupted operations preserve the prior artifact;
- the workflow exposes a clear blocked status and never silently continues;
- approval evidence is attributable, contains no secret, retains its exact
  original bytes, and is not reused after a final run state.

## P1 — finish declared governance coverage

1. Decide whether to configure tracked capability artifacts.
2. Reconfirm that the declared empty capability-dependency graph is complete.
3. Keep control applicability and evidence references aligned as runtime paths
   evolve.
4. Add new reviewed evaluation cases only when they change a decision boundary,
   not to inflate a case count.

Acceptance signals:

- AgentGov has no deterministic failure;
- remaining WARN and ADVISORY findings have named owners and honest rationale;
- no governance coverage percentage is claimed without a denominator and
  applicability model.

## P2 — adopt AgentGov 0.3 after stable release

1. Wait for an approved, published AgentGov 0.3 release and migration-declared
   manifest.
2. Generate the exact two-workflow migration review inside NYC.
3. Human-review the permission diff and current/target dry-run evidence.
4. Merge the one-time migration only after the NYC project suite and governance
   checks pass.
5. Confirm the first trusted-main run reports `baseline_missing`, then confirm a
   later eligible run restores the exact baseline and reports an honest state.
6. Verify PR authors see only their change and required action while maintainers
   see trend and upgrade administration on trusted runs.

Stop conditions:

- undeclared repository migration, unexpected write permission, workflow drift,
  evidence digest mismatch, deterministic regression, or missing approval.

## P3 — demonstrate development-time value

1. Replay selected historical NYC changes through the proposed local AgentGov
   development check and the GitHub PR check.
2. Record which issue was discovered locally, which was discovered only in CI,
   false positives, and the action each finding caused.
3. Use the next real NYC change as the preferred live pilot; do not create a
   meaningless PR only to make the dashboard change.
4. Join project-test or runtime evidence only when the source and denominator
   are explicit. Do not claim that AgentGov caused a quality outcome.

Acceptance signals:

- developers receive relevant governance constraints before opening a PR;
- GitHub independently reproduces deterministic facts as the final backstop;
- `unchanged` is not presented as a benefit;
- a workflow-only upgrade is distinguished from a change to NYC business code.

## P4 — operational readiness

- register and verify the persistent `nyc-taxi` self-hosted runner when real
  scheduled operations are authorized;
- rehearse recovery for partial download, failed validation, failed promotion,
  rejected publication, and monitoring alert states;
- keep model, data, forecast, credential, and approval retention policies
  explicit before production use;
- require a separate human decision for every deployment or external production
  action.

No item on this page authorizes model promotion, forecast publication,
deployment, scheduled production execution, or AgentGov release activity.
