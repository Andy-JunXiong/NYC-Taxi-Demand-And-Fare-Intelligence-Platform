# Governance follow-up

## Next review

- Target date: 2026-07-25
- Owner: NYC Taxi platform maintainers
- Status: Open

## Decisions and work remaining

1. Decide whether production model promotion and forecast publication require a
   separate human approval checkpoint. The current implementation promotes
   `production.joblib` after deterministic model gates pass, and the scheduled
   operations workflow can continue directly to forecast publication.
2. Review the three draft seed cases under
   `evaluation/nyc-hourly-zone-demand-forecast/seed-cases/`. Keep
   `needs_seed_cases` until reviewed seed evidence, an approved golden example,
   a reviewed failure case, and baseline approval exist.
3. Select and declare the supported local Python version. CI uses Python 3.11;
   the available local interpreter is Python 3.12, and the existing `.venv`
   points to an unavailable Python 3.13 installation. Rebuild side by side
   rather than deleting or overwriting the existing environment.
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
