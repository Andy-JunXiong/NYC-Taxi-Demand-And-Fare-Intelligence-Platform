---
name: incident-response
description: Triage and contain an operational failure using evidence-first diagnosis, narrow remediation, and explicit escalation boundaries. Use when an alert, production error, failing CI check, smoke-test failure, or service degradation needs investigation. Do not use for routine feature development, planned deployment, or speculative architecture work.
---

# Incident Response

## Goal

Restore confidence in the affected behavior by classifying the incident,
preserving evidence, identifying the most supported cause, and applying only
an authorized narrow remedy.

## Required context

- Read the repository's incident, operations, and security instructions that
  apply to the affected system.
- Establish the environment, observed time window, impact, recent relevant
  changes, and available read-only evidence.
- Confirm which systems may be inspected and which actions require a human or
  a sanctioned deployment path.

## Inputs

- The alert, failing check, error, or observed symptom.
- Reproduction details and sanitized logs or traces.
- Current service state, relevant change history, and validation endpoints.

## Workflow

1. State incident mode, affected scope, current impact, and the first
   falsifiable hypothesis.
2. Preserve sanitized evidence before changing code or state.
3. Reproduce or verify the symptom with the least invasive read-only check.
4. Inspect in order: input shape, identifier mapping or normalization,
   routing or orchestration, then downstream rendering or storage.
5. Classify the cause as code, configuration, infrastructure, external
   dependency, data, permissions, or still unknown.
6. If authorized, apply the smallest reversible code or configuration patch;
   otherwise stop at a concrete remediation proposal.
7. Validate the affected path, a nearby regression path, and the safety rule
   most likely to be compromised by the incident.
8. Record what is restored, what remains uncertain, and what follow-up reduces
   recurrence.

## Required checks

- Evidence and timestamps support the stated classification.
- Logs and reports exclude credentials, private data, authorization material,
  and unsanitized payloads.
- The remedy does not weaken tests, approval gates, auditability, or security
  boundaries.
- External writes, deployments, permission changes, and destructive actions
  have separate explicit authorization.
- A failed or partial recovery is reported honestly and is not presented as a
  resolved incident.

## Stop conditions

Stop and escalate when investigation requires secrets, broader permissions,
destructive recovery, an unauthorized external write, an unclear blast radius,
or repeated remediation failure. Also stop when the evidence points outside
the repository's authorized control boundary.

## Human escalation

Provide impact, sanitized evidence, leading diagnosis, actions already taken,
the blocked or risky action, and the exact operator decision needed. Preserve
the distinction between observed facts, supported inferences, and unknowns.

## Expected output

Report incident status, impact, evidence, classification, root cause or leading
hypothesis, changes made, validation results, unresolved risk, required human
actions, and a focused prevention follow-up.
