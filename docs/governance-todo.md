# Governance follow-up register

This is a specialized register for unresolved AgentGov governance decisions. It
is not the general roadmap, current project status, or a source of agent
permissions. See [`development-plan.md`](development-plan.md) for durable
direction, [`current-development-status.md`](current-development-status.md) for
current reality, and [`../AGENTS.md`](../AGENTS.md) for authority.

## Owner and review trigger

- Owner: NYC Taxi platform maintainers
- Review when capability scope, runtime callers, governance evidence,
  dependencies, or AgentGov release semantics change.
- Current deterministic state: no AgentGov failures in the latest recorded
  2026-08-14 local check.

## Active decisions

1. Decide whether tracked capability artifacts would provide useful,
   reproducible evidence rather than generated noise.
2. Reconfirm that the declared empty capability-dependency graph reflects the
   real runtime and organizational dependency boundary.
3. Keep capability callers, contracts, provenance, control evidence, and
   evaluation references aligned when governed runtime paths change.
4. Add reviewed evaluation cases only when they exercise a real decision
   boundary; do not inflate case counts without behavioral value.

## Resolved decisions

- Model promotion and forecast publication require separate human approval
  records bound to exact artifact checksums. Scheduled operations stop after
  model validation unless a later action is separately authorized.
- Complete-grid and JFK/LaGuardia routing seeds are reviewed, the complete-grid
  golden example is approved, and negative-prediction preservation has a
  regression test.
- Python 3.11 is the declared runtime, aligned with CI and the locked development
  environment.
- Agent instructions distinguish deterministic checks from advisory findings
  and prohibit tests or governance evidence from authorizing production action.

## Safety boundary

Passing AgentGov, tests, static checks, model gates, or publication gates is
evidence only. It does not authorize production workflows, artifact replacement,
deployment, scheduling, or external-system mutation. This register cannot
override `AGENTS.md`.

## Verification

```powershell
agentgov check repository .
agentgov check agent-skills agent-skills
git diff --check
```
