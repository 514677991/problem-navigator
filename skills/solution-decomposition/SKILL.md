---
name: solution-decomposition
description: Reorganize an accepted solution document into a design-depth specification package without adding semantics or implementation work.
---

# Solution Decomposition

Contract marker: `stage_gate: next_stage == solution-decomposition`.
Normative wrong-stage guard: `wrong_stage: return=problem-navigator; artifact_writes=0; state_mutations=0`.
Normative invalid-artifact guard: `invalid_artifact: atomic_next_stage=STOPPED; blocking_reason.code=MISSING_OR_INVALID_ARTIFACT`.

## Stage gate

Run only when the validated workflow has `next_stage: solution-decomposition`. If it
does not, return to `problem-navigator` and mutate nothing. Validate the workflow
and accepted `solution_document` against `../problem-navigator/references/artifacts.schema.json`; workflow
ID, document ID/version, profile, accepted status, and all member paths must match
the current artifact reference. Validate actual accepted member bytes against their
member_hashes; keep declared requirement traces closed. A metadata-only envelope check
is insufficient. Any missing, unreadable, invalid, stale, or mismatched
input atomically sets `next_stage: STOPPED` with:

```yaml
blocking_reason:
  code: MISSING_OR_INVALID_ARTIFACT
  task_ids: [<every known affected task ID>]
```

Do not guess, repair, or redispatch this stage.

## Reorganize only

Read ../problem-navigator/references/workflow-control.md. Run only for a framed
FINAL_SPEC_PACKAGE; other endpoints terminate at their accepted document. Never add
Spec decomposition solely to satisfy an internal stage count.

This stage adds design-depth organization, never new meaning. Preserve the document's
requirements, acceptance, boundaries, dependencies, risk allocation, and current
document ID/version. A presentation/trace gap uses resume --target solution-documentation;
a semantic gap uses resume --target solution-refinement; a factual gap uses shared
reopen/append. Invoke the control to invalidate downstream refs before handoff. A changed
`document_version` (including a PRD revision) invalidates every stale technical and
package binding; no old package is accepted.

- `GENERAL`: dynamically split only when independent goals, boundaries, interfaces,
  dependencies, or acceptance meaning make separate units useful. A one-unit package
  is valid when a meaningful split does not exist. Each unit gives its goal, boundary,
  semantic interface/dependency, constraints, and acceptance mapping.
- `PRODUCT_SOFTWARE`: retain the same dynamic units and add a closed trace table:
  current PRD requirement ID → Technical Solution Spec design ID → one or more unit
  Spec IDs. Every current requirement and acceptance ID closes through this mapping;
  a shallow map, shared constraints, and design-depth unit Specs are all permitted.

The package must not contain an implementation plan, task list, ticket, ordered
implementation steps, schedule, staffing, source-file list, implementation code,
test code, deployment command, migration command, or external planning/implementation
handoff. It describes design intent and reviewable boundaries only.

## Acceptance and terminal transition

First form a complete **pre-acceptance preview** bound to the current document ID/version
and proposed package ID/version. It contains the shallow map, closed trace table when
applicable, every shared-constraint stable identity, and every unit record with stable
unit ID, actual package member path, and content identity. The member-path set must
exactly equal the proposed package `units`; no detached unit list is accepted. Show the
map and the whole current package to the user, then ask for explicit affirmative
whole-package acceptance. A rejection, correction, ambiguous answer, or silence leaves
the workflow and every accepted artifact/ref byte-for-byte unchanged: it does not
publish `acceptance_status: ACCEPTED`, change `artifact_refs.solution_spec_package`, or
set DONE. Apply accepted corrections to a new preview and ask again.

Only explicit acceptance publishes that exact current preview; never manufacture or
substitute a new package after the acceptance. It creates the `solution_spec_package` envelope with stable
`package_id`, current package version, current document ID/version, profile, non-empty
unit paths, and `acceptance_status: ACCEPTED`. Validate the accepted envelope and all
current members, atomically publish every current member and the package, then perform
the workflow-last atomic replacement that sets `artifact_refs.solution_spec_package`
and `next_stage: DONE`. The only terminal states are `DONE` and `STOPPED`; never emit
planning or implementation readiness.
