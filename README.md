[简体中文](README.zh-CN.md) · English

# Problem Navigator

Turn an unclear general or product/software problem into an evidence-backed research report, decision or design specification. Shared skills and a local Python/MCP research core support Chinese and English. Release **2.2.0**; research MCP **0.2.0**; [MIT](LICENSE).

## How it protects decision quality

- **Evidence before preference.** Frame the problem and collect relevant support and counterevidence, then clarify the user-owned trade-offs that can change the decision.
- **An isolated court.** Candidate advocates, redteam and feasibility reviewers complete independent papers before exchanging them. A fresh, non-participating judge decides from the sealed record. Supported Agent Team must be used; otherwise real independent Sessions preserve the roles manually.
- **Visible evidence gaps.** Separate facts, supported inferences, assumptions and unknowns. Missing evidence leads to targeted research, a qualified partial report or no selection; debate does not manufacture a winner.
- **Scope that fits the problem.** General problems follow their relevant mechanisms and constraints; product/software problems preserve What before How. Request a PRD only or technical specification only without unrelated chapters.
- **Traceable, correctable conclusions.** Link claims, sources, candidates and requirements. Correcting evidence reopens affected work, preserves research counts and invalidates stale decisions and documents.
- **Honest acceptance.** Drafting permission allows a preview. Publication requires acceptance of the actual document and checks its current bindings and member bytes.

These are workflow controls and review responsibilities. Structural checks and hashes do not prove factual truth, actual independent contexts or real user acceptance.

## How the court stays separate

| Step | Who reads the content |
|---|---|
| Freeze neutral scope, evidence and decision conditions | Main coordinator prepares references for clean role contexts |
| Complete every independent paper, then seal the full set | Each advocate, redteam and feasibility reviewer sees only its allowed neutral inputs |
| Exchange sealed papers; one or two bounded rounds | Role contexts read the exchange; round two only covers unresolved material issues |
| Judge the full record | A new independent judge context, separate from main and all participants |
| Continue the workflow | Main reads safe status, file references/hashes and the final neutral outcome only |

Main never receives position papers or debate bodies and never acts as judge. Roles can queue when concurrency is limited. Team support that is disabled or temporarily failing must be restored; only genuine lack of support permits manual independent Sessions. A single candidate may use direct assessment unless the accepted scope requires court. There is no single-session court fallback.

Manual mode supplies copy-ready role packets. The user opens independent Sessions and transfers their full submissions directly to assigned files and other role Sessions; main receives safe receipts only. See [host requirements](HOST_INSTRUCTIONS.md) and the [court protocol](skills/adversarial-option-selection/references/court-protocol.md).

## Quick start

Use an AI host that can load complete skill files/references, read/write local artifacts, run Python commands and obtain clarification and document acceptance. Prepare Python 3.11+ and `uv` on that host's PATH. Keep `skills/`, `mcp/` and `release.json` together in the extracted `problem-navigator-2.2.0.zip`. From that root:

```sh
uv sync --locked --project mcp/web-research-mcp
```

Initial setup may download dependencies. Then ask the host:

> Read the complete `skills/problem-navigator/SKILL.md` from this installation and its required references. Follow the workflow and load adjacent stage skills when routed. Answer in English. Only use these notes: a meeting planned for 30 minutes took 45 minutes and two agenda items were added midway. Do not browse. Produce a research report separating facts, inferences and unknowns.

Specify the absolute installation path if outside the host workspace. Native skill discovery is optional; explicit file loading works with the required capabilities. `$` and `/` shortcuts are host syntax. Offline research selects `NONE`, skips provider configuration checks and makes no research network calls. Host/model connectivity and initial dependency downloads are separate. Supplied statements retain provenance and are not automatically independently verified.

## Outputs and language

| Request | Endpoint and result |
|---|---|
| Understand a problem | `UNDERSTAND` → `RESEARCH_REPORT` |
| Decide a general solution | `DECIDE` + `GENERAL` → formal solution report |
| Design a complete product/software solution | `DECIDE` + `PRODUCT_SOFTWARE` → PRD and technical specification |
| Product requirements only | `PRD_ONLY` → `01-prd.md` |
| Technical design only | `TECHNICAL_SPEC_ONLY` → `01-technical-solution-spec.md` |
| Explicitly scoped specification package | Optional `FINAL_SPEC_PACKAGE` |

State the goal in ordinary language. For a PRD describe users, behavior, constraints and acceptance needs; for a technical problem request only the technical specification. The workflow ends at analysis/design. Documents remain previews until explicitly accepted.

Chinese and English have equal support. Prose follows the current explicit language choice, then an applicable earlier preference, then the current request. A final-document-only preference does not change interview language. Machine keys, enums, IDs, filenames and original citations stay unchanged.

## Web research, costs and host limits

Web research uses user-supplied Brave, Exa or Firecrawl keys with a local stdio MCP connection. Each Core call uses one explicit route without silently switching providers. Authorized queries, public URLs, domains and options go to that provider; keep confidential material out of requests. Host-native research requires authorization for its scope. The shared call budget counts operations, including failures and host operations; it is not a monetary spending cap.

MCP exposes research tools; full workflow execution also needs skills and local file/command access. Plain chat cannot execute it, and remote-HTTP-only MCP hosts cannot directly connect to the stdio server. One bundle includes the shared core once and optional Codex metadata. See the [Codex guide](adapters/codex/README.md); no second archive is needed. A portable file bundle does not imply universal one-click installation.

Validation checks schemas, current references, sealed records and retained file hashes. Host capability/context declarations still rely on truthful host or user observation. Detected court leakage invalidates the run. These controls do not establish live provider quality or successful end-to-end operation in every host.

Preserve safe error codes, request IDs and workflow artifacts when recovering. Keep credentials and private documents out of reports. Use the repository host's private vulnerability channel when available. Configuration, exact controls and integration limits are in [HOST_INSTRUCTIONS.md](HOST_INSTRUCTIONS.md). Licensing and attribution are in [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
