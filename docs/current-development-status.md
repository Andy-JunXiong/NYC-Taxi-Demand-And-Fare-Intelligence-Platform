# NYC Taxi current development status

Updated 2026-08-24. This is the canonical snapshot of current implementation
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
- A proposed recursive-evaluation pre-registration freezes four disjoint
  out-of-time blocks, 96 staggered 24-hour origins, accepted metric roles, and
  confirmatory reporting rules without inspecting new outcomes or defining a
  numeric gate.
- The Showcase now includes a responsive `/review` surface that turns the
  pre-registration into a decision-first timeline, origin-rotation visual,
  metric-role summary, and explicit non-production boundary. It records no
  approval and performs no external write.
- The recursive shadow evaluator now preserves arbitrary UTC-naive hourly
  origins, supports a deterministic coprime origin-hour step, exposes the
  pre-registered step through the CLI, reports origin and horizon/clock
  crossing evidence, and fails closed on incomplete target-hour actuals.
- Staggered recursive evaluation now fails closed unless it is bound to the
  canonical executable JSON plan, the exact candidate model bytes, and one
  named plan block. Both identities are verified before model deserialization
  or outcome access and re-verified before atomic report replacement; legacy
  midnight shadows are marked `unbound_exploratory`.
- A read-only recursive-evaluation readiness preflight now verifies the bound
  plan and model, every declared Silver digest, Gold identity and schema,
  quality-gate coverage, key integrity, and the exact required-hour window. It
  never deserializes the model, calculates outcomes, writes an evaluation
  report, or permits promotion.
- The TLC downloader now performs a body-free official-source availability
  check before any range download. HTTP `403`/`404` is reported as structured
  `source_not_available`; if any requested month is absent, no month is
  downloaded and the monthly governance workflow stops before Silver, quality,
  Gold, or lineage writes.

## Codex-run validation

- Recursive-stability decision slice, 2026-08-20: the leakage, recursive-shadow,
  and model-quality focused suite passed `14` tests, with the existing
  joblib/loky physical-core detection warning.
- Loss-day attribution, 2026-08-20: candidate v2 was replayed observationally
  across `82,056` losing-day zone-hour rows; all 13 loss labels reproduced, and
  the 13-row pre-forecast table plus the drift cross-tab passed exact assertions.
- Complete repository suite, rerun 2026-08-20: `88 passed`, with one existing
  joblib/loky physical-core detection warning.
- Recursive pre-registration, 2026-08-24: the block/origin crossing assertions,
  relative documentation links, and whitespace checks passed; the focused
  recursive/event suite passed `11` tests and the complete suite passed `88`
  tests with the existing joblib/loky physical-core detection warning. No model
  evaluation was run because the design awaits review and later governed data.
- Showcase review UI, 2026-08-24: the vinext build completed, all `3` rendered
  HTML tests passed, ESLint returned zero errors with four pre-existing
  `<img>` optimization warnings on the case-study page, and local headless
  Chrome checks passed for desktop and responsive single-column layouts.
- Staggered recursive evaluator, 2026-08-24: the matched recursive suite passed
  `10` tests, the leakage/model-quality focused suite passed `19`, and the
  complete repository suite passed `93`, with the existing joblib/loky
  physical-core detection warning.
- Recursive evaluation identity binding, 2026-08-24: the canonical plan digest
  independently reproduced as
  `d510a9e49d417e194fbed4d1de9b5ba07ca6593365236c88cec5143f539e166d`;
  the matched suite passed `19` tests, the recursive/forecast/quality focused
  suite passed `28`, and the complete repository suite passed `102`, with the
  existing joblib/loky physical-core detection warning. Failure-injection tests
  preserved the prior report across plan and model identity changes.
- Block A readiness preflight, 2026-08-24: the matched suite passed `6` tests
  and the complete repository suite passed `108`, with the existing joblib/loky
  physical-core detection warning. A real read-only preflight authenticated the
  frozen candidate, plan, `53` Silver sources, Gold artifact, and quality gate,
  then correctly returned `blocked`: `595` of the `763` required hours are not
  present because governed Gold ends at `2026-05-31T23:00:00`.
- June 2026 governed-data extension attempt, 2026-08-24: the bounded monthly
  workflow stopped at the official TLC download with HTTP `403`. The official
  2026 catalog currently lists Yellow Taxi files only through May and states
  that monthly files are typically published with a two-month delay. No partial
  file, manifest entry, Silver partition, or quality report was created; the
  prior Gold and quality-gate digests remained unchanged.
- TLC source-availability gate, 2026-08-24: a real check returned HTTP `200`
  and content length for 2026-05, and structured `source_not_available` for
  2026-06. The downloader suite passed `10` tests, the directly related data
  and governance suite passed `13`, and the complete repository suite passed
  `113`, with the existing joblib/loky physical-core detection warning.
- Immutable-publication focused suite: `30 passed`.
- Publication failure probe: all three injected failures preserved the previous
  canonical pointer; visible orphan bundles were complete and noncanonical.
- AgentGov repository check: `17 PASS`, `0 FAIL`, `1 WARN`, `4 ADVISORY`.
- AgentGov agent-skills check: `4 PASS`, `0 FAIL`.

The test results above are dated local evidence from the dates named in each
entry. The governance results remain dated 2026-08-14 evidence because AgentGov
is not installed in either currently available Python environment. They are
evidence, not authority to execute a production operation.

## User-reported validation

- On 2026-08-24, the maintainer declared the day's work complete and authorized
  the related documentation closeout, commit, and normal push to GitHub `main`.
  This delivery authorization does not permit model evaluation, promotion,
  publication, deployment, scheduling, or another external mutation.
- On 2026-08-24, the maintainer authorized the previously proposed bounded
  June 2026 download, governed rebuild, and read-only Block A preflight. This
  did not authorize model evaluation, promotion, publication, or deployment.
- On 2026-08-24, the maintainer specifically approved modifications to
  `src/nyc_taxi/model_validation.py`,
  `tests/test_recursive_shadow_evaluation.py`, and creation of
  `evaluation/recursive-evaluation-plan-2026-08-24.v1.json` for fail-closed
  model/plan identity binding. This did not authorize executing Blocks A-D or
  any production operation.
- On 2026-08-24, the maintainer specifically approved edits to
  `src/nyc_taxi/model_validation.py` and
  `tests/test_recursive_shadow_evaluation.py` to implement the staggered-origin
  evaluator. This did not authorize an evaluation or production operation.
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
- Retry the already authorized June 2026 governed-data extension only after the
  official TLC catalog publishes that exact Yellow Taxi partition, then rerun
  the read-only Block A preflight. A successful preflight must still not
  automatically start evaluation.

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
- Triage the Showcase dependency audit before any deployment; the locked
  install reported `21` findings (`1` low, `4` moderate, `16` high). No forced
  or breaking dependency upgrade was attempted in this slice.

## Active risks and stop conditions

- Do not infer new model-release thresholds from the May sample alone.
- Do not transfer approval between semantically similar but byte-different
  model packages.
- Do not treat a passing static, governance, model, forecast, or monitoring
  check as permission to promote, publish, deploy, or schedule.
- Stop before a core-file change unless the human has approved the exact files
  and validation plan.

## Next slice

Use the new body-free availability command to check the exact 2026-06 Yellow
Taxi Parquet. Once it reports `ready`, retry the already authorized bounded
monthly workflow followed only by the read-only Block A preflight. Do not
substitute another month or start Block A evaluation, threshold selection,
training, promotion, or publication.

## Recent evidence

- [`recursive-evaluation-preregistration-2026-08-24.md`](recursive-evaluation-preregistration-2026-08-24.md)
- [`recursive-evaluation-identity-binding-design-2026-08-24.md`](recursive-evaluation-identity-binding-design-2026-08-24.md)
- [`development-log/2026-08-24.md`](development-log/2026-08-24.md)
- [`recursive-stability-decision-memo-2026-08-20.md`](recursive-stability-decision-memo-2026-08-20.md)
- [`recursive-loss-day-attribution-2026-08-20.md`](recursive-loss-day-attribution-2026-08-20.md)
- [`development-log/2026-08-20.md`](development-log/2026-08-20.md)
- [`development-log/2026-08-14.md`](development-log/2026-08-14.md)
- [`development-log/2026-08-09.md`](development-log/2026-08-09.md)
- [`publication-failure-safety-audit-2026-08-14.md`](publication-failure-safety-audit-2026-08-14.md)
- [`policy-intervention-evidence.md`](policy-intervention-evidence.md)
- [`agent-operator-e2e-evidence-2026-08-14.md`](agent-operator-e2e-evidence-2026-08-14.md)
