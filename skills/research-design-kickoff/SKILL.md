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
invalid input stops with known task IDs. Design questions only: no search Provider
choice, backend route, recommendation or selection in the brief. Named products,
suppliers, APIs or repositories may be research subjects. Do not search.

## Design by relevance

GENERAL selects themes that answer this question: relevant definitions, mechanisms,
stakeholders, historical change, cases, constraints, boundaries or counterevidence.
Do not read the product guide, collect product inputs or require four themes for
GENERAL. A narrow supplied-material question can have one task. UNDERSTAND asks for
an explanation and its limits, without manufactured candidates or recommendations.

For PRODUCT_SOFTWARE, read `references/product-research-guide.md`. Carry the six-input
summary into `design.product_context`: product definition, target market, competitor
or substitute anchors, critical resources, reuse intention and capability/module map.
Use a short labeled text identifying known inputs, needed user clarification, research
gaps and inapplicability with reasons. The accepted frame remains authoritative;
do not invent or silently revise its scope. For clarification, block only on a material
user-controlled boundary uncertainty; unknown public facts become questions.

Use stable product themes `product-form`, `critical-resources`,
`open-source-ecosystem`, `implementation-path`; add relevant themes when needed.
Expand applicable themes using the guide's concrete dimensions, not labels alone.
PRD_ONLY needs product evidence and feasibility constraints, not architecture
selection. TECHNICAL_SPEC_ONLY emphasizes code/logs, versions, interfaces, actual
behavior and validation evidence, omitting unrelated product discovery with a reason.

Every newly designed brief has `design.theme_coverage`: rows with `theme_id`,
`treatment: RESEARCH|MERGED|NOT_APPLICABLE`, `rationale` and `task_ids`. List all four
product themes for PRODUCT_SOFTWARE; GENERAL lists only its relevant themes and has
no `product_context`. RESEARCH points to the covering tasks; MERGED explains the
combination and points to the task(s) carrying it under another theme. NOT_APPLICABLE
explains the scope exclusion and has empty task_ids. Never impose four tasks or agents.

## Executable tasks

Draft 1–12 initial tasks with stable unique RES-NNN IDs. Each new task has:

- `theme_id` and `purpose`: the evidence use or gap this task addresses.
- `question`: enough accepted context and bounded subquestions for an independent
  researcher to begin; cite accessible material/frame references rather than copying
  unrelated conversation. Choose dimensions that can change the answer.
- `expected_output`: a usable comparison, explanation or evidence map and its needed
  contents, without prescribing a separate canonical artifact for every task.
- `quality_bar`: observable coverage and source/locator requirements for critical
  claims, relevant contrary evidence and unresolved conflicts; no vague "high quality".
- `stop_condition`: when those questions are answered, or when the shared access,
  failure or budget limit requires an explicit gap and its impact. Do not equate a
  task stopped at a limit with complete evidence.
- `depends_on`: existing task IDs whose results are genuinely needed first, otherwise
  `[]`. Do not manufacture a dependency chain for independent questions.

Task depth follows scope; a simple material question can express each field briefly.
Use primary support appropriate to the claim, and distinguish documented promises
from observed behavior. Plan counterevidence around important claims, not a fixed
number of objections. For DECIDE, questions should distinguish alternatives under
relevant themes; an unstudied candidate is an evidence gap, not an inferior candidate.
Do not split merely for budget. Use the shared execution protocol for isolation and
dispatch; do not create a second budget or research-state system in the brief.

PROVIDED_MATERIAL adds task_kind and accessible project-relative material_refs; it has no
direction/domains/freshness. Capture conversation facts in a frame/material artifact first.
PUBLIC_WEB adds task_kind, direction: auto|news|semantic|academic|developer, domains: [],
freshness: ""|day|week|month|year; no material_refs on that task.
NONE permits material only; authorized Web workflows may mix both task kinds.
Revision-1 tasks have no supplemental_request_id.

## Initial handoff

Write research-brief.yaml with schema_version: 1, workflow_id, revision: 1, analysis_goal,
problem_frame_id and problem_frame_version copied from the current accepted frame,
design and tasks. Then set workflow's research_brief ref, zero counts for exactly its task IDs and
next_stage: research-execution. Artifact files first and workflow last. Execution invokes
the shared validate-brief --require-design command for this new brief, then init before
requiring its evidence draft. Present the questions but
only block on a material boundary uncertainty.

## Additional evidence

Use shared append with 1–4 new tasks and a bounded reason, current validated brief and
draft/package. Preserve old definitions/IDs/counts; zero counts only for new IDs. At most
16 tasks and the shared total budget apply. Later revisions are allowed; no revision-2 stop.
New tasks use the executable-task fields above. If design exists, update its theme
coverage to include the supplement while preserving accepted product scope. A legacy
brief without design may continue or receive supplements; do not claim its old tasks
were redesigned or fabricate retroactive coverage metadata.
If readiness/selection provided supplemental_request, keep affected_candidate_ids closed
to the current evidence package and attach its matching request ID as supplemental_request_id.
For material requests collectively cover every carrier material_ref. PUBLIC_FACT questions
answer the requested gap/decision impact; no semantic-relevance engine.
UNDERSTAND/later-stage gaps may append directly without manufacturing readiness.

For an erroneous old claim use reopen rather than duplicating its task. Helper controls
initialize the draft, invalidate downstream refs and set execution. Follow shared
interruption rules. A substantive goal change starts a new frame; new relevant evidence
within scope does not. NONE never gains network permission from supplementation.
