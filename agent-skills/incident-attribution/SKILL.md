---
name: incident-attribution
description: Capture and review collaboration failures as evidence-based process learning without turning attribution into blame or automatic policy change. Use when unclear framing, weak handoff, unsupported judgment, execution mistakes, or verification gaps reveal how humans and agents should work better together. Do not use for ordinary product bugs, live service incidents, production remediation, or individual performance evaluation.
---

# Incident Attribution

## Goal

Turn a meaningful collaboration failure into a reviewable factual record,
provisional stage attribution, and proportionate corrective decision while
preserving uncertainty, dignity, and human control over governance changes.

## Required context

- Confirm that the learning concerns the collaboration process rather than an
  active operational incident. Use the repository's incident-response process
  first when service restoration or containment is still required.
- Read applicable repository instructions, approval boundaries, and the
  configured location for governance or incident-learning records.
- Gather sanitized evidence from the task, handoff, implementation, review,
  and validation without widening access or exposing private material.

## Inputs

- The active task and expected outcome.
- What was observed, where it appeared, and its immediate impact.
- Relevant instructions, decisions, diffs, tests, logs, reviews, or handoffs.
- The current recovery status and any proposed process change.

## Workflow

1. Capture an immediate factual record with date, task, observation, location,
   evidence references, impact, and recovery status. Do not assign blame or
   infer intent in this record.
2. Use the repository's configured record location. If none exists, prepare
   the proposed record in the handoff and request approval before creating a
   new governance directory or persistence convention.
3. Classify one or more provisional stages:
   - `problem_definition`: the goal, priority, constraints, or success criteria
     were incomplete or misleading;
   - `task_handoff`: scope, context, permissions, or validation expectations
     were lost between participants;
   - `reasoning_and_judgment`: analysis or planning was plausible but weakly
     grounded, insufficiently challenged, or overconfident;
   - `execution`: a tool, file, implementation, or test action was incorrect;
   - `verification`: review or validation did not test the relevant behavior,
     policy, evidence, or user expectation.
4. Produce an attribution closeout that separates facts, supported inferences,
   stage attribution, contributing roles, uncertainty, effective recovery
   actions, and candidate corrective actions.
5. Open a pattern review only for recurrence or when an accountable human asks
   for one. Do not promote one ordinary failure into a systemic pattern.
6. Give the pattern review one explicit outcome: approved corrective change,
   proposed change requiring approval, backlog item, no-change decision with
   rationale, or continued observation.
7. Treat approval of the review outcome and authorization to edit, commit,
   publish, deploy, or change an external system as separate decisions.

## Required checks

- The factual record contains observations and evidence, not blame, motive, or
  unsupported certainty.
- Attribution describes contributing behavior and roles; it does not rank
  people or substitute for performance management.
- Facts, inferences, judgments, and unknowns remain visibly distinct.
- Sensitive data, credentials, private prompts, unnecessary payloads, and
  private user information are excluded or safely redacted.
- Recovery successes and protective controls that worked are recorded along
  with failures.
- A proposed policy or protected-file change remains a proposal until the
  repository's required human approval is explicit.
- Operational response and collaboration learning remain separate even when
  both arise from the same event.

## Stop conditions

Stop and escalate when evidence is inaccessible, attribution would expose
sensitive data, participants dispute material facts, the review is being used
for personal blame, or the corrective action needs ungranted authority. Do not
manufacture consensus or infer intent to complete the record.

## Human escalation

Present disputed facts, available evidence, uncertainty, immediate risk, and
the smallest decision required. Ask an accountable human to confirm record
placement, pattern status, and any protected governance change separately.

## Expected output

Report the factual record location or proposed record, provisional stage
attribution, contributing roles, recovery result, candidate pattern, explicit
review outcome, unresolved disputes, and the next corrective action. State
which actions still require separate human approval.
