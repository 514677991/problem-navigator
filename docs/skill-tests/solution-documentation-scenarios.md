# Solution documentation scenarios — 2.0.0

| Case | Expected contract result |
|---|---|
| Wrong stage or invalid refined solution | Return to entry unchanged, or stop with `MISSING_OR_INVALID_ARTIFACT`. |
| GENERAL DECIDE | One accepted, versioned formal solution report with no PRD obligation. |
| PRODUCT_SOFTWARE DECIDE | One accepted logical package: `01-prd.md`, then `02-technical-solution-spec.md`. |
| New semantic discovered while writing | Return to refinement; documentation adds no semantics. |
| New public fact | Route to legal evidence supplementation; do not invent it. |
| PRD-only endpoint | Only an accepted `delivery_endpoint: PRD_ONLY` frame permits the same `solution_document` envelope with `[01-prd.md]`; explicit PRD acceptance publishes its canonical ref and atomically ends at `DONE`. |
| Stable existing PRD | Cite current requirement/acceptance IDs and write only the necessary How document. |
| PRD version changes | Invalidate stale Technical Solution Spec and solution Spec package bindings. |

The Technical Solution Spec explicitly carries the current `prd_document_id` and
`prd_document_version`, plus stable requirement and acceptance references. A stable
existing PRD stays the first logical member without semantic rewriting.

The PRD retains all 14 approved chapters, including shallow/inapplicable chapters with
their reason. It contains What, not stack, library, internal class, source file, code,
tests, or deployment/migration commands.
