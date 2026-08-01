# Governance follow-up

## Next review

- Target date: 2026-07-25
- Owner: NYC Taxi platform maintainers
- Status: In progress

## Decisions and work remaining

1. **Resolved 2026-07-25:** production model promotion and forecast publication
   require separate human approval records bound to the exact artifact checksum.
   Scheduled operations stop after model validation.
2. **Resolved 2026-08-01:** the complete-grid and JFK/LaGuardia routing seeds
   are reviewed, the complete-grid golden example is approved, and the
   negative-prediction failure case has a publication-preservation regression
   test. The first evaluation baseline is recorded as `baseline_ready`.
3. **Resolved 2026-08-01:** Python 3.11 is declared in `.python-version`,
   matching CI, and the test suite has been verified in a side-by-side Python
   3.11.9 environment. The existing `.venv` was preserved.
4. Decide whether to configure tracked capability artifacts and whether the
   empty declared capability-dependency graph is complete.

## Safety boundary

Passing AgentGov, tests, static checks, model gates, or publication gates is
evidence only. It does not authorize running production workflows, replacing
production artifacts, deploying, scheduling, or mutating external systems.

## Suggested verification

```powershell
$env:PYTHONPATH = (Resolve-Path 'agent-governance-starter\src').Path
python -m agentgov check repository .
python -m agentgov check agent-skills agent-skills
git diff --check
```

After an approved Python environment is available:

```powershell
python -m pytest -q
```
