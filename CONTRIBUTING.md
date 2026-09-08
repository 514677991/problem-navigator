[简体中文](CONTRIBUTING.zh-CN.md) · [Home](README.md)

# Contributing

Chinese and English contributions are welcome. Describe the concrete problem, the expected behavior, and a small reproducible example. For security-sensitive reports, use [SECURITY.md](SECURITY.md).

## Work on a change

1. Read the [development guide](docs/en/development.md) and bootstrap with Python 3.11+ and locked `uv` dependencies.
2. Make focused changes in the canonical `skills/` or `mcp/web-research-mcp/` source. Preserve the single workflow, its goal/profile distinction, and host-neutral routing. Put host-specific metadata and documentation under `adapters/`; Codex is one adapter, not the identity of the shared core.
3. Add or update meaningful regression coverage for changed behavior. A prose-only edit normally needs a careful read and link check.
4. Update the corresponding English and Chinese documentation together. Translate user-facing prose; preserve machine keys, enums, IDs, filenames, and original citations. If you cannot review both languages, say which translation needs review.
5. Regenerate and check the unified bundle mirror, verify its shared core and optional adapter metadata, and include actual results in the change description. Never claim a live service or host end-to-end run based on mocks or stdio checks.

```sh
uv sync --locked --project mcp/web-research-mcp --extra dev
uv run --locked --project mcp/web-research-mcp python scripts/sync_plugin_payload.py --write
uv run --locked --project mcp/web-research-mcp python scripts/sync_plugin_payload.py --check
uv run --locked --project mcp/web-research-mcp --extra dev pytest -q
```

For packaging or MCP changes, build the single archive and run its validator and both direct/declared launch checks in the development guide. `release.json` owns release metadata; edit adapter READMEs in `adapters/`, not the generated `plugins/problem-navigator/` mirror. Keep real keys, local workflows, private source material, caches, and virtual environments out of commits and archives.

## Submit a reviewable contribution

Use the repository host's available issue or pull-request mechanism. State what changed, why it matters, how it was checked, and any remaining limits. For workflow/schema changes, describe the effect on saved artifacts and compatibility. For a new provider or route, document outbound data, configuration, cost boundaries, and failures.

Maintain canonical sources and the generated bundle together. The changelog and verification report should describe the actual release contents and completed checks.

By contributing, provide only material you are entitled to submit under the repository's [MIT license](LICENSE). Preserve applicable copyright and license notices, and record third-party provenance in [NOTICE.md](NOTICE.md) when needed. Be specific, respectful, and constructive in review; disagreement about evidence or design is welcome.
