# NYC Taxi remaining development plan

Updated 2026-08-02. Completed work stays in the development record; this page
contains the ordered work that remains.

## P0 — close the approval-gate slice

1. Add a documented approval-record schema or checked template for
   `model_promotion` and `forecast_publication`.
2. Add integration tests around `rolling_backtest` for the awaiting, approved,
   checksum-mismatch, and failed-model-gate paths.
3. Verify workflow-dispatch behavior on the self-hosted Windows runner without
   executing production publication.
4. Confirm that approval files are retained as auditable evidence without
   storing credentials, private data, generated models, or runtime outputs in
   Git.
5. Review error handling for malformed JSON and filesystem failures so an
   interrupted promotion cannot leave an ambiguous production artifact.

Acceptance signals:

- only the exact approved bytes can replace production;
- rejected or interrupted operations preserve the prior artifact;
- the workflow exposes a clear blocked status and never silently continues;
- approval evidence is attributable and contains no secret.

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
