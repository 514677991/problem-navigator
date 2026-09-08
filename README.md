[简体中文](README.zh-CN.md) · English

# Problem Navigator

A general-purpose AI plugin made of shared skills and a local Python/MCP research core. It turns general and product/software problems into evidence-backed reports and design specifications in Chinese or English. Release `2.1.0`; research MCP `0.2.0`; MIT license.

Clone this public repository or download the v2.1.0 release ZIP, `problem-navigator-2.1.0.zip`. Both use the same layout: keep `skills/`, `mcp/`, and `release.json` under the same installation root. The shared core appears once, alongside optional Codex metadata and its guide. This layout is not a universal one-click plugin import format.

## Quick start

Use an AI host that can read complete skill files and references, read/write local artifacts, run local Python commands, and ask for clarification and document acceptance. Prepare Python 3.11+ and `uv` on that host's `PATH`. From the repository root or extracted release root:

```sh
uv sync --locked --project mcp/web-research-mcp
```

Initial setup may download dependencies. Then ask your host:

> Read the complete `skills/problem-navigator/SKILL.md` from this installation and its required references. Follow that workflow and load adjacent stage skills when routed. Answer in English. Only use these notes: a meeting planned for 30 minutes took 45 minutes and two agenda items were added midway. Do not browse. Produce a research report separating facts, inferences, and unknowns.

Specify the absolute installation path if it is outside the host's current workspace. Native skill discovery is optional: explicit file loading is an integration approach for a host with the required file and command capabilities. `$` or `/` shortcuts are host syntax and are not required by the core.

Offline research selects `NONE`, skips provider configuration checks, and makes no research network calls. The host/model's normal connectivity and initial dependency downloads are separate. Supplied claims retain their provenance and are not automatically independently verified.

See [HOST_INSTRUCTIONS.md](HOST_INSTRUCTIONS.md) for complete host requirements, stage loading, MCP registration, key configuration, and limits.

## Outputs and language

| Request | Endpoint and result |
|---|---|
| Understand a problem | `UNDERSTAND` → `RESEARCH_REPORT` |
| Decide a general solution | `DECIDE` + `GENERAL` → `FORMAL_DOCUMENT` |
| Design a complete product/software solution | `DECIDE` + `PRODUCT_SOFTWARE` → PRD and technical specification |
| Product requirements only | `PRD_ONLY` → `01-prd.md` |
| Technical design only | `TECHNICAL_SPEC_ONLY` → `01-technical-solution-spec.md` |
| Explicitly scoped specification package | Optional `FINAL_SPEC_PACKAGE` |

For a PRD, state the users, behavior, constraints, and acceptance needs, and ask for a PRD only. For a technical problem, request a technical specification only without a PRD. Outputs end at analysis/design; implementation code and deployment are outside the workflow. Documents remain previews until explicitly accepted.

Chinese and English have equal support. Prose follows the current explicit language choice, then an applicable earlier preference, then the current request's language. A preference limited to final documents does not change interview language. Machine keys, enums, IDs, filenames, and original citations stay unchanged.

## Web research, costs, and limits

Web research uses user-supplied Brave, Exa, or Firecrawl keys and a local stdio MCP connection configured in the host. Only the research tools are exposed through MCP; connecting them does not install the full workflow. Plain chat without local file/command access cannot execute the full workflow, and remote-HTTP-only MCP hosts cannot directly connect to this server.

Authorized queries, public URLs, domains, and related request options go to the selected provider. Each core call selects one route and does not silently switch providers. Keys, host/model access, and applicable provider charges are your responsibility. The workflow call budget is not a monetary spending cap. Keep confidential material out of outbound requests. Host-native research requires explicit authorization for its scope.

The public checkout and release bundle both support manual core loading and the optional Codex adapter. The Codex guide is `adapters/codex/README.md`; `.agents/plugins/marketplace.json` points to the installation root, and `.codex-plugin/plugin.json` contains the inline MCP registration. No separate Codex download is needed.

There is no claim of end-to-end validation across all hosts. Automated schema, mock-provider, workflow, archive, and stdio checks do not prove live service availability or complete host behavior. No Claude Code or other native adapter is included here.

For failures, preserve safe error codes and request IDs, check the selected route's configuration and quota locally, and retain workflow artifacts before requesting recovery. Keep real credentials and private documents out of reports. Use private vulnerability reporting if the source repository host enables it; otherwise request a private channel without publishing sensitive details.

The included `LICENSE` and `NOTICE.md` describe licensing and attribution.
