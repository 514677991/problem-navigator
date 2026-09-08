---
name: solution-documentation
description: Project frozen solution semantics into an accepted formal report or one product/software document package.
---

# Solution Documentation

Contract marker: `stage_gate: next_stage == solution-documentation`.
Normative wrong-stage guard: `wrong_stage: return=problem-navigator; artifact_writes=0; state_mutations=0`.
Normative invalid-artifact guard: `invalid_artifact: atomic_next_stage=STOPPED; blocking_reason.code=MISSING_OR_INVALID_ARTIFACT`.

## Stage gate and invariant

Read ../problem-navigator/references/workflow-control.md for 2.1 controls and endpoint
trims. Preserve the normal full-product trace contract; apply trims before drafting.

Run only when the validated workflow has `next_stage: solution-documentation`. A
wrong-stage invocation returns to `problem-navigator` without mutation. Validate
the workflow, accepted problem_frame, and current validated refined_solution (DRAFT
is allowed under explicit drafting delegation; ACCEPTED indicates actual review);
their workflow ID, profile, decision ID/version, and solution ID/version must close.
For a missing, unreadable, invalid, stale, or mismatched artifact, atomically set
`next_stage: STOPPED` and:

```yaml
blocking_reason:
  code: MISSING_OR_INVALID_ARTIFACT
  task_ids: [<every known affected task ID>]
```

Do not guess, repair, or publish a partial formal document.

This stage only projects Stage 6's current semantics. Preserve stable IDs,
priorities, conditions, exceptions, risks, scope, What/How boundary, and acceptance
meaning. A changed requirement/architecture uses resume --target solution-refinement;
changed selection uses resume --target adversarial-option-selection. Incorrect facts
use reopen and new evidence questions append. These shared controls update next_stage
and withdraw stale refs before handoff. Do not fill factual gaps yourself.

## Formal output

Prepare versioned document members as an unaccepted preview for every endpoint.
Do not publish an ACCEPTED solution_document envelope or canonical artifact ref until
the user explicitly accepts the exact whole document. Silence or rejection leaves the
preview unaccepted and this stage active. After acceptance, validate the proposed
envelope with the shared validate-document command before atomic publication.

- `GENERAL`: create one versioned formal solution report. Its structure is dynamic,
  but covers source/lineage, problem and decision, scope/non-goals, solution,
  conditions/acceptance, risks and residual issues. It does not impose PRD or
  software-architecture chapters.
- `PRODUCT_SOFTWARE`: create exactly one logical `solution_document` package with
  members in this fixed order on the normal route:

  ```text
  01-prd.md
  02-technical-solution-spec.md
  ```

  01-prd.md is the current What baseline. These 14 chapters are the default full-product
  template. Use relevant chapters at appropriate depth; omit inapplicable chapters with
  a concise applicability note instead of generating empty boilerplate:

  1. 文档信息
  2. 背景、目标与非目标
  3. 目标用户与画像
  4. 用户故事与场景
  5. 功能范围与 Out-of-Scope
  6. 详细功能
  7. 非功能需求
  8. UI/交互
  9. 验收标准
  10. 优先级与 MVP
  11. 度量指标
  12. 依赖与约束
  13. 风险与开放问题
  14. 里程碑

  Milestones, when relevant, express outcome/acceptance gates rather than implementation
  schedules or staffing. Do not invent UI or an MVP for a problem that has neither.

  The PRD must not prescribe a stack, framework, library, internal class, source
  file, implementation code, test code, deployment command, or migration command.
  `02-technical-solution-spec.md` contains only How and references the current PRD's
  stable requirement and acceptance IDs. It explicitly carries the current
  `prd_document_id` and `prd_document_version`, and those values must equal this
  `solution_document` envelope's `document_id` and `document_version`; it does not
  copy or rewrite requirements.

An explicitly framed **PRD-only** endpoint is a scope trim. It is legal only when the
accepted frame has `delivery_endpoint: PRD_ONLY`; represent it with the same
`solution_document` envelope and exactly `members: [01-prd.md]`. After explicit PRD
acceptance, atomically publish that canonical envelope at
`artifact_refs.solution_document` and set `next_stage: DONE` in the workflow-last
replacement. Rejection, silence, or a non-PRD-only frame publishes no accepted
envelope/ref and does not transition to DONE. The normal route still requires exactly
the ordered two-member pair.

A stable existing PRD is also a scope trim: keep it as the first logical member
without rewriting its product semantics, validate and cite its current document tuple
and requirement/acceptance IDs, and newly produce only the needed current Technical
Solution Spec as the second member. Neither trim creates a third profile or a second
state machine.

For delivery_endpoint: TECHNICAL_SPEC_ONLY, publish the same solution_document envelope
with exactly members: [01-technical-solution-spec.md]. It describes the technical
problem/evidence, constraints, alternatives, design and validation criteria using stable
design/acceptance IDs. Do not invent a PRD ID/version or product requirements. Accept the
complete technical document and set DONE. This trim was already applied at refinement.

If a PRD version changes, it invalidates every technical-spec and Spec-package binding
to the earlier PRD/document version. Withdraw stale downstream refs and return to the
appropriate current documentation/decomposition acceptance; never silently retain a
stale package.

## Handoff

After whole-document acceptance, mark the exact reviewed refined_solution ACCEPTED
without altering its semantic identity/version, publish the accepted document, then
atomically update artifact_refs.solution_document. No accepted document may point to
different or unreviewed semantics. Artifact files precede the workflow replacement.
Only a framed FINAL_SPEC_PACKAGE routes to solution-decomposition. FORMAL_DOCUMENT,
PRD_ONLY and TECHNICAL_SPEC_ONLY go directly to DONE after final acceptance. Reuse earlier
accepted semantics; final review is of the actual document, not another scope interview.
This Plugin ends in
accepted reports/specifications, never an implementation plan, tasks, tickets,
schedules, staffing, source files, code, tests, or external implementation routing.
