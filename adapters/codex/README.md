[简体中文](README.zh-CN.md) · English

# Problem Navigator — Codex adapter

This is the Codex adapter for the general-purpose Problem Navigator plugin, release `2.1.0`, with local Web Research MCP `0.2.0`. The shared skills and Python/MCP core can also be integrated with other capable hosts; this guide covers only Codex. Turn general or product/software problems into evidence-backed reports and design specifications in Chinese or English. The workflow ends at analysis/design and does not generate implementation code or deploy a system.

## Enable the Codex adapter

Requirements: a Codex version supporting local plugins, Python 3.11+, and `uv` on the host's `PATH`.

From the **source repository root or the extracted release root** containing `.agents/plugins/marketplace.json`, run these commands yourself:

```sh
uv sync --locked --project mcp/web-research-mcp
codex plugin marketplace add .
codex plugin add problem-navigator@problem-navigator
```

Start a **new Codex task with the plugin enabled**. Commands depend on support in your installed Codex; inspect `codex plugin --help` when needed. The official [plugin testing guide](https://developers.openai.com/plugins/deploy/connect-chatgpt) describes installing from a local marketplace and testing in a new conversation.

Use a clone of the public repository or the single release archive `problem-navigator-2.1.0.zip`; no separate Codex download is needed. In both layouts, the catalog points to the installation root (`source.path: "."`) and uses the marketplace/plugin name shown above.

The first dependency sync may download packages. The inline `mcpServers` object in `.codex-plugin/plugin.json` launches the shared local stdio server through `uv`. The bundle does not use an independent `.mcp.json`. Skills and MCP core are included once and also support direct loading in other capable hosts.

This guide has the same `adapters/codex/` path in the public repository and release archive. See the [main README](../../README.md) for general use.

## Start without keys

> Use $problem-navigator. Answer in English. Using only my notes, help me understand why a meeting planned for 30 minutes took 45 minutes. We added two agenda items midway. Do not browse. Produce a research report separating facts, inferences, and unknowns.

Offline research selects `NONE`, skips provider configuration checks, and makes no research network calls. Initial runtime downloads and the Codex host/model connection are separate. Supplied claims are recorded with their provenance and are not automatically independently verified.

For a PRD, say “Deliver a PRD only” and describe users, behavior, constraints, and acceptance needs. For a pure technical problem, say “Deliver a technical solution specification only; do not create a PRD.” The plugin clarifies material gaps and presents a document preview for your acceptance.

## Language and outputs

Chinese and English have equal support. Prose follows the current explicit language choice, then an applicable earlier preference, then the current request's language. A preference limited to the final report does not change interview language. Keep machine keys, enum values, IDs, filenames, and original citations unchanged.

| Goal/profile | Endpoint and result |
|---|---|
| `UNDERSTAND`, either profile | `RESEARCH_REPORT` |
| `DECIDE` + `GENERAL` | `FORMAL_DOCUMENT`: formal solution report |
| `DECIDE` + `PRODUCT_SOFTWARE` | `FORMAL_DOCUMENT`: PRD and technical solution specification |
| Product requirements only | `PRD_ONLY`: `01-prd.md` |
| Technical design only | `TECHNICAL_SPEC_ONLY`: `01-technical-solution-spec.md` |
| Explicitly scoped specification package | `FINAL_SPEC_PACKAGE`: optional design-depth package |

One workflow stores state under the analysis workspace's `.problem-navigator/workflows/`. Preserve it together with referenced artifacts. Do not run concurrent writers on one workflow. Final documents remain previews until explicitly accepted.

## Optional public Web research

Supply your own keys in the UTF-8 user-home file `.problem-navigator/web-research.json`, outside this plugin and any source repository:

```json
{
  "schema_version": 1,
  "brave": { "api_key": "<YOUR_BRAVE_API_KEY>" },
  "exa": { "api_key": "<YOUR_EXA_API_KEY>" },
  "firecrawl": { "api_key": "<YOUR_FIRECRAWL_API_KEY>" }
}
```

Replace placeholders locally and omit unused providers. The file accepts no extra fields, comments, or custom endpoints. Alternatively, set `BRAVE_API_KEY`, `EXA_API_KEY`, and/or `FIRECRAWL_API_KEY` in the host environment. A present variable overrides its provider's file value; an empty/invalid variable leaves that provider unconfigured. Restart the host after environment changes.

| Operation | `primary` | `alternate` |
|---|---|---|
| Search `auto` / `news` | Brave | Exa |
| Search `semantic` | Exa | Unsupported |
| Search `academic` | Firecrawl | Exa |
| Search `developer` | Firecrawl | Brave |
| Fetch | Firecrawl | Exa |
| Map | Firecrawl | Unsupported |

Each core call selects one route; it does not silently switch providers on failure. `web_research_status` is local and returns configuration status without keys; it cannot prove live authentication or quota. `NONE` does not call it.

You supply any Codex/model access and pay applicable provider charges. The local server sends authorized queries, public URLs, domain filters, and related options to the selected provider; keep secrets and private details out of them. The workflow budget counts operations, not money. Host-native tools require explicit authorization for their research scope.

## Troubleshooting and verification

- Missing plugin: enable it and start a new task; confirm your Codex supports the local marketplace flow.
- Missing `uv`/Python: check the environment seen by the desktop host and prepare Python 3.11+ with locked dependencies.
- `NOT_CONFIGURED`: configure the selected provider or deliberately choose a compatible configured route.
- Invalid configuration: check UTF-8 JSON and exact supported fields. `CONFIGURED` is not proof that a key works.
- Authentication/quota/network errors: check the selected provider's account or connectivity. Share only safe error codes and request IDs.
- Missing/stale workflow artifacts: preserve files and request explicit regeneration from valid retained inputs; do not invent history or reset counters.

Automated checks cover schemas, mocked providers, workflow controls, packaging, and stdio registration. They do not establish live provider service or successful installed-Codex end-to-end use.

Licensed under MIT; the extracted archive includes `LICENSE` and `NOTICE.md`. Keep credentials out of issue reports. Use the repository host's private vulnerability reporting if enabled; otherwise request a private channel without exposing vulnerability details or secrets publicly.
