# NYC Taxi current development status

Updated 2026-08-14. This is the canonical snapshot of current implementation
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

## Codex-run validation

- Complete repository suite: `88 passed`, with one existing joblib/loky
  physical-core detection warning.
- Immutable-publication focused suite: `30 passed`.
- Publication failure probe: all three injected failures preserved the previous
  canonical pointer; visible orphan bundles were complete and noncanonical.
- AgentGov repository check: `17 PASS`, `0 FAIL`, `1 WARN`, `4 ADVISORY`.
- AgentGov agent-skills check: `4 PASS`, `0 FAIL`.

These are dated local results from 2026-08-14. They are evidence, not authority
to execute a production operation.

## User-reported validation

No separate browser, self-hosted-runner, production, or cross-provider
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

- Diagnose the 13 candidate-v2 days that did not beat the previous-week
  baseline and the remaining recursive-horizon degradation using only
  pre-forecast information.
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

Prepare a review-ready decision memo for daily 24-hour recursive stability. It
should classify daily win rate, worst-day degradation, daily drift pass rate,
and horizon degradation as proposed release criteria, advisory evidence, or
diagnostic-only evidence. It must use the existing shadow results, expose the
tradeoffs, avoid fitting thresholds to one month, and stop for human review
before any gate, model, promotion, or publication change.

## Recent evidence

- [`development-log/2026-08-14.md`](development-log/2026-08-14.md)
- [`development-log/2026-08-09.md`](development-log/2026-08-09.md)
- [`publication-failure-safety-audit-2026-08-14.md`](publication-failure-safety-audit-2026-08-14.md)
- [`policy-intervention-evidence.md`](policy-intervention-evidence.md)
- [`agent-operator-e2e-evidence-2026-08-14.md`](agent-operator-e2e-evidence-2026-08-14.md)
