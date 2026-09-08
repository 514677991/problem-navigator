[简体中文](../zh-CN/configuration.md) · [Home](../../README.md)

# Provider configuration

For offline research (`NONE`), skip this page: no provider key or MCP status check is required. For public Web research, supply keys for the routes you intend to use. The plugin does not create accounts, purchase credits, or bundle credentials.

## Register the local MCP server

Use your host's local stdio MCP configuration. The launch command is:

```sh
uv run --locked --isolated --project "<ABSOLUTE_INSTALL_PATH>/mcp/web-research-mcp" web-research
```

Replace `<ABSOLUTE_INSTALL_PATH>` with the actual installation root. This command does not depend on the host's current working directory. A common JSON-shaped template is:

```json
{
  "mcpServers": {
    "web-research": {
      "command": "uv",
      "args": [
        "run", "--locked", "--isolated", "--project",
        "<ABSOLUTE_INSTALL_PATH>/mcp/web-research-mcp",
        "web-research"
      ]
    }
  }
}
```

Replace the path before use; it is not a usable installed location as written. Use forward slashes or escaped backslashes in Windows JSON paths. The host's outer configuration format, file location, and permission controls may differ; `mcpServers` is an example, not a universal file format. Follow the host's own documentation. No `cwd` field is assumed.

The current server is stdio-only and registers four tools, with no workflow prompts/resources. A host supporting only remote HTTP MCP cannot connect directly to it. After connection, discover actual tool names and schemas; host-specific prefixes may be added. Complete analysis also requires the skills and local execution described in the [quick start](quickstart.md).

## Configure keys locally

Create a UTF-8 JSON file in your user home at `.problem-navigator/web-research.json`. On Windows this is `%USERPROFILE%\.problem-navigator\web-research.json`; on POSIX systems it is `~/.problem-navigator/web-research.json`. Keep it outside the repository and restrict access to your account.

A minimal example for Brave:

```json
{
  "schema_version": 1,
  "brave": {
    "api_key": "<YOUR_BRAVE_API_KEY>"
  }
}
```

An example with all supported providers:

```json
{
  "schema_version": 1,
  "brave": { "api_key": "<YOUR_BRAVE_API_KEY>" },
  "exa": { "api_key": "<YOUR_EXA_API_KEY>" },
  "firecrawl": { "api_key": "<YOUR_FIRECRAWL_API_KEY>" }
}
```

Replace placeholders locally with your own keys; omit providers you do not use. These examples are valid JSON, but their placeholder strings cannot authenticate real requests. Do not add comments, trailing commas, extra fields, or custom base URLs. `schema_version` must be the integer `1`. A malformed file is rejected as a whole.

Alternatively, set `BRAVE_API_KEY`, `EXA_API_KEY`, and/or `FIRECRAWL_API_KEY` in the environment of the host process that launches the MCP server. A present environment variable overrides the matching file value; an empty or invalid environment value leaves that provider unconfigured. Other providers' file settings are preserved. Restart the host after changing its environment.

## Choose a route

Each core operation uses one explicit route. Failure does not automatically call another provider. The workflow can deliberately select a compatible alternate route and records the additional operation.

| Capability | `primary` | `alternate` |
|---|---|---|
| Search `auto` | Brave | Exa |
| Search `news` | Brave | Exa |
| Search `semantic` | Exa | Unsupported |
| Search `academic` | Firecrawl | Exa |
| Search `developer` | Firecrawl | Brave |
| Fetch | Firecrawl | Exa |
| Map | Firecrawl | Unsupported |

A configured provider enables only its routes. For example, Exa alone can serve `auto` search with `route: "alternate"`; the default Brave route still reports `NOT_CONFIGURED`. Filter compatibility also matters: Brave routes reject `domains`, Firecrawl academic search rejects freshness/domain filters, and Firecrawl fetch rejects a nonempty `query`. See the [MCP reference](../../mcp/web-research-mcp/README.md).

`web_research_status` reads local configuration without making network requests or returning keys. `CONFIGURED` does not establish that a key works or has quota. `config_state: "INVALID"` identifies a bad config file; a valid environment key may still enable a route.

## Costs and outbound data

You pay any applicable provider and host/model charges through your own accounts. Check your provider account's current pricing and limits before enabling Web research. The default workflow budget is 40 search/fetch/map operations, including 6 reserved for recovery. Failures and authorized host operations count. Provider retries, billing units, and host tokens do not map one-to-one to this budget.

The local stdio server sends selected requests to `api.search.brave.com`, `api.exa.ai`, or `api.firecrawl.dev`. Requests can include queries, target public URLs, domains, freshness filters, and provider-specific options. Keys are sent to their provider for authentication. Retrieved public content is returned to the host for analysis; host data handling is separate from this plugin.

Minimize private data in research queries. A public URL can still contain sensitive query parameters. Local material is not automatically a public Web source, and `NONE` avoids the research providers entirely. Host-native tools require explicit authorization for their research scope and outbound data. See [security](../../SECURITY.md).
