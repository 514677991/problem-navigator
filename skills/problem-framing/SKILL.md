---
name: problem-framing
description: Use when a Problem Navigator workflow is at the problem-framing stage and needs its goal, content profile, scope, constraints, assumptions, and delivery endpoint confirmed.
---

# Problem Framing

## Stage boundary

Contract marker: `stage_gate: next_stage == problem-framing`.
Normative wrong-stage guard: `wrong_stage: return=problem-navigator; artifact_writes=0; state_mutations=0`.
Normative invalid-artifact guard: `invalid_artifact: atomic_next_stage=STOPPED; blocking_reason.code=MISSING_OR_INVALID_ARTIFACT`.

Run only when the validated workflow has `next_stage: problem-framing`. If invoked at any other stage, return control to `problem-navigator` without modifying state.

This stage clarifies and records the problem; it does not inspect MCP configuration, search, design research tasks, evaluate candidates, recommend a solution, or generate evidence. It produces only the current `problem-frame.yaml`.

Before framing, validate the workflow against `../problem-navigator/references/artifacts.schema.json`. If the workflow is missing, unparsable, or inconsistent, do not guess（不得猜测）or invent state. Atomically write:

```yaml
blocking_reason:
  code: MISSING_OR_INVALID_ARTIFACT
  task_ids: []
next_stage: STOPPED
```

Then stop and return to the entry Skill.

## Decide only the frame

Read ../problem-navigator/references/workflow-control.md. Its 2.1 recovery,
authorization, mixed-evidence and delivery rules supersede older conflicting rules.

Set `analysis_goal` once:

- `UNDERSTAND` for explanation, diagnosis, situation mapping, or an evidence summary.
- `DECIDE` for choosing, ranking, recommending, approving, or forming an actionable solution.
- 从零开始把产品、软件或其他想法形成完整方案时，默认 `DECIDE`.

When this distinction is unclear, 只问 `analysis_goal` 这一项. Do not open a questionnaire or add another mode system. Draft other fields from the user's supplied meaning and let the confirmation gate expose any correction.

Set `content_profile` independently:

- General strategy, operations, career, organization, policy, procurement, or other non-product/system questions map to `GENERAL`.
- Both `PRODUCT` and `SOFTWARE` inputs map to the single `PRODUCT_SOFTWARE` profile. Never persist PRODUCT or SOFTWARE as separate profiles.

The profile does not select a backend and does not enter the workflow YAML.

Choose the endpoint from the requested deliverable: UNDERSTAND uses RESEARCH_REPORT;
GENERAL or full-product DECIDE defaults to FORMAL_DOCUMENT. A product-needs-only
request uses PRD_ONLY. Pure architecture/technical comparison or software diagnosis
uses TECHNICAL_SPEC_ONLY; don't impose a PRD. FINAL_SPEC_PACKAGE applies only when
requested or when independently reviewable units materially help, confirmed in scope.
These are scope trims in the same workflow, not additional profiles.

## Confirmation and artifact

Present a concise frame containing the problem, outcome, scope/non-goals, constraints,
assumptions, endpoint, analysis_goal and content_profile. Reuse explicit user instructions
that already establish or delegate this scope. Ask only about a material ambiguity;
do not demand a separate ritual confirmation after a clear instruction to proceed.
Silence never confirms newly invented scope. Record ACCEPTED only from actual explicit
instructions/acceptance; preserve the source of that scope in the human explanation.

After explicit acceptance, create this single artifact at `.problem-navigator/artifacts/<workflow_id>/problem-frame.yaml`:

```yaml
schema_version: 1
workflow_id: <same workflow UUID>
problem_frame_id: <stable ID for this frame>
problem_frame_version: 1
analysis_goal: UNDERSTAND | DECIDE
content_profile: GENERAL | PRODUCT_SOFTWARE
clarified_problem: <confirmed problem statement>
goal: <what the analysis must enable>
scope: []
non_goals: []
constraints: []
assumptions: []
delivery_endpoint: <confirmed report or specification endpoint>
user_confirmation_status: ACCEPTED
```

Use a stable `problem_frame_id`. A user-confirmed correction increments `problem_frame_version` and atomically replaces the same stable file; do not keep a version graph.

## Atomic handoff order

The only success order is:

1. 原子写入 `problem-frame.yaml` through a same-directory temporary file and replace.
2. Only after that succeeds, 更新 workflow YAML atomically with the same accepted `analysis_goal`, the relative `artifact_refs.problem_frame` path, and `next_stage: research-design-kickoff`.
3. Hand off to `research-design-kickoff` and stop this stage.

If artifact writing fails, leave the workflow reference and stage unchanged. Never write the YAML reference first, never store `content_profile` in the workflow, and never begin research from this Skill.
