---
name: solution-refinement
description: Refine a selected DECIDE direction into frozen semantic What and How without creating formal documents or implementation work.
---

# Solution Refinement

Contract marker: `stage_gate: next_stage == solution-refinement`.
Normative wrong-stage guard: `wrong_stage: return=problem-navigator; artifact_writes=0; state_mutations=0`.
Normative invalid-artifact guard: `invalid_artifact: atomic_next_stage=STOPPED; blocking_reason.code=MISSING_OR_INVALID_ARTIFACT`.

## Stage gate

Run only when the validated workflow has `next_stage: solution-refinement`. If it
does not, return to `problem-navigator` without reading downstream artifacts,
writing an artifact, or modifying state.

When it is this stage, validate the workflow, current `problem_frame`, current
`evidence_package`, and current `decision` against `../problem-navigator/references/artifacts.schema.json`.
They must share one workflow ID; the frame must be `DECIDE`; the decision must be
`SELECTED`, cite the current readiness/evidence revision, and select only supported
candidates. Validate current readiness and decision review through the shared helper,
including actual court case integrity on disk. Read only safe review receipts and the
final neutral decision; never load court papers or debate into main. Missing, unreadable, invalid, stale, or mismatched input is not a prompt
to reconstruct it. Atomically preserve the research state, set `next_stage: STOPPED`,
and write:

```yaml
blocking_reason:
  code: MISSING_OR_INVALID_ARTIFACT
  task_ids: [<every known affected task ID>]
```

Use `[]` only if no task ID is trustworthy. Do not guess, repair, or rerun this stage.

## Freeze the selected semantics

Read ../problem-navigator/references/workflow-control.md for current control operations
and delivery trims. It supersedes conflicting older recovery/acceptance rules.

Read only the accepted decision and cited evidence needed to keep its meaning true.
Do not reopen candidates, replace the selected direction, create a new candidate,
quietly cut scope to an MVP, or change a material goal. A material objective,
boundary, or profile change terminates this old workflow: set `next_stage: STOPPED`
with a truthful reason and ask the user to start a new workflow. It never silently
continues under a changed goal.

Create the current refined_solution from accepted scope/decision and explicit delegation
to draft; request a new decision only for material new semantics. Do not ask the user to
re-approve unchanged content just to advance stages. It has a stable refined_solution_id, incremented version on a
confirmed in-boundary correction, decision ID/version, definition, scope,
constraints, acceptance criteria, and user_confirmation_status (DRAFT or ACCEPTED).

When semantics have not yet been explicitly reviewed, use user_confirmation_status:
DRAFT, even if the user delegated drafting. Only actual acceptance of these semantics
or the final document containing exactly them changes it to ACCEPTED. Delegation is
permission to draft, not evidence that the user already reviewed the new content.

- `GENERAL`: freeze the complete solution definition: outcome, boundaries and
  non-goals, operating model or relationships where relevant, assumptions,
  dependencies, risks/exceptions, trade-offs, and verifiable acceptance criteria.
- `PRODUCT_SOFTWARE` with PRD_ONLY: freeze What, acceptance criteria and necessary
  feasibility constraints. Leave architecture choice open for the engineering team;
  do not require a complete How to deliver the requested PRD.
- `PRODUCT_SOFTWARE` with TECHNICAL_SPEC_ONLY: freeze the technical problem, observed
  behavior, system constraints, alternatives, selected design and validation criteria.
  Omit irrelevant product-market/UI requirements and do not invent a PRD baseline.
- Other `PRODUCT_SOFTWARE`: freeze **What** first—value, target users, in/out of scope,
  stable requirement IDs, and acceptance IDs. Record declared requirement IDs/statements in optional requirements entries
  {requirement_id, statement} for executable document trace checks. Only then freeze **How** under those
  constraints—system boundary, architecture direction, data/interface boundary,
  quality attributes, and operating constraints. Technical convenience may constrain
  feasibility; it must not redefine the product value or What.

An incorrect fact uses shared reopen on affected task IDs; a new evidence question uses
append. Both invalidate downstream refs and set research-execution. An unresolved value
uses resume --target decision-readiness-interview; decision conflict uses resume --target
adversarial-option-selection. Invoke the control before handoff, not a wrong-stage call.
This Skill does not research, rank, or choose.

## Output boundary and handoff

This is a semantic freeze, not formal documentation. Do not write a PRD, Technical
Solution Spec, formal report, solution Spec package, implementation plan, task list,
ticket, schedule, staffing plan, source-file list, implementation code, test code,
deployment command, migration command, or an external implementation handoff.

Write the artifact with its truthful DRAFT or ACCEPTED status atomically at its stable project-relative path, validate
it, then atomically set `artifact_refs.refined_solution` and
`next_stage: solution-documentation`. Hand off to `solution-documentation` and stop.
