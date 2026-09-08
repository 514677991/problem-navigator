[简体中文](../zh-CN/development.md) · [Home](../../README.md)

# Development and maintenance

Develop the shared skills and Python/MCP core here, and build one release archive with optional Codex integration metadata.

## Bootstrap a clean clone

With Python 3.11+ and `uv` on `PATH`, run from the repository root:

```sh
uv sync --locked --project mcp/web-research-mcp --extra dev
uv run --locked --project mcp/web-research-mcp --extra dev pytest -q
```

The first sync downloads dependencies. Subsequent offline runs are possible after the necessary runtime and packages are cached. No live provider key is needed for these tests. Configuration fixtures isolate the test process from the user's research settings.

## Edit the canonical sources

| Location | Role |
|---|---|
| `skills/` | Entry skill, stage instructions, artifact schema, workflow control helper |
| `mcp/web-research-mcp/` | Provider-independent core, provider adapters, stdio MCP server, lockfile |
| `release.json` | Host-neutral release metadata |
| `adapters/generic/` | Canonical archive-root README pair and host instructions |
| `adapters/codex/` | Canonical Codex manifest with inline MCP registration, UI files, and README pair |
| `plugins/problem-navigator/` | Generated unified bundle mirror; do not edit directly |
| `.agents/plugins/marketplace.json` | Source catalog points to the mirror; released catalog points to the bundle root |
| `tests/` | Workflow, protocol, provider, and packaging checks |

Edit skills and MCP source in their canonical locations, and host-specific files under the corresponding adapter. Keep host invocation syntax out of shared workflow routing. Then regenerate the unified mirror:

```sh
uv run --locked --project mcp/web-research-mcp python scripts/sync_plugin_payload.py --write
uv run --locked --project mcp/web-research-mcp python scripts/sync_plugin_payload.py --check
```

The sync script keeps the generated bundle aligned with canonical source and license/notice files. Direct edits to generated files will be overwritten. If synchronization fails, fix the cause and rerun `--write`, then `--check`.

## Validate and build

```sh
uv run --locked --project mcp/web-research-mcp python scripts/validate_plugin.py plugins/problem-navigator
uv run --locked --project mcp/web-research-mcp python scripts/build_plugin_zip.py
uv run --locked --project mcp/web-research-mcp --extra dev python tests/verify_plugin_mcp_registration.py --archive dist/problem-navigator-2.1.0.zip --mode direct
uv run --locked --project mcp/web-research-mcp --extra dev python tests/verify_plugin_mcp_registration.py --archive dist/problem-navigator-2.1.0.zip --mode declared
```

The launch verifier extracts the same archive to a temporary directory for each mode. `direct` constructs the stdio command using the extracted project's absolute path. `declared` checks the inline `mcpServers` registration in `.codex-plugin/plugin.json`. Both use temporary user configuration, no provider keys, and dependencies cached by the canonical bootstrap, offline. They verify four tool names, strict input schemas, local status, and safe `NOT_CONFIGURED` failure. They do not launch an AI host or create runtime files in the source mirror.

The build writes `dist/problem-navigator-2.1.0.zip` and its `.zip.sha256` checksum. The name and version follow `release.json`. The archive contains shared skills/MCP once, root user instructions, optional Codex manifest/UI metadata, the Codex guide under `adapters/codex/`, and an archive-local marketplace whose `source.path` is `.`. Tests, caches, credentials, and workflow artifacts are excluded.

To validate the extracted layout separately, extract the ZIP into a temporary directory and run the following with its actual path:

```sh
uv run --locked --project mcp/web-research-mcp python scripts/validate_plugin.py "<EXTRACTED_BUNDLE_ROOT>"
```

The validator checks the generated mirror or an extracted distribution. The development repository has a different layout. Review the archive contents and checksum before sharing.

## Release review

1. Keep English and Chinese user documentation aligned, including examples and limitations.
2. Review schema/workflow compatibility, update release metadata and the changelog, and refresh `uv.lock` deliberately when dependencies change. Keep adapter metadata aligned with `release.json`.
3. Sync the unified mirror, run relevant tests and its validator, then build the ZIP, inspect/validate the extracted layout, and run its direct and declared launch checks.
4. Record actual platform, tool versions, commands, results, and untested scope in the [verification report](../VERIFICATION.md).
5. Test representative English and Chinese prompts in a fresh session of each host before claiming end-to-end coverage for that host. Check complete skill loading, local helper execution, artifact persistence, and acceptance. Live provider tests require explicitly supplied credentials and an approved research scope.

Windows and Linux CI definitions are a portability check to run, not proof that both platforms passed. Only actual completed runs support a passing claim. Mock tests and stdio checks cannot establish live service compatibility or the quality of a generated analysis. See [verification scope](../../mcp/web-research-mcp/VERIFICATION.md).
