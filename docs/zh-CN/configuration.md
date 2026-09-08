[English](../en/configuration.md) · [首页](../../README.zh-CN.md)

# 服务商配置

离线研究（`NONE`）可跳过本页：无需服务商密钥，也不要求 MCP 状态检查。公开网页研究只需为将要使用的路由提供密钥。插件不会创建账户、购买额度或内置凭据。

## 注册本地 MCP 服务

使用宿主的本地 stdio MCP 配置，启动命令为：

```sh
uv run --locked --isolated --project "<ABSOLUTE_INSTALL_PATH>/mcp/web-research-mcp" web-research
```

将 `<ABSOLUTE_INSTALL_PATH>` 替换为实际安装根目录。此命令不依赖宿主当前工作目录。常见 JSON 形式的模板如下：

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

使用前必须替换路径；模板中的位置并非可直接使用的安装路径。Windows JSON 路径使用正斜杠或转义反斜杠。宿主的配置外层格式、文件位置与权限控制可能不同；`mcpServers` 只是示例，不是统一文件格式。请遵循宿主自身文档，不假定存在 `cwd` 字段。

当前服务仅支持 stdio，注册四个工具，不提供工作流 prompts/resources。仅支持远程 HTTP MCP 的宿主不能直接连接。连接后发现实际工具名与结构，宿主可能为名称添加前缀。完整分析还需要[入门指南](quickstart.md)中的技能与本地执行能力。

## 在本地配置密钥

在用户主目录的 `.problem-navigator/web-research.json` 创建 UTF-8 JSON 文件。Windows 路径为 `%USERPROFILE%\.problem-navigator\web-research.json`；POSIX 系统为 `~/.problem-navigator/web-research.json`。文件应放在仓库之外，并仅允许自己的账户访问。

仅配置 Brave 的最小示例：

```json
{
  "schema_version": 1,
  "brave": {
    "api_key": "<YOUR_BRAVE_API_KEY>"
  }
}
```

同时配置全部支持的服务商：

```json
{
  "schema_version": 1,
  "brave": { "api_key": "<YOUR_BRAVE_API_KEY>" },
  "exa": { "api_key": "<YOUR_EXA_API_KEY>" },
  "firecrawl": { "api_key": "<YOUR_FIRECRAWL_API_KEY>" }
}
```

在本地将占位文本替换为自己的密钥；不使用的服务商可直接省略。这些示例是有效 JSON，但占位字符串无法完成真实请求的认证。不要添加注释、尾逗号、额外字段或自定义服务地址。`schema_version` 必须为整数 `1`。格式错误会使整个文件被拒绝。

也可以在启动 MCP 服务的宿主进程环境中设置 `BRAVE_API_KEY`、`EXA_API_KEY`、`FIRECRAWL_API_KEY` 中的一个或多个。只要某个环境变量存在，就覆盖文件中对应的值；空值或无效值会让该服务商处于未配置状态。其他服务商的文件配置不受影响。修改宿主环境后需重启宿主。

## 选择路由

核心每次操作使用一条明确路由。失败不会自动调用另一家服务商。工作流可以主动选择兼容的备用路由，并记录新增操作。

| 能力 | `primary` | `alternate` |
|---|---|---|
| `auto` 搜索 | Brave | Exa |
| `news` 搜索 | Brave | Exa |
| `semantic` 搜索 | Exa | 不支持 |
| `academic` 搜索 | Firecrawl | Exa |
| `developer` 搜索 | Firecrawl | Brave |
| Fetch | Firecrawl | Exa |
| Map | Firecrawl | 不支持 |

某服务商已配置，只代表其自身路由可选。例如只配置 Exa 时，`auto` 搜索可使用 `route: "alternate"`，默认 Brave 路由仍会返回 `NOT_CONFIGURED`。还需考虑过滤条件：Brave 路由拒绝 `domains`；Firecrawl 学术搜索拒绝时效与域名过滤；Firecrawl fetch 拒绝非空 `query`。详见 [MCP 说明](../../mcp/web-research-mcp/README.md)。

`web_research_status` 仅读取本地配置，不联网也不返回密钥。`CONFIGURED` 无法证明密钥有效或仍有额度。`config_state: "INVALID"` 表示配置文件有误；有效的环境变量密钥仍可能使某条路由可用。

## 费用与外发数据

适用的服务商费用与宿主/模型费用由你自己的账户承担。启用网页研究前，请在服务商账户中确认当前价格与限制。默认工作流预算为 40 次 search/fetch/map 操作，其中 6 次留给恢复。失败与经授权的宿主操作也计数。服务商重试、计费单位以及宿主 token 用量与该预算并非一一对应。

本地 stdio 服务将所选请求发送至 `api.search.brave.com`、`api.exa.ai` 或 `api.firecrawl.dev`。请求可能包含查询、目标公开 URL、域名、时效过滤及服务商专属选项。密钥发送至对应服务商完成认证。检索到的公开内容会返回宿主用于分析；宿主的数据处理独立于本插件。

尽量减少研究查询中的私人数据。公开 URL 仍可能在查询参数中携带敏感信息。本地材料不会自动成为公开网页来源，`NONE` 完全不使用研究服务商。宿主内置工具需要获得覆盖研究范围与外发数据的明确授权。另见[安全说明](../../SECURITY.zh-CN.md)。
