---
name: problem-navigator
description: Use when starting or resuming an evidence-backed problem analysis, research report, solution report, PRD, technical solution specification, or solution specification package.
---

# Problem Navigator

Only ordinary natural-language entry. Own CREATE/RESUME, backend authorization and routing.
不执行 framing、不搜索、不生成 evidence. Read references/workflow-control.md and
references/artifacts.schema.json; they govern current execution.

Serve Chinese and English users equally. Follow the shared language policy for
interviews, summaries and deliverables; keep machine-readable keys and IDs unchanged.
Check the shared host capabilities before creating or changing workflow files.
Research uses enabled Team when supported, otherwise independent manual Sessions
with shared control; see ../research-execution/references/research-dispatch.md.
Main coordinates safe receipts and receives the final neutral research package.
For court-required selection, supported Agent Team must be enabled and used; genuine
absence requires manual independent Sessions. The main session never reads court
arguments or judges them. Follow the selection protocol and its safe CLI receipts.
Skill names below are stable IDs; load the linked sibling SKILL.md to hand off.
Host-specific command aliases are optional integration conveniences.

## CREATE

First decide whether public Web evidence is needed. Persist one current workflow in
.problem-navigator/workflows/<UUID>.yaml through same-directory temporary replacement:
schema_version: 1, next_stage: problem-framing, research_state: NOT_STARTED,
native_fallback_approved: false, call_counts: {}, artifact_refs: {},
research_budget: {limit: 40, recovery_reserve: 6}.
analysis_goal is assigned at framing; content_profile exists only in the frame.

Pure reasoning/user materials or explicit offline request selects NONE. 不运行 MCP
reachability、不得检查 MCP status、不得调用 web_research_status, no network call.
Hand off immediately to problem-framing.

For Web create UNSET first. If the user already explicitly chose host tools, record
HOST_NATIVE + true from that authorization without forcing Core setup. Otherwise check
MCP reachability and read-only web_research_status. Any relevant configured capability
(search/news/academic/developer/semantic/fetch/map) permits framing; generic search is
not a universal prerequisite. Execution checks actual routes. Status is local configuration,
not proof of key validity or remaining quota. Suitable Core selects RESEARCH_CORE + false.
A valid environment key can be usable despite config_state: INVALID; explain the file issue.

If unavailable, explain the specific Python 3.11+, uv, available skill bundle, MCP registration or
provider-key prerequisite. Recheck after a change. Do not install or claim repairs without
doing/verifying them. Use current explicit host authorization when available; otherwise
disclose intended capability, evidence scope and outbound query/URL/domain data and ask.
No consent leaves UNSET + false, RESEARCH_BLOCKED, problem-framing and
blocking_reason: {code: NO_AUTHORIZED_WEB_BACKEND, task_ids: []}.
Approval selects HOST_NATIVE + true and NOT_STARTED. The entry still does not research.

## RESUME

Read stored workflow first; validate schema/current required inputs. Preserve IDs/counts
and refs except named shared-control operations. NONE skips configuration/network checks.
Recheck Web only before new Web work, never merely while consuming accepted evidence.
Valid unrevoked host consent persists; Core recovery does not automatically replace it.
Revocation first clears HOST_NATIVE authorization to UNSET + false, preserving evidence/counts.

Apply user correction before normal routing: reopen affected factual tasks, append new
questions, or resume --target to a downstream producer. STOPPED recovery requires the
explicit request and --user-requested. Never guess missing history.
A legacy decision without review metadata cannot proceed downstream: return explicitly
to selection and create a valid current review. Missing frame bindings require truthful
regeneration from validated inputs, never invented migration fields. On corruption stop
with MISSING_OR_INVALID_ARTIFACT and known task IDs; use shared explicit regeneration.

An entry-preflight block restores NOT_STARTED only with zero calls, empty blocking task
IDs, problem-framing and a newly usable/authorized backend. Execution blocks retain draft,
counts and execution stage; never reset them as initial preflight.

## Routing

| next_stage | Handoff |
|---|---|
| problem-framing | [problem-framing](../problem-framing/SKILL.md) |
| research-design-kickoff | [research-design-kickoff](../research-design-kickoff/SKILL.md) |
| research-execution | [research-execution](../research-execution/SKILL.md) |
| decision-readiness-interview | [decision-readiness-interview](../decision-readiness-interview/SKILL.md) |
| adversarial-option-selection | [adversarial-option-selection](../adversarial-option-selection/SKILL.md) |
| solution-refinement | [solution-refinement](../solution-refinement/SKILL.md) |
| solution-documentation | [solution-documentation](../solution-documentation/SKILL.md) |
| solution-decomposition | [solution-decomposition](../solution-decomposition/SKILL.md) |
| DONE | Return accepted artifact unless a correction invokes shared controls |
| STOPPED | Explain reason; apply explicitly requested valid recovery or stop |

No version graph, event log, second state machine or automatic implementation exit.
