[简体中文](README.zh-CN.md) · English

# Problem Navigator

A general-purpose AI plugin that turns an unclear problem into an evidence-backed research report, a decision, or a design specification. Its shared skills and Python/MCP core support general problems and product/software work in Chinese and English. Codex is one host adapter.

Start with what you know, choose whether public Web research is needed, review the evidence, and receive a document with explicit assumptions and unresolved questions. The workflow ends at analysis and design; implementation code and deployment are outside its scope.

**Snapshot:** plugin `2.1.0`; bundled research MCP `0.2.0`. **License:** [MIT](LICENSE), with [attribution and dependency notes](NOTICE.md).

## Quick start

Use an AI host that can read complete skill files, write local artifacts, and execute Python commands, with Python **3.11+** and `uv` on its `PATH`. Clone this repository or extract `problem-navigator-2.1.0.zip`, keeping `skills/` and `mcp/` together. From that root, run:

```sh
uv sync --locked --project mcp/web-research-mcp
```

The first `uv sync` may download Python dependencies. Have your host load the complete `skills/problem-navigator/SKILL.md` entry skill, follow its references, and load the adjacent stage skills when routed. If the host has no skills mechanism, explicitly ask it to read those files. No `$` or `/` command prefix is required by the core. See the [generic quick start](docs/en/quickstart.md) or the [Codex adapter guide](adapters/codex/README.md).

Try this without any provider keys:

> Read and follow `skills/problem-navigator/SKILL.md` and its required references. Answer in English. Using only the following notes, help me understand why our weekly meeting overruns: planned duration 30 minutes; last three meetings lasted 45, 50, and 55 minutes; agenda items were added during each meeting. Do not browse. Produce a research report separating facts, inferences, and unknowns.

`NONE` research uses supplied material and reasoning without research network calls or provider configuration checks. Host/model connectivity and initial dependency downloads are separate from this offline research mode.

For public Web evidence, register the local stdio MCP server in your host and supply your own Brave, Exa, or Firecrawl API key using the [configuration guide](docs/en/configuration.md). No key is included, and you do not need all three providers.

The single ZIP contains the shared core once, general host instructions, and optional Codex metadata. It is a portable file bundle, not a universal one-click import format. MCP-only integration exposes four research tools; the complete workflow also needs skill loading and local file/command execution. Plain chat cannot execute the full workflow. Hosts supporting only remote HTTP MCP cannot connect directly to the current stdio entry point. Other hosts, including Claude Code, have integration guidance but no claimed host end-to-end validation.

## What you can produce

The workflow has two independent choices: goal (`UNDERSTAND` or `DECIDE`) and content profile (`GENERAL` or `PRODUCT_SOFTWARE`). State the desired result in ordinary language; you do not need to edit these fields yourself.

| Desired result | Endpoint | Scope |
|---|---|---|
| Understand a problem | `RESEARCH_REPORT` | Evidence, synthesis, limitations, open questions |
| Decide a general solution | `FORMAL_DOCUMENT` | Formal solution report |
| Design a complete product/software solution | `FORMAL_DOCUMENT` | PRD and technical solution specification with traceable requirements |
| Define product requirements only | `PRD_ONLY` | `01-prd.md`; product scope and acceptance criteria |
| Resolve a technical design problem | `TECHNICAL_SPEC_ONLY` | `01-technical-solution-spec.md`; no invented PRD |
| Reorganize an accepted design into a specification package | `FINAL_SPEC_PACKAGE` | Optional, explicitly scoped design deliverable |

One workflow records framing, research design, evidence, decision readiness, option selection, refinement, documentation, and optional decomposition. Only the stages needed for the endpoint run. The final document remains a preview until you accept it.

Chinese and English have equal support. Interviews, explanations, and documents follow your current explicit language choice, then an applicable earlier preference, then the language of your current request. A preference limited to the final report does not change interview language. Machine keys, enum values, IDs, filenames, and original source citations stay unchanged. See [three matched examples](docs/en/examples.md).

## Costs and data

This repository supplies code and skills under MIT; it does not supply a host/model subscription or provider credits. Your host/model usage and any Brave, Exa, or Firecrawl charges follow your own accounts. The workflow's call budget is an operation limit, not a spending cap.

The MCP server runs locally over stdio. Authorized Web operations send queries, URLs, domain filters, and related request options to the selected provider. A core call selects one route and does not silently switch providers. Host-native research requires explicit authorization covering its scope. Keep credentials and confidential details out of prompts, published evidence, and issue reports. Details: [configuration](docs/en/configuration.md) and [security](SECURITY.md).

## Documentation and development

- [Quick start](docs/en/quickstart.md), [provider configuration](docs/en/configuration.md), and [examples](docs/en/examples.md)
- [Troubleshooting](docs/en/troubleshooting.md) and [MCP tool reference](mcp/web-research-mcp/README.md)
- [Development and maintenance](docs/en/development.md), [contributing](CONTRIBUTING.md), and [changelog](CHANGELOG.md)
- [Verification scope](mcp/web-research-mcp/VERIFICATION.md) and [snapshot verification report](docs/VERIFICATION.md)

Canonical source is in `skills/` and `mcp/web-research-mcp/`; `release.json` owns release metadata. `adapters/generic/` supplies the bundle's root user instructions, and `adapters/codex/` owns optional Codex metadata and guides. `plugins/problem-navigator/` is the generated unified bundle mirror. The source marketplace points to that mirror; the released marketplace points to the extracted bundle root.

Build the single `problem-navigator-2.1.0.zip`; see [development](docs/en/development.md). Codex MCP registration is inline in `.codex-plugin/plugin.json`. No additional archive is needed for the Codex adapter; no other native host adapter is bundled in this snapshot.

Automated checks cover schemas, workflow controls, mocked provider behavior, packaging, and stdio launch. They do not establish live provider availability, research quality, or successful end-to-end use in an AI host. Read the verification report for actual runs and platform coverage.
