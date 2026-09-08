# Research design kickoff behavior scenarios

These cases record observable Skill behavior. They do not restate the artifact schema.

## RED baseline

The pre-Task-9 Skill was replayed against the following pressures. These are RED
because its observable output followed retired readiness tokens and Web-only task
shapes.

| Case | Pressure | RED observation |
|---|---|---|
| Wrong stage | A caller asks for a brief while `next_stage` is framing. | It accepts a retired precondition marker instead of returning without state change. |
| NONE | The user supplies a report and prohibits external research. | It still makes every initial task a mandatory Web task instead of `PROVIDED_MATERIAL`. |
| Core-neutrality | The caller asks the designer to save executor capabilities in each task. | It emits executor-specific capability metadata and a Web-only handoff rather than the current provider-neutral `PUBLIC_WEB` shape. |
| Product/software relevance | Only product form and a critical resource matter. | It uses generic lenses and does not explain the omission of the other two views. |
| Supplemental | Twelve tasks exist and the user asks to patch one fact gap. | It uses retired package IDs/readiness states rather than the one bounded brief revision. |

## GREEN cases

| Case | Input | Observable pass condition |
|---|---|---|
| Stage gate | The valid workflow says another `next_stage`. | Returns to the entry Skill and leaves workflow/artifacts byte-for-byte unchanged. |
| NONE | Backend is `NONE` and the problem frame plus one user document are accessible. | Produces 1–12 `PROVIDED_MATERIAL` tasks with material refs, no Web fields, zero-initialized counts, then hands off to research execution. |
| RESEARCH_CORE | Backend is `RESEARCH_CORE`; the user asks that the brief prefer a named provider. | Produces only provider-neutral `PUBLIC_WEB` questions with direction/domains/freshness and no provider, route, recommendation, or technical selection. |
| HOST_NATIVE entry authorization | The entry-authorized backend is `HOST_NATIVE`. | Still produces the same `PUBLIC_WEB` task shape; entry authorization changes execution, not the research questions. |
| PRODUCT_SOFTWARE | Product form and critical resource are relevant; open-source ecosystem and implementation path are not. | Covers the two relevant views, explains a merge when useful, and states why each other view is omitted instead of creating four fixed tasks. |
| GENERAL | A policy question has no product/system target. | Themes are derived dynamically and no PRD, architecture or product checklist is imposed. |
| One supplemental revision | A schema-valid revision-1 brief, current package and `NEEDS_SUPPLEMENTAL` readiness identify three fact gaps. | Revision 2 preserves ordered old tasks and appends three new IDs; its draft inherits every old package member, marks only new IDs unfinished, and preserves old counts/adds zeros. Each stable artifact is temp-written/atomically replaced before the workflow is replaced last. |
| NONE material supplement | A partial revision-1 `NONE` workflow receives another accessible user artifact without changing its accepted boundary. | Revision 2 appends only `PROVIDED_MATERIAL` tasks, keeps backend `NONE`, and preserves/adds only zero counts. |
| Invalid supplemental input | A schema-valid graph has a mismatched goal/ref/count/state, missing or duplicate old receipt, unresolved/duplicate evidence or candidate ID, incomplete DECIDE comparison, or missing/duplicate readiness disposition. | The shared semantic gate rejects it and atomically stops with full `MISSING_OR_INVALID_ARTIFACT` reason and known task IDs; it never synthesizes old data. |
| Interrupted supplemental publication | Brief/draft replacement succeeds but workflow-last publication is interrupted. | RESUME detects the inconsistent referenced graph, stops with full `MISSING_OR_INVALID_ARTIFACT`, and asks to regenerate the stable artifacts; it creates no version graph, lock, or transaction layer. |
| Second supplementation | A revision-2 brief still has a fact gap. | Atomically stops with `SUPPLEMENTAL_LIMIT_REACHED` and exact gap task IDs; it neither creates revision 3 nor changes backend. |
| NONE boundary change | A material-only workflow later needs a public fact. | Preserves backend `NONE` and atomically writes `RESEARCH_CANCELLED`, `STOPPED`, and `PUBLIC_WEB_REQUIRES_NEW_WORKFLOW` with known affected IDs. |
| Intentional boundary change | The user deliberately changes the accepted problem, profile, backend, or material boundary. | Cancels and stops the current workflow with a full `USER_CANCELLED` reason, then directs a new unrelated workflow. |
| Direct design cancellation | The user cancels during design. | Atomically writes `RESEARCH_CANCELLED`, `STOPPED`, and full `USER_CANCELLED`; it does not classify cancellation as corrupt input. |
| Corrupt graph | Required artifacts are missing, invalid, inconsistent, or interrupted. | Preserves the current research state and stops with full `MISSING_OR_INVALID_ARTIFACT`; it does not classify corruption as an intentional change. |

## GREEN review result

Static contract replay passes when every case above is observable in the current
Skill and no retired readiness token or old Web-only task shape is used. The focused
workflow tests independently check the oneOf task shapes, stable IDs, task bounds,
supplemental preservation and wrong-stage non-mutation.
