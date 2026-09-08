---
name: research-design-kickoff
description: Use when a Problem Navigator workflow is at research-design-kickoff and needs an initial or supplemental research brief.
---

# Research Design Kickoff

Contract marker: stage_gate: next_stage == research-design-kickoff.
Normative wrong-stage guard: wrong_stage: return=problem-navigator; artifact_writes=0; state_mutations=0.
Normative invalid-artifact guard: invalid_artifact: atomic_next_stage=STOPPED; blocking_reason.code=MISSING_OR_INVALID_ARTIFACT.

Read ../problem-navigator/references/workflow-control.md and the shared schema.
Schema: ../problem-navigator/references/artifacts.schema.json.
Validate workflow/frame identity, goal and scope. Wrong stage returns unchanged;
invalid input stops with known task IDs. Design questions only: no Provider name, route,
recommendation or selection in the brief. Do not search.

## Design by relevance

GENERAL selects relevant definitions, mechanisms, stakeholders, cases, constraints,
counterevidence. PRODUCT_SOFTWARE checks 产品形态 (product form), 关键资源 (critical
resource), 开源生态 (open-source ecosystem), 候选实现路径 (implementation path).
Explain merges/omissions; never impose four tasks/agents. PRD_ONLY needs product evidence
and feasibility constraints, not architecture selection. TECHNICAL_SPEC_ONLY emphasizes
current code/logs, versions, constraints, actual behavior and validation evidence.

Draft 1–12 initial tasks with stable unique RES-NNN IDs, theme_id, question, quality_bar,
stop_condition. Prefer primary support and counterevidence. Do not split merely for budget.
PROVIDED_MATERIAL adds task_kind and accessible project-relative material_refs; it has no
direction/domains/freshness. Capture conversation facts in a frame/material artifact first.
PUBLIC_WEB adds task_kind, direction: auto|news|semantic|academic|developer, domains: [],
freshness: ""|day|week|month|year; no material_refs on that task.
NONE permits material only; authorized Web workflows may mix both task kinds.
Revision-1 tasks have no supplemental_request_id.

## Initial handoff

Write research-brief.yaml with schema_version: 1, workflow_id, revision: 1, analysis_goal,
tasks. Then set workflow's research_brief ref, zero counts for exactly its task IDs and
next_stage: research-execution. Artifact files first and workflow last. Execution invokes
the shared init command before requiring its evidence draft. Present the questions but
only block on a material boundary uncertainty.

## Additional evidence

Use shared append with 1–4 new tasks and a bounded reason, current validated brief and
draft/package. Preserve old definitions/IDs/counts; zero counts only for new IDs. At most
16 tasks and the shared total budget apply. Later revisions are allowed; no revision-2 stop.
If readiness/selection provided supplemental_request, keep affected_candidate_ids closed
to the current evidence package and attach its matching request ID as supplemental_request_id.
For material requests collectively cover every carrier material_ref. PUBLIC_FACT questions
answer the requested gap/decision impact; no semantic-relevance engine.
UNDERSTAND/later-stage gaps may append directly without manufacturing readiness.

For an erroneous old claim use reopen rather than duplicating its task. Helper controls
initialize the draft, invalidate downstream refs and set execution. Follow shared
interruption rules. A substantive goal change starts a new frame; new relevant evidence
within scope does not. NONE never gains network permission from supplementation.
