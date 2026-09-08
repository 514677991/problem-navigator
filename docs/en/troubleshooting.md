[简体中文](../zh-CN/troubleshooting.md) · [Home](../../README.md)

# Troubleshooting

| Symptom | What to check |
|---|---|
| Host cannot import the ZIP | Use its own discovery or explicit file-loading mechanism and follow the [generic quick start](quickstart.md). The single bundle includes optional Codex metadata, not a universal import protocol. |
| Host does not follow the workflow | Confirm that it read the complete entry and required stage skills, can write artifacts and run the Python helper, and can ask for document acceptance. Plain chat or MCP tools alone are insufficient. |
| Codex adapter is missing or `codex plugin` is unknown | Follow the dedicated [Codex guide](../../adapters/codex/README.md), check installed CLI support, enable the adapter, and start a new task. |
| MCP launches only in one working directory | Configure the generic command with the absolute installed `mcp/web-research-mcp` path; do not rely on a host-specific `cwd` field. |
| Tools are exposed under different names | Discover actual names and schemas; host prefixes may differ. Only four research tools are exposed, not the entire workflow. |
| Host accepts only remote HTTP MCP | The current server is stdio-only; that transport cannot connect directly. No hosted endpoint is bundled. |
| `uv` cannot be found | Ensure the desktop host, not just your current shell, sees `uv` on `PATH`; restart after changing it. |
| Python or dependency resolution fails | Confirm Python 3.11+ and run the locked `uv sync` from the [quick start](quickstart.md). A first install needs downloads. |
| Offline launch check cannot start | Prepare dependencies with canonical `uv sync --locked --project mcp/web-research-mcp --extra dev`, build the ZIP, then use `--archive` with `--mode direct` or `--mode declared` as shown in the development guide. The verifier's child uses offline cache. |
| `NOT_CONFIGURED` | Configure the provider for the selected route, or explicitly select a configured compatible route. `NONE` research needs no key. |
| `config_state: "INVALID"` | Check UTF-8 JSON, integer `schema_version: 1`, supported fields, and nonempty keys. One file error invalidates all file settings; environment keys can still work. |
| A file key is ignored | A present provider environment variable overrides the file, even when its value is empty or invalid. Inspect variable presence without printing secrets. |
| `AUTH_FAILED` | Check the selected provider's key locally and replace revoked/invalid credentials. A configured status is not a live authentication test. |
| `RATE_LIMITED` or `QUOTA_EXHAUSTED` | Check the provider account and its limits. The server also has a local rate limit; repeated immediate retries may worsen it. |
| `INVALID_REQUEST` | Check route and filter compatibility, query lengths, and public URL requirements in the [MCP reference](../../mcp/web-research-mcp/README.md). |
| `NETWORK_ERROR` or `PROVIDER_ERROR` | Check connectivity and provider availability. Save the safe error code and request ID. No automatic provider switching is performed. |
| `NO_RESULTS` or truncated evidence | Narrow the question or retrieve a relevant passage through a compatible authorized route. Keep the evidence gap visible. |
| Workflow stops on missing/invalid artifacts | Preserve the workflow and referenced artifacts. Identify the missing/stale input and request explicit regeneration from valid retained inputs; do not invent history or reset counts. |
| Bundle mirror drift check fails | Edit canonical core/adapter sources, run `scripts/sync_plugin_payload.py --write`, then `--check`. |
| Layout validator rejects the source root | Pass the generated mirror or extracted ZIP directory; the source repository has a development layout. |

For a bug report, include release/MCP version, integration method, host name/version, OS, Python/uv versions, a minimal sanitized reproduction, safe error code/request ID, and expected versus observed behavior. Exclude API keys, full config files, raw private documents, and sensitive URLs. Report vulnerabilities through the [security process](../../SECURITY.md).

Generated analysis can still contain unsupported inferences. Request a correction identifying the affected claim; the workflow should reopen relevant evidence and withdraw stale downstream results. Passing automated checks does not replace this factual review.
