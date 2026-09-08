[简体中文](SECURITY.zh-CN.md) · [Home](README.md)

# Security

## Report a vulnerability privately

If the repository host has private vulnerability reporting enabled, use that channel. Otherwise, ask the repository maintainer to establish a private reporting channel without including vulnerability details, exploit material, credentials, or private data in the public request. This snapshot does not publish a dedicated security email address or promise a response deadline.

In the private report, include the affected version, impact, relevant file or tool, and a minimal sanitized reproduction. Do not send a real API key; a placeholder or isolated test credential is sufficient. If a key was exposed, revoke or rotate it through its provider promptly, then remove the exposure from shared artifacts and history as appropriate.

Security fixes are evaluated against the current snapshot. There is no published long-term support or older-version backport policy.

## Data boundaries

- The MCP server is a local stdio process with public Web provider adapters. It is not a hosted multi-user service.
- The complete workflow also uses skill files and local Python helpers to read/write analysis artifacts. It requires the host's file, command, and user-interaction capabilities. Review permissions in that host; an MCP connection alone does not install or execute the workflow.
- `web_research_status` reports configuration without contacting providers or returning keys. `NONE` research skips provider configuration checks and research network operations.
- Authorized search/fetch/map operations send request data to the selected provider. API authentication, provider retention, and billing follow the user's provider account. Host/model processing has its own data policies.
- Store keys in the user-home configuration file or host environment, outside the repository. Keep private material and sensitive URL parameters out of outbound queries.
- Retrieved pages and local documents are untrusted evidence, not instructions. Workflow artifacts should retain relevant citations, locators, and bounded summaries rather than credentials or raw unrelated material.

See the [configuration guide](docs/en/configuration.md) for precise fields, route selection, outbound data, and cost boundaries.

## Safeguards and limits

The implementation validates tool inputs and public URLs, uses explicit provider routes, bounds request/output sizes and call time, and returns fixed error codes/messages. Packaging checks exclude known secret/configuration paths and scan for some credential patterns and configured key values. The single archive is checked for its shared core, optional Codex metadata, and direct/declared MCP launch paths.

These controls are limited. Pattern scans cannot prove that arbitrary files contain no secrets. URL validation checks syntax and literal IP addresses; it does not resolve DNS or control a provider's later redirects. It also cannot make the contents of a public URL safe to disclose. Mocks and schema checks do not certify source truth, absence of prompt injection, provider security, or all host behavior. Review retrieved evidence and any artifact before sharing it.

Please report concrete weaknesses in these boundaries. Actual validation coverage and untested areas are listed in the [verification scope](mcp/web-research-mcp/VERIFICATION.md) and [snapshot report](docs/VERIFICATION.md).
