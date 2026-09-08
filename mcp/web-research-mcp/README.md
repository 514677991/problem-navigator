[English guide](../../docs/en/configuration.md) · [中文配置指南](../../docs/zh-CN/configuration.md)

# Web Research MCP

Version `0.2.0`, bundled with Problem Navigator `2.1.0`. The single release includes one provider-independent Python core with a thin local stdio MCP surface, usable directly or through the optional Codex adapter. / 版本 `0.2.0`，随 Problem Navigator `2.1.0` 提供；唯一发行包包含一份独立 Python 研究核心与本地 stdio MCP 接口，可直接接入或通过可选 Codex 适配使用。

## Run / 运行

Requires Python 3.11+ and `uv` on `PATH`. From the repository root: / 需要 Python 3.11+ 与 `PATH` 中的 `uv`。在仓库根目录运行：

```sh
uv sync --locked --project mcp/web-research-mcp
uv run --locked --project mcp/web-research-mcp web-research
```

The second command starts a stdio server waiting for an MCP client; it is not an interactive search prompt. For host integration, configure the following command using the actual absolute installation path: / 第二条命令启动等待 MCP 客户端的 stdio 服务，并非交互搜索提示符。接入宿主时，使用真实绝对安装路径配置以下命令：

```sh
uv run --locked --isolated --project "<ABSOLUTE_INSTALL_PATH>/mcp/web-research-mcp" web-research
```

Host configuration formats differ; no `cwd` field or host-specific tool prefix is assumed. The server is stdio-only and does not provide a remote HTTP endpoint. The same release includes inline Codex registration in `.codex-plugin/plugin.json`. See the configuration guides above for a JSON-shaped template for other capable hosts. / 宿主配置格式各异，不假定 `cwd` 字段或宿主工具前缀。服务仅支持 stdio，不提供远程 HTTP 端点；同一发行包在 `.codex-plugin/plugin.json` 中内联 Codex 注册。其他具备能力的宿主可参考顶部配置指南中的 JSON 形式模板。

The initial dependency setup may need downloads. Tests need the `dev` extra; see [development](../../docs/en/development.md) / [开发指南](../../docs/zh-CN/development.md).

## Tools / 工具

| Tool | Input / 输入 | Behavior / 行为 |
|---|---|---|
| `web_research_status` | `{}` | Local configuration only; no key output or network / 仅本地配置，不返回密钥、不联网 |
| `web_search` | `query`, optional `direction`, `route`, `freshness`, `domains` | One selected search route / 一条选定搜索路由 |
| `web_fetch` | `url`, optional `query`, `route` | One public URL / 一个公开 URL |
| `web_map` | `url`, optional `query` | Discover public URLs under a starting URL / 从起始 URL 发现公开链接 |

Unknown fields are rejected. `direction` is `auto`, `news`, `semantic`, `academic`, or `developer`; `route` is `primary` or `alternate`; `freshness` is `""`, `day`, `week`, `month`, or `year`. / 拒绝未知字段；参数枚举保持英文原值。

These four tools do not include workflow prompts/resources. Complete analysis additionally requires the shared skills, local file access, Python execution, and user interaction. Hosts may prefix tool names; discover actual names and schemas before calling. / 这四个工具不包含工作流 prompts/resources；完整分析还需要共享技能、本地文件访问、Python 执行与用户交互。宿主可能为工具名添加前缀，调用前应发现实际名称和结构。

Example MCP arguments, requiring the corresponding configured provider and authorized scope: / MCP 参数示例，需要配置对应服务商并授权范围：

```json
{
  "query": "public documentation atomic transactions",
  "direction": "auto",
  "route": "alternate",
  "freshness": "",
  "domains": []
}
```

This explicitly selects Exa. It is not a recorded successful research call. / 此示例明确选择 Exa，并非已经成功执行的研究记录。

## Routes and limits / 路由与限制

| Operation / 操作 | `primary` | `alternate` |
|---|---|---|
| `auto` search | Brave | Exa |
| `news` search | Brave | Exa |
| `semantic` search | Exa | Unsupported / 不支持 |
| `academic` search | Firecrawl | Exa |
| `developer` search | Firecrawl | Brave |
| Fetch | Firecrawl | Exa |
| Map | Firecrawl | Unsupported / 不支持 |

One core call selects one provider with no automatic cross-provider fallback. The transport may retry that provider once within its deadline. / 每次核心调用选择一家服务商，不自动跨服务商回退；传输层可在截止时间内对同一服务商重试一次。

- Queries: at most 2,000 characters; Brave also limits to 400 characters and 50 whitespace-separated words. / 查询最多 2,000 字符；Brave 另限 400 字符与 50 个空白分隔词。
- Domains: at most 20 public hostnames; Brave rejects domain filters. Firecrawl academic search rejects domain and freshness filters. / 最多 20 个公开域名；Brave 拒绝域名过滤，Firecrawl 学术搜索拒绝域名和时效过滤。
- Firecrawl fetch requires an empty `query`; use Exa's alternate fetch for a directed query. / Firecrawl fetch 的 `query` 必须为空；定向查询可使用 Exa 备用 fetch。
- URLs must use public HTTP(S) syntax and default ports without userinfo or recognized signed/token query parameters. Validation checks syntax and literal IPs, not DNS resolution or provider redirects. / URL 必须符合公开 HTTP(S) 语法，使用默认端口，不含用户认证信息或已识别的签名/token 查询参数；验证检查语法和字面 IP，不检查 DNS 解析或服务商重定向。
- Results are bounded: up to 10 search sources, 2,000 characters per snippet, 20,000 characters of fetched content, and 50 mapped URLs. Inspect `truncated`. / 输出最多 10 条搜索来源、每条 2,000 字符摘要、20,000 字符正文与 50 个 map URL；请检查 `truncated`。
- The core call deadline is 60 seconds. The stdio server allows at most two concurrent network operations and 60 operations per process-local minute window. / 核心调用截止时间为 60 秒；stdio 服务最多并发两项网络操作，每个进程本地分钟窗口最多 60 次操作。

The workflow's separate operation budget does not cap provider spending. / 工作流另有操作预算，但它不限制服务商金额。

## Configuration and failures / 配置与失败

Keys come from the user's `.problem-navigator/web-research.json` or `BRAVE_API_KEY`, `EXA_API_KEY`, and `FIRECRAWL_API_KEY` environment variables. See the linked configuration guides for valid JSON and precedence. No custom provider endpoint is supported. / 密钥来自用户主目录配置文件或对应环境变量；有效 JSON 和优先级见顶部配置指南，不支持自定义服务地址。

Status values describe local configuration, not live authentication or quota. Calls use `INVALID_REQUEST`, `NOT_CONFIGURED`, `AUTH_FAILED`, `RATE_LIMITED`, `QUOTA_EXHAUSTED`, `NETWORK_ERROR`, or `PROVIDER_ERROR` with a safe request ID/message. `NO_RESULTS` is a successful empty result, not an authentication error. / 状态只说明本地配置，不证明线上认证或额度；失败使用固定错误码和安全请求 ID/信息。`NO_RESULTS` 表示成功但无结果，并非认证错误。

Public Web requests send query/URL/filter data to the selected provider and may incur charges on the user's account. Offline `NONE` workflows do not call these research tools or status. Host/model processing is separate. / 公开网页请求向所选服务商发送查询、URL 与过滤数据，可能在用户账户产生费用。离线 `NONE` 工作流不调用这些研究工具或状态；宿主/模型处理另行适用。

See [verification / 验证](VERIFICATION.md), [security / 安全](../../SECURITY.md), and [license / 许可证](../../LICENSE).
