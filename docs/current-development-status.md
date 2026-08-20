# NYC Taxi current development status

Updated 2026-08-20. This is the canonical snapshot of current implementation
and validation reality. Durable direction belongs in
[`development-plan.md`](development-plan.md); permissions and execution rules
belong only in [`../AGENTS.md`](../AGENTS.md); dated evidence belongs in
[`development-log/`](development-log/).

## Product state

The repository is a governed pre-production MVP preparing for an operational
pilot. It is not a continuously scheduled production service. Model promotion,
forecast publication, deployment, scheduling, and other external mutations
remain separate human-authorized operations.

The current candidate-v2 decision is `HOLD`. It improved aggregate May 2026 and
Memorial Day behavior, but it beat the previous-week baseline on only 18 of 31
daily recursive forecasts. It has not been promoted or published.

## Recently completed

- Forecast publication now writes a complete immutable release bundle and
  changes canonical state with one atomic `latest.json` replacement.
- Monitoring and operational monitoring resolve and verify the canonical
  pointer, bounded bundle paths, artifact digests, lineage identity, and gate.
- Controlled intervention tests cover approval, exact-digest binding, forecast
  validation, and airport/event/global routing decisions.
- A sandboxed Agent Operator E2E harness completed two independent fresh-context
  Codex runs without changing protected files or crossing the approval boundary.
- `AGENTS.md` now requires every completed feature handoff to report completed
  work, short- and long-term benefits, the next feature, and their connection.
- Development documentation now separates durable plan, current status, dated
  evidence, and agent authority.
- The maintainer accepted the recursive-stability memo's evidence roles: daily
  win rate and worst-day degradation are proposed release criteria, daily drift
  pass rate is advisory evidence, and the current clock-hour-confounded horizon
  profile is diagnostic-only. No numeric gate was introduced.
- A bounded attribution packet localizes the 13 candidate-v2 losses to the
  ordinary non-airport/global path and high-volume Manhattan zones. It records
  descriptive hypotheses and explicitly makes no causal or release claim.

## Codex-run validation

- Recursive-stability decision slice, 2026-08-20: the leakage, recursive-shadow,
  and model-quality focused suite passed `14` tests, with the existing
  joblib/loky physical-core detection warning.
- Loss-day attribution, 2026-08-20: candidate v2 was replayed observationally
  across `82,056` losing-day zone-hour rows; all 13 loss labels reproduced, and
  the 13-row pre-forecast table plus the drift cross-tab passed exact assertions.
- Complete repository suite, rerun 2026-08-20: `88 passed`, with one existing
  joblib/loky physical-core detection warning.
- Immutable-publication focused suite: `30 passed`.
- Publication failure probe: all three injected failures preserved the previous
  canonical pointer; visible orphan bundles were complete and noncanonical.
- AgentGov repository check: `17 PASS`, `0 FAIL`, `1 WARN`, `4 ADVISORY`.
- AgentGov agent-skills check: `4 PASS`, `0 FAIL`.

The test results are dated local results from 2026-08-20; the governance results
remain dated 2026-08-14 evidence because AgentGov is not installed in either
currently available Python environment. They are evidence, not authority to
execute a production operation.

## User-reported validation

- On 2026-08-20, the maintainer accepted all four metric-role classifications in
  the recursive-stability memo. This is a human release-evidence decision, not
  model validation or approval of candidate v2.
- No separate browser, self-hosted-runner, production, or cross-provider
  validation has been reported for the latest publication-safety and document
  lifecycle changes.

## Pending validation

- Run the sandboxed Agent Operator scenario with a distinct Claude or DeepSeek
  operator when an approved CLI is available, then compare the same invariants.
- Verify checkout-external approval-record handling on the persistent Windows
  runner without executing model promotion or forecast publication.
- Human-review whether daily win rate, worst-day degradation, and daily drift
  pass rate are release criteria, advisory evidence, or both.

## Incomplete

- Test the descriptive Manhattan/global-model and recent-demand hypotheses on
  disjoint out-of-time periods; the May attribution packet does not establish a
  causal explanation.
- Separate clock hour from recursive horizon before claiming horizon
  degradation or proposing a horizon release statistic.
- Establish deterministic model-package identity or explicitly version the
  serialization environment before treating rebuilt bytes as an equivalent
  artifact.
- Decide whether to configure tracked AgentGov capability artifacts and confirm
  that the declared empty capability-dependency graph is complete.
- Resolve the non-blocking 2025 negative-fare warnings before claiming an
  operational fare-intelligence product.
- Complete Sydney evidence requirements before considering its release gate
  complete.

## Active risks and stop conditions

- Do not infer new model-release thresholds from the May sample alone.
- Do not transfer approval between semantically similar but byte-different
  model packages.
- Do not treat a passing static, governance, model, forecast, or monitoring
  check as permission to promote, publish, deploy, or schedule.
- Stop before a core-file change unless the human has approved the exact files
  and validation plan.

## Next slice

Prepare a review-ready, pre-registered recursive evaluation specification. It
should select multiple disjoint out-of-time periods without inspecting their
outcomes, use staggered forecast origins to separate clock hour from horizon,
and state how the accepted daily criteria and advisory drift evidence will be
reported. Stop for maintainer review before core-file changes, threshold
selection, model training, promotion, or publication.

## Recent evidence

- [`recursive-stability-decision-memo-2026-08-20.md`](recursive-stability-decision-memo-2026-08-20.md)
- [`recursive-loss-day-attribution-2026-08-20.md`](recursive-loss-day-attribution-2026-08-20.md)
- [`development-log/2026-08-20.md`](development-log/2026-08-20.md)
- [`development-log/2026-08-14.md`](development-log/2026-08-14.md)
- [`development-log/2026-08-09.md`](development-log/2026-08-09.md)
- [`publication-failure-safety-audit-2026-08-14.md`](publication-failure-safety-audit-2026-08-14.md)
- [`policy-intervention-evidence.md`](policy-intervention-evidence.md)
- [`agent-operator-e2e-evidence-2026-08-14.md`](agent-operator-e2e-evidence-2026-08-14.md)
