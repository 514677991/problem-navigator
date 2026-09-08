# Evidence package semantic gate 2.1

Read workflow-control.md. Schema validation precedes workflow_control.validate_evidence;
first execution initializes its draft before this gate. Before publishing an accepted
package run validate-publication against the completed draft and proposed package.
The executable checks protect
identity, revision, ownership and reference closure; hosts must still evaluate factual truth.

1. Workflow/frame/brief/draft or package share workflow_id and analysis_goal wherever present.
   Upstream ID/version tuples equal current referenced artifacts.
2. content_profile comes from the frame and stays consistent downstream.
3. Every task appears exactly once in a terminal receipt or unfinished_task_ids; counts keys
   equal the brief and counts never reset.
4. Web/external/evidence references close within the same task. IDs are unique. WITH_RESULTS
   has owned source and evidence; non-results and quality shortfalls have same-task limitations.
5. Every host receipt records USER_APPROVED and a truthful reason using current scoped consent.
6. NONE permits only PROVIDED_MATERIAL with zero Web counts. Authorized Web workflows may
   mix PROVIDED_MATERIAL/PUBLIC_WEB; material tasks remain zero-count and external-source only.
7. UNDERSTAND has no candidates. DECIDE covers every candidate and comparison theme with
   evidence or explicit limitation. Existence of a source ID alone does not establish truth.
8. Publication uses base_evidence_revision +1. reopen withdraws affected facts and preserves
   other members/counts. append preserves old definitions/counts, adds at most four tasks and
   keeps at most 16 overall; later revisions are budget-bound. If supplied, supplemental_request
   and affected_candidate_ids close to the current evidence package; new tasks use matching
   supplemental_request_id and material tasks cover carrier refs. UNDERSTAND needs no readiness.
9. Product lenses are relevance/endpoint-aware; explain omissions and never fabricate a PRD
   for a technical-only problem.
10. Derive research state from outcomes; FACT has support, critical claims passage_locator,
    INFERENCE factual basis, UNKNOWN/ASSUMPTION limitations. Inspect currency, versions,
    counterevidence and source independence.

On corruption stop with MISSING_OR_INVALID_ARTIFACT and known task IDs, preserving counts
and artifacts; use shared explicit recovery rather than guessing.
