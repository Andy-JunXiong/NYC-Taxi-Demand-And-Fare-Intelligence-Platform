# NYC Taxi development plan

Updated 2026-08-14. This document contains durable direction, priority tracks,
and decision gates. It does not report current implementation status, recent
session history, or permissions. See
[`current-development-status.md`](current-development-status.md) for current
reality and [`../AGENTS.md`](../AGENTS.md) for execution authority.

## Product direction

Develop a reproducible taxi-demand and fare-intelligence platform that turns
governed NYC and Sydney data into auditable analytics, model evaluation, and
bounded forecast products. Advance from a governed pre-production MVP toward an
operational pilot without coupling evidence generation to model promotion,
forecast publication, deployment, or scheduling.

The central product risk is an apparently successful aggregate model hiding
unstable daily, event, market, or recursive-horizon behavior. Product progress
therefore prioritizes decision-quality evidence, exact artifact identity,
fail-closed publication, and explicit human release decisions.

## P0 — define recursive-stability decision boundaries

Establish how daily 24-hour recursive evidence affects model release decisions
before training or promoting another candidate.

Outcomes:

1. classify daily win rate, worst-day degradation, daily drift pass rate, and
   horizon degradation as release criteria, advisory evidence, or diagnostic
   evidence;
2. diagnose losing days and horizon degradation using only information
   available before each forecast;
3. prevent threshold fitting to one observed month; and
4. train and shadow-evaluate a new candidate only after the decision boundary
   and model-package identity are reviewed.

Acceptance signals:

- the decision memo exposes metric tradeoffs and sample limitations;
- deterministic gates remain separate from advisory judgment;
- no threshold is silently weakened or introduced from one sample; and
- promotion and publication remain separately approved actions.

## P1 — close controlled-release operational readiness

Complete the environment-dependent approval and runner checks without executing
a production mutation.

Outcomes:

1. establish deterministic model-package identity or explicitly version the
   serialization environment;
2. create the approved external approval-record retention root and permissions
   only when separately authorized;
3. verify workflow-dispatch handling of checkout-external approval paths on the
   persistent Windows runner without promoting or publishing; and
4. rehearse blocked and failed approval states with attributable ledger evidence.

Acceptance signals:

- only exact approved bytes can replace production;
- rebuilt bytes cannot inherit an earlier approval;
- rejected or interrupted operations preserve the previous artifact;
- approval records remain attributable, unchanged, non-secret, and single-use;
  and
- the workflow exposes a clear blocked state and never silently continues.

## P2 — finish declared governance coverage

Keep governance declarations aligned with real runtime paths and evidence.

Outcomes:

1. decide whether to configure tracked capability artifacts;
2. reconfirm that the declared empty capability-dependency graph is complete;
3. keep control applicability and evidence references aligned as code evolves;
   and
4. add reviewed evaluation cases only when they exercise a decision boundary.

Acceptance signals:

- AgentGov has no deterministic failure;
- WARN and ADVISORY findings have named owners and honest rationale;
- coverage claims state their denominator and applicability model; and
- static governance results are not presented as proof of control effectiveness.

## P3 — evolve AgentGov after a stable release

Adopt a future AgentGov release only through an explicit, evidence-backed
migration.

Outcomes:

1. wait for an approved published release and migration-declared manifest;
2. generate the exact workflow and permission diff inside this repository;
3. review current and target dry-run evidence before merge;
4. verify trusted-main baseline initialization and later restoration; and
5. distinguish workflow-only governance changes from NYC business-code changes.

Stop on undeclared migration, unexpected write permission, workflow drift,
evidence-digest mismatch, deterministic regression, or missing approval.

## P4 — demonstrate development-time value

Use real changes rather than synthetic activity to evaluate whether governance
feedback improves developer decisions.

Outcomes:

1. replay selected historical changes through local and GitHub checks;
2. record which issue was discovered locally, only in CI, or was a false
   positive, plus the action it caused;
3. use the next real change as the preferred live pilot; and
4. join project-test or runtime evidence only when source and denominator are
   explicit.

Acceptance signals:

- developers receive relevant constraints before opening a pull request;
- GitHub independently reproduces deterministic facts as a backstop;
- `unchanged` is not presented as a benefit; and
- no causal quality claim is made without supporting evidence.

## P5 — broader product and pilot readiness

Prepare demand, fare, Sydney, and operations tracks for an explicitly authorized
pilot.

Outcomes:

- resolve negative-fare warnings before treating fare intelligence as an
  operational product;
- complete Sydney's distinct governed-source evidence requirement;
- register and verify the persistent `nyc-taxi` runner when authorized;
- rehearse recovery for download, validation, promotion, publication, and
  monitoring failures; and
- make retention policy explicit for data, models, forecasts, approvals, and
  credentials.

## Cross-cutting decision rules

- Historical notebook results are evidence, not current operational advice.
- Observational or shadow evidence cannot promote or publish an artifact.
- Model promotion, forecast publication, deployment, and scheduling remain
  separate decisions.
- A passing test or gate is evidence only; it never expands authority.
- Current completion, pending validation, and the next executable slice belong
  in `current-development-status.md`, not in this plan.

Nothing in this document authorizes a core-file edit, production operation,
external mutation, commit, push, release, or deployment.
