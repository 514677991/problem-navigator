# Isolated court protocol 2.2

Read court.schema.json and role-packets.md. The court is an isolated review record
inside selection, not another workflow, an evidence provider or implementation exit.

## Information boundary

Main is the coordinator and sole canonical workflow/evidence/readiness/decision writer.
During court it receives only safe status, IDs, file refs, SHA256 hashes and routing
needs; after validation it may receive the final neutral outcome. It must not read or
quote papers, challenges, responses or detailed judge reasoning. A file tool printing
those bodies into main context is a leak. Main is not the judge.

Every advocate, redteam, feasibility reviewer and judge has a real distinct context.
Start clean with its packet and frozen neutral inputs, without inherited main history,
prior recommendations or another role's memory. Never relabel a persuasive old Session
as fresh. Context IDs and isolation are host declarations: scripts check consistency
and hashes, not actual independence. Different models are optional; isolation is not.
Workers write only their assigned submissions; in file-incapable manual Sessions the
user saves their directly returned submissions. Only the coordinator runs sealing and
changes manifest or canonical state. Never run concurrent writers on one case/workflow.

## Phase 0 — Current inputs, mode and responsibilities

Validate frame, frame-bound brief, evidence and READY readiness. Freeze criteria from
accepted goal, constraints and value_conditions before comparisons. Assess relevant
status-quo, reject-all and combination alternatives, or explain their irrelevance.
New candidates/combinations require prior evidence and a return to research/readiness.

Use TEAM whenever independently scheduled agents are supported. Enable/recover disabled
or temporarily failing Team; do not call that UNSUPPORTED. Only genuine absence permits
MANUAL_SESSIONS with real external clean Sessions. If neither preserves isolation,
remain blocked. DIRECT is separate and cannot replace a required court.

The host declaration JSON contains actual observed values:

```json
{
  "mode": "TEAM",
  "team_support": "SUPPORTED",
  "team_enabled": true,
  "capability_basis": "Observed capability and current enabled state",
  "coordinator_context_id": "actual-main-context-id",
  "main_context_clean": true
}
```

Manual mode uses MANUAL_SESSIONS, UNSUPPORTED and team_enabled false. Replace examples
with observed values; do not fabricate identities. If a manual Session exposes no
native ID, use a user-registered unique label mapped to that actual separate Session;
prefer native IDs when available. Labels identify real Sessions, not simulated roles.
Resolve the helper from installation,
independent of the workspace. Refs are workspace-relative; quote paths for the shell:

```text
uv run --locked --project <bundle-root>/mcp/web-research-mcp python <bundle-root>/skills/adversarial-option-selection/scripts/court_control.py --project-root <workspace> prepare --workflow <workflow-ref> --host-declaration <host-json-ref> --case-id CASE-001
```

The case_ref is `.problem-navigator/courts/<workflow_id>/<case_id>/manifest.json`.
Prepare snapshots neutral inputs and returns safe refs. Roles are advocate-1 through
advocate-N, redteam, feasibility and judge. Each candidate has an advocate; redteam
and feasibility each cover all candidates. Limited slots mean independent contexts
queue, not one context playing several roles. There is no fixed five-person rule.

## Phase 1 — Complete and seal every independent paper

Generate each non-judge role's independent packet. Dispatch only that packet and its
allowed neutral inputs. Nobody reads other positions, partial results or summaries,
or contacts another role before the entire independent set is completed and sealed.
Redteam and feasibility also produce full papers before seeing advocacy.

Advocates explain mechanism/design, demonstrated capability, dependencies/interfaces,
adaptation/operating costs, failure conditions, counterevidence, unknowns and relevant
compatibility. Give cost ranges with assumptions, not invented precision. Claims cite
current evidence IDs or explicit limitations. No new research runs inside selection.

Adapt dimensions to scope. GENERAL may examine mechanisms, stakeholders, resources,
incentives, costs, reversibility and adverse effects. PRODUCT_SOFTWARE may examine
architecture, actual capability/maturity, data/interfaces, extension constraints,
migration/operation cost, failure modes and integration. PRD_ONLY examines product
value, behavior, scope and feasibility; TECHNICAL_SPEC_ONLY uses actual code/version
and system constraints without a fabricated PRD. Each paper records all seven stable
dimension keys exactly once: mechanism, capabilities, interfaces, adaptability,
total_cost, failure_conditions, combination. Explain inapplicability or a shared
assessment in the relevant records instead of omitting keys or inventing content.

Self-disclose strongest known defects, falsifying conditions and remaining unknowns.
No quota of three defects or questions applies. Finding no defect is only a bounded
observation with coverage limits. Redteam checks all candidates and omitted paths;
feasibility independently checks practical constraints and comparable assumptions.

Collect safe receipts only. seal-papers freezes the complete required submission set
before Phase 2; do not release faster papers early. Frozen papers stay immutable.
Later concessions/withdrawals are linked public records; changed upstream facts need
invalidation and a new current case.

## Phase 2 — Balanced, bounded exchange

Use the recorded paper order, deterministically derived from case_id and role_id
hashes rather than arrival order or presumed winner. Do not reorder it to favor a
candidate. This is an order control, not proof that model position bias is eliminated. Apply comparable
scrutiny across candidates and relevant themes. Keep each challenge/response concise
and provide comparable language-appropriate space. Chinese characters and English
words are different units; do not pretend equal numbers guarantee equal expression.
The schema limits each question/response text to 1200 characters and the manifest
provides the total per-role/phase expression_budget_chars. These are upper bounds,
not a target length or a claim of equal linguistic expressiveness.

Each challenge links a sealed claim, candidate, criterion/theme, evidence or explicit
unknown, and decision impact. Redteam and feasibility each cover every candidate
advocate paper and theme. Set kind CHALLENGE or NO_MATERIAL_OBJECTION; the latter gives
a supported, explicit no-objection assessment rather than a fabricated challenge.
Every challenge/assessment gets a linked evidence-based rebuttal,
concession/withdrawal, clarification or evidence request. Preserve the original claim
and public disposition. Fixed role responsibility never requires defending falsehood.
Do not reward agreement, repetition or length. Main and judge give no interim preference.

Seal challenges before issuing response packets. Seal responses before another round.
Use one or two rounds; round two addresses only unresolved decision-changing earlier
issues and references them. Never reopen settled rhetoric, silently add claims or treat
the limit as evidence sufficiency. Preserve the full exchange outside main for review.

## Phase 3 — New, non-participating judge

After exchange, create the judge in another clean context. It receives the generated
packet's neutral snapshots and full sealed corpus, not main preferences or a participant
summary. It did not advocate, red-team or assess feasibility earlier. It re-reads original
positions and every disposition, including concessions and withdrawals.

Judge all candidates against the same criteria and surviving supported claims. Record
rejected options/reasons, remaining issues, assumptions and conditions that would change
the outcome. Give each unresolved challenge exactly one residual_dispositions entry:
NON_BLOCKING, NEEDS_RESEARCH or NEEDS_READINESS, with reason and current evidence or
limitation references. SELECTED requires only justified NON_BLOCKING residuals and
surviving support for each selected candidate; no residuals means an empty list.
Do not count votes or infer truth from consensus. Select only current
supported candidate IDs. Detailed reasoning stays in the verdict; only the final neutral
summary and required routing metadata reach main through outcome. verdict.outcome and
neutral_summary.status are SELECTED, NEEDS_RESEARCH, NEEDS_READINESS or STOPPED;
neutral_summary also records selected_candidate_ids and rationale. Non-selected
outcomes leave selected_candidate_ids empty. Copy a selected neutral rationale exactly
to the proposed decision instead of importing detailed argument bodies.

New facts return to research under existing authorization, reserve and revisions;
user-owned values return to readiness. The sole workflow writer executes those routes.
No supported selection means no selected decision. Changed frame/evidence/readiness
bindings invalidate the old court for current publication; prepare a new current case.

## CLI and violations

Use the common invocation above with these actions. Generated packets carry exact
submission schemas/templates; follow them rather than inventing fields.

| Action | Arguments after --project-root |
|---|---|
| Packet | packet --case <case-ref> --role <role-id> --phase independent\|challenge\|response\|judge [--round 1\|2] |
| Seal papers | seal-papers --case <case-ref> --submission <record-ref> [--submission <record-ref> ...] |
| Seal challenges | seal-challenges --case <case-ref> --round 1\|2 --submission <record-ref> [...] |
| Seal responses | seal-responses --case <case-ref> --round 1\|2 --submission <record-ref> [...] |
| Seal verdict | seal-verdict --case <case-ref> --submission <record-ref> |
| Check integrity | check --case <case-ref> |
| Read final neutral result | outcome --case <case-ref> |
| Invalidate contamination | invalidate --case <case-ref> --reason-code CONTEXT_LEAK |

Prepare, packet, seal and check emit only metadata. The packet receipt provides
packet_ref, packet_sha256 and assigned_submission_ref. Never paste record bodies into
main tool descriptions, progress, completion messages or automatic worker returns.
In a real manual external Session with no file writing, a full schema-valid record may
be returned directly to its human user for saving; it must never be relayed into main.
Shared validate-decision later binds the
sealed case to the proposed decision.

On a real leak stop exchange, invalidate and preserve the case. Disclosure does not
restore independence. Restart with clean roles; if main received arguments, use a clean
coordination Session carrying only neutral accepted state and safe references. On
timeout/missing submission recover the actual role or report a capability block; never
synthesize its answer. Hashes prove retained bytes and links, not facts or isolation.
