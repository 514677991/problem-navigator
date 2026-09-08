# Solution decomposition scenarios — 2.0.0

| Case | Expected contract result |
|---|---|
| Wrong stage | Return to `$problem-navigator` without mutation. |
| Missing/stale accepted document | `MISSING_OR_INVALID_ARTIFACT` and `STOPPED`. |
| GENERAL document cannot usefully split | One design-depth unit is accepted. |
| GENERAL document can split | Units follow real boundaries/interfaces/dependencies, not chapters or departments. |
| PRODUCT_SOFTWARE document | PRD requirement ID → technical design ID → unit Spec trace closes for every current requirement and acceptance. |
| PRD/document version change | Old technical and package bindings are stale and must not be accepted. |
| Whole package preview | Bind current document/package tuples; show map, closed trace, shared-constraint identities, and every unit's stable ID, actual member path, and content identity before explicit affirmative acceptance. |
| Detached/foreign package member | Reject when unit-record paths do not exactly equal `solution_spec_package.units`. |
| Rejection, correction, ambiguity, or silence | Preserve workflow and accepted artifact refs byte-for-byte; publish no accepted package and do not set `DONE`. |
| Whole package explicitly accepted | Publish exactly the accepted preview, validate and atomically publish every current member/ref, then set `DONE` workflow-last. |

This stage reorganizes only. It never emits implementation plans, task lists, tickets,
steps, schedules, staffing, source-file lists, code, test code, commands, or an
implementation handoff.
