[简体中文](README.zh-CN.md) · English

# Problem Navigator

Turn an unclear general or product/software problem into an evidence-backed research report, decision or design specification. Shared skills and a local Python/MCP research core support Chinese and English. Release **2.3.0**; research MCP **0.2.0**; [MIT](LICENSE).

## Core ideas across the eight stages

Problem Navigator moves from framing the problem, building evidence, clarifying values and selecting an option to refining the solution, documenting it and decomposing its specification. Court-style adversarial review is the selection method in Stage 5; the other stages protect the quality of the problem definition, evidence, requirements and design.

The table connects each stage's operating rules with its methodological perspective. First-principles thinking, Socratic questioning and Occam's razor guide analysis and review; local scripts check the artifact, reference, version and content relationships that can be expressed explicitly.

| Stage | Core methods | Practice and quality contribution |
|---|---|---|
| [1. Problem framing](skills/problem-framing/SKILL.md) | **First-principles thinking; problem reframing** | Start from the actual goal, necessary constraints and assumptions needing verification. Separate scope, non-goals and the requested outcome. Ask what must really be achieved, so a proposed solution does not become the problem definition by default. |
| [2. Research design](skills/research-design-kickoff/SKILL.md) | **Question-driven research; falsifiability; relevance-based organization** | Turn gaps into answerable research questions; for decision tasks, make them distinguish candidates. Define quality bars and stop conditions, and seek both support and counterevidence. Merge or omit themes according to relevance so research informs judgment. |
| [3. Research execution](skills/research-execution/SKILL.md) | **Critical thinking; evidence classification; independent verification** | Inspect original passages, source independence, dates and versions. Separate facts, inferences, assumptions and unknowns; ground inferences in facts. Repeated retrieval of one article is one source. Make conclusions locatable, challengeable and correctable. |
| [4. Decision readiness](skills/decision-readiness-interview/SKILL.md) | **Socratic questioning; separation of facts and values** | Ask only about intentions, premises and trade-offs that can change the decision: why a constraint matters or which risks are unacceptable. Reuse existing answers. Research resolves public factual gaps; users clarify their values, avoiding questionnaires without decision impact or requests to guess facts. |
| [5. Option selection](skills/adversarial-option-selection/SKILL.md) | **Independent thinking; critical thinking; court-style adversarial review** | Freeze criteria, build independent cases, disclose weaknesses and counterevidence, and challenge each candidate. A separate judge who did not advocate decides from the record. Support selection with arguments that withstand scrutiny, avoiding conformity, anchoring and vote counting. |
| [6. Solution refinement](skills/solution-refinement/SKILL.md) | **First principles; Occam's razor; ablation reasoning; What/How separation** | Derive necessary capabilities from goals and acceptance criteria. Establish What before constraining the How required by the deliverable scope. Examine the necessity of features, components, rules and processes; state dependencies, exceptions and costs. Reduce unsupported assumptions and complexity while preserving the agreed meaning and satisfying the same goals and constraints. |
| [7. Formal documentation](skills/solution-documentation/SKILL.md) | **Semantic fidelity; separation of concerns; one requirements baseline; traceability** | Accurately express the refined solution. When both product and technical documents are needed, technical design references current requirement and acceptance IDs. Preserve scope, exceptions and risks, and review the actual version to reduce semantic drift, duplicate definitions and delivery of the wrong draft. |
| [8. Specification decomposition](skills/solution-decomposition/SKILL.md) | **High cohesion and low coupling; purposeful decomposition; explicit interfaces and contracts** | Organize units around distinct goals and responsibilities, with explicit boundaries, interfaces, dependencies and acceptance mappings. Keep related concerns together and make relationships reviewable. Retain one unit when splitting adds no value, avoiding fragmentation and hidden dependencies. |

**Socratic questioning exposes consequential premises.** Examples include: Which goal does this requirement serve? What supports it? What changes if its premise fails? Which exceptions or consequences remain unexamined? Ask when the answer can affect scope, selection or risk, and reuse answers already established.

**Ablation experiments examine necessity and contribution.** During refinement, where relevant, ask what happens if a feature, component or approval step is removed: do the goal and acceptance criteria still hold? That is counterfactual reasoning. When empirical evidence is needed, define the baseline, removed element, controlled conditions and evaluation measures; add a focused evidence question and examine actual experiment records as needed. The current workflow has no built-in engine that automatically runs ablation experiments. An unperformed experiment remains a proposed validation design, not a verified finding.

**Occam's razor constrains unnecessary complexity.** Simplification is conditional on satisfying the goals, evidence and constraints; the shortest solution is not automatically best. Preserve required reliability, safety and exceptions. Do not silently cut accepted requirements or shrink them to an MVP; changes to selection or meaning return to the appropriate stage.

Principles that apply throughout the workflow also include:

- **Maintain independent thinking and revise judgments.** User preference, authority, model confidence and multi-role agreement do not prove facts. Apply consistent standards to supporting and opposing evidence, and revise conclusions when counterevidence warrants it.
- **Match depth to the problem.** General problems focus on mechanisms, stakeholders and constraints; product/software work trims What and How to the requested scope. `UNDERSTAND` completes its report at Stage 3; `DECIDE` continues through decision and design. Stage 8 runs only when a specification package is in scope.
- **Keep stage responsibilities focused and handoffs explicit.** Research design, evidence gathering, value clarification, selection, semantic refinement and documentation have distinct responsibilities, connected by stable artifact references and versions.
- **Preserve traceability, correction and honest acceptance.** Factual corrections reopen affected research, retain counts and invalidate stale downstream references. Drafting permission produces a preview; acceptance applies to the actual document version reviewed.

These methods require careful host execution and judgment. Structural checks and hashes establish record consistency; they do not prove factual truth, that an experiment occurred, optimal architecture, actual context isolation or real user acceptance.

## From a question to an executable research brief

Product/software research connects six project anchors—definition, target market,
competitors or substitutes, critical resources, reuse intent and capability/module
boundaries—to concrete questions. The [product research guide](skills/research-design-kickoff/references/product-research-guide.md)
expands product form, resource-specific constraints, open-source reuse and implementation
paths. Relevant omissions and merges are explained; fixed competitor counts or a
six-module architecture are not required. Known inputs are reused, public unknowns
become research tasks, and only material user-owned ambiguity needs clarification.

General problems choose their own themes. A short material-only explanation can
remain one task; UNDERSTAND produces an explanation and its limits without candidate
ranking. Every new task states its purpose, expected output, evidence quality bar,
stopping condition and genuine dependencies. The brief is the authoritative source
for the worker packets, so dispatch does not introduce a second research plan.

Research uses enabled **Agent Team when supported**, otherwise real independent
manual **Sessions**. One task can use one independent researcher; a separate synthesis
context is used for multiple results. Main receives coordination receipts and the final
neutral evidence package, keeping research bodies outside its context. Independent
tasks can run in parallel while shared budget updates are serialized. See the
[research dispatch protocol](skills/research-execution/references/research-dispatch.md).
Context declarations and local receipts do not prove actual host isolation or undeclared
external calls. Manual Sessions without shared control receive handoff packets; they
cannot be reported as a validated execution.

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

Use an AI host that can load complete skill files/references, read/write local artifacts, run Python commands and obtain clarification and document acceptance. Prepare Python 3.11+ and `uv` on that host's PATH. Keep `skills/`, `mcp/` and `release.json` together in the extracted `problem-navigator-2.3.0.zip`. From that root:

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
