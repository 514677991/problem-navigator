# End-to-end contracts — 2.0.0

`analysis_goal` controls depth and `content_profile` controls content shape. They are
orthogonal axes in one state machine, not separate product/software workflows.

| content_profile | analysis_goal | accepted terminal deliverable | Must not be fabricated |
|---|---|---|---|
| GENERAL | UNDERSTAND | neutral research report → `DONE` | candidate registry, readiness, decision, PRD |
| PRODUCT_SOFTWARE | UNDERSTAND | product/open-source/feasibility research report → `DONE` | forced decision chain, PRD, technical spec |
| GENERAL | DECIDE | formal solution report → dynamic `solution_spec_package` → `DONE` | PRD or software-only chapter structure |
| PRODUCT_SOFTWARE | DECIDE | research report → `01-prd.md` + `02-technical-solution-spec.md` → traced `solution_spec_package` → `DONE` | duplicated requirements or code/plans |

An explicit formal-document endpoint and PRD-only endpoint are scope trims. PRD-only
uses the same `solution_document` envelope with `[01-prd.md]` only when the accepted
frame carries `delivery_endpoint: PRD_ONLY`; normal product delivery retains both
ordered members. A stable
existing PRD is another scope trim: it avoids repeat discovery but remains in the same
`PRODUCT_SOFTWARE` DECIDE state machine; neither creates a third profile or state
machine. A new PRD/document version invalidates stale technical/spec-package bindings.

The Technical Solution Spec binds the current PRD document ID/version and stable
requirement/acceptance IDs. The final package closes requirement/acceptance → design →
unit trace whose unit-record paths exactly equal actual package members. Stage 8 binds
the preview to current document/package tuples, map, trace, shared constraints, and
unit content identities; rejection or silence changes nothing, while explicit
acceptance alone publishes that exact accepted preview and `DONE`.

Only `DONE` and `STOPPED` are terminal. Every wrong-stage invocation returns to
`$problem-navigator` without mutation. Every current-stage missing, invalid, stale,
or mismatched artifact stops with `MISSING_OR_INVALID_ARTIFACT`. No path creates code,
implementation plans, tasks, tickets, schedules, staffing, source files, tests, or
deployment/migration commands.
