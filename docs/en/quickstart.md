[简体中文](../zh-CN/quickstart.md) · [Home](../../README.md)

# Generic quick start

## 1. Prepare the host

Use an AI host that can read complete Markdown skill files, follow their references, read/write local workflow artifacts, and execute local Python commands. Python 3.11+ and `uv` must be available to that host. Native skill support is convenient; explicit file loading also works as an integration approach. Plain chat without file and command access cannot execute the complete workflow.

Clone the source repository or extract `problem-navigator-2.1.0.zip`. Keep `skills/` and `mcp/` under the same installation root. From that root, check:

```sh
uv --version
uv python find ">=3.11"
```

If a command is missing, install or configure that prerequisite first. A terminal's environment may differ from the AI host's environment; restart the host after changing `PATH` or provider environment variables.

Prepare locked dependencies:

```sh
uv sync --locked --project mcp/web-research-mcp
```

This first setup normally needs network access. Offline research does not mean a clean machine can download its runtime offline.

## 2. Load the workflow instructions

Have the host load the entire `skills/problem-navigator/SKILL.md` entry file, including its referenced workflow contract and artifact schema. When it routes to another skill, load that stage's complete `SKILL.md` from the adjacent directory. Keep scripts and references in place; copying only the entry text loses required dependencies.

If your host supports skill discovery, use its documented registration mechanism for these skill directories. If it does not, begin with an explicit instruction such as:

> The installation root is `<absolute installation path>`. Read the complete `skills/problem-navigator/SKILL.md` there and its required references, then use that workflow for my request. Resolve the adjacent stage skills from this installation. Store analysis artifacts in my chosen workspace.

Replace the path with your installation location. `$problem-navigator`, `/problem-navigator`, and other shortcuts are host syntax, not required by the core. The single ZIP includes optional Codex metadata, but does not promise one-click import into every host.

For the included Codex adapter, use the [Codex installation guide](../../adapters/codex/README.md) in the same bundle; no additional archive is needed. For Claude Code or another host, consult that host's skill and MCP documentation and verify its behavior locally; no additional native host adapter is bundled here.

## 3. Run an offline example

> Use the loaded problem-navigator workflow in English. Only use my notes: a volunteer reading group wants to choose between weekly and fortnightly meetings; members have not yet been surveyed. Do not browse. Help us understand the decision and produce a research report, marking preferences and attendance estimates as unknown.

Expected behavior: select `NONE`, clarify material gaps, analyze the supplied evidence, and present a report preview. There should be no provider-key check or research network call. Accept the reviewed report explicitly when it is ready; its limitations should remain visible.

The workflow is stored in your analysis workspace under `.problem-navigator/workflows/`. Treat workflow files and linked artifacts as a set when continuing or backing up your work. Do not run concurrent writers against one workflow.

## 4. Register MCP for Web research

Follow [provider configuration](configuration.md) to register the stdio server with an absolute installation path and add your own keys. MCP configuration differs by host. Registration alone exposes four research tools; it does not install the skill workflow from step 2.

Start a Web request and ask the workflow to check the relevant configured capabilities. A local status response confirms configuration only; a real request is needed to establish live authentication and quota. That request may incur provider charges. Hosts supporting only remote HTTP MCP cannot connect directly to this stdio entry point.

You can explicitly authorize host-native tools for a defined research scope if your host provides them. This is separate from the bundled provider routes and uses the host's own accounts and policies.

## Optional: use cached dependencies offline

The canonical `uv sync` in step 1 prepares the dependency cache. After the dependencies and a compatible Python runtime are cached, `uv`'s `--offline` option can be used for local commands. Do not create a virtual environment inside the source repository's generated plugin mirror; development checks expect that payload to match the canonical sources.

The archive launch verifier also requires the cached runtime. `NONE` only guarantees that this workflow does not perform research network operations; the AI host may still need its normal model connection.

## Integration guidance and verification limits

The [Agent Skills specification](https://agentskills.io/specification) describes skill content, while its [client integration guide](https://agentskills.io/client-implementation/adding-skills-support) explains host loading responsibilities. [Claude Code's skill documentation](https://code.claude.com/docs/en/skills) and [MCP documentation](https://code.claude.com/docs/en/mcp) describe that host's mechanisms. These are integration references, not evidence that this package has passed an end-to-end run there. Test the offline example, artifact persistence, language choice, and authorized Web path in your actual host before relying on the integration.

Next: [examples](examples.md), [troubleshooting](troubleshooting.md), or [development](development.md).
