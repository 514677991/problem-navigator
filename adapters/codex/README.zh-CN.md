简体中文 · [English](README.md)

# Problem Navigator — Codex 适配

这是通用 Problem Navigator 插件的 Codex 适配，发行版本 `2.4.0`，内置本地 Web Research MCP `0.2.0`。共享技能和 Python/MCP 核心也可集成至具备所需能力的其他宿主；本指南仅介绍 Codex。将通用问题或产品/软件问题整理成有证据支撑的报告与设计规格，支持中文和英文。工作流止于分析/设计，不生成实现代码，也不部署系统。

## 启用 Codex 适配

需要支持本地插件的 Codex、Python 3.11+，以及宿主 `PATH` 中的 `uv`。

在包含 `.agents/plugins/marketplace.json` 的**源仓库根目录或发行包解压根目录**自行运行：

```sh
uv sync --locked --project mcp/web-research-mcp
codex plugin marketplace add .
codex plugin add problem-navigator@problem-navigator
```

随后**新建启用插件的 Codex 任务**。命令取决于已安装 Codex 的支持情况，必要时查看 `codex plugin --help`。官方[插件测试指南](https://developers.openai.com/plugins/deploy/connect-chatgpt)说明了本地市场安装与新会话测试流程。

使用唯一发行包 `problem-navigator-2.4.0.zip`，无需另下 Codex 包。发行包市场目录指向自身根目录（`source.path: "."`）；请使用包根市场目录及上述市场/插件名称。

首次依赖同步可能下载包。`.codex-plugin/plugin.json` 中内联的 `mcpServers` 对象通过 `uv` 启动共享本地 stdio 服务，不使用独立 `.mcp.json`。技能与 MCP 核心只包含一份，也支持具备所需能力的其他宿主直接加载。

保持发行包目录完整；本指南位于 `adapters/codex/`。通用用法见[主 README](../../README.zh-CN.md)。

## 在 Codex 中保持法庭隔离

多候选或已确认范围要求法庭时，必须使用受支持的 Agent Team/独立 Agent。被禁用或暂时故障时先启用或恢复；只有真实缺少能力才允许手动独立 Session，不允许单会话法庭降级。

角色从干净上下文启动，不继承父任务对话。每个倡导者、红队和可行性评估者先独立完成完整文稿，收齐封存后才能交换。进行一至两轮有限质询，再由新的法官上下文读取完整记录，与主会话和所有参与者分离。并发不足时可排队执行独立角色。

角色将完整提交保存到指定文件，只返回安全状态、ID 和引用/哈希。主会话负责协调并读取最终通过校验的中性结论，不接收论证、不担任法官；自动返回结果也必须遵守该边界。发现泄漏后，该次法庭失效，需要干净上下文重新开始。

手动模式由用户打开真实不同的 Session，直接转交角色包与提交。角色不能写文件时，可在该外部 Session 直接向用户返回完整提交供保存，绝不转发给主会话。优先使用宿主上下文 ID，没有 ID 时可给每个真实 Session 登记唯一标签。详见[宿主说明](../../HOST_INSTRUCTIONS.md)、[法庭协议](../../skills/adversarial-option-selection/references/court-protocol.md)和[可复制角色说明](../../skills/adversarial-option-selection/references/role-packets.md)。运行时检查引用、哈希与声明，不证明实际独立性或事实真实。

## 无需密钥即可开始

> 使用 $problem-navigator，用中文回答。只根据我的记录，分析一次原定 30 分钟的会议为什么用了 45 分钟，会议中途新增了两个议题。不要联网。输出研究报告，区分事实、推断与未知。

离线研究选择 `NONE`，跳过服务商配置检查，不执行研究网络调用。首次运行环境下载与 Codex 宿主/模型连接另行适用。提供的陈述会记录来源，但不自动视为已独立核实。

需要 PRD 时，可说明“仅交付 PRD”，并描述用户、行为、约束与验收需要。纯技术问题可说明“仅交付技术方案规格，不创建 PRD”。插件会澄清关键缺口，并提供文档预览供你接受。

## 语言与成果

中文和英文同等支持。正文先遵循当前明确语言选择，再遵循适用的先前偏好，否则跟随当前请求语言。只限定最终报告的偏好不会改变访谈语言。机器字段、枚举值、ID、文件名和原始引用保持不变。

| 目标/内容类型 | 端点与结果 |
|---|---|
| `UNDERSTAND`，任一内容类型 | `RESEARCH_REPORT` |
| `DECIDE` + `GENERAL` | `FORMAL_DOCUMENT`：正式方案报告 |
| `DECIDE` + `PRODUCT_SOFTWARE` | `FORMAL_DOCUMENT`：PRD 与技术方案规格 |
| 仅产品需求 | `PRD_ONLY`：`01-prd.md` |
| 仅技术设计 | `TECHNICAL_SPEC_ONLY`：`01-technical-solution-spec.md` |
| 明确约定的规格包 | `FINAL_SPEC_PACKAGE`：可选设计深度规格包 |

单一工作流将状态存入分析工作区的 `.problem-navigator/workflows/`。请与引用产物一起保存，不要让多个进程同时写入同一工作流。最终文档在明确接受前保持预览状态。

## 可选公开网页研究

在用户主目录的 UTF-8 文件 `.problem-navigator/web-research.json` 中提供自己的密钥。文件应放在插件与任何源仓库之外：

```json
{
  "schema_version": 1,
  "brave": { "api_key": "<YOUR_BRAVE_API_KEY>" },
  "exa": { "api_key": "<YOUR_EXA_API_KEY>" },
  "firecrawl": { "api_key": "<YOUR_FIRECRAWL_API_KEY>" }
}
```

在本地替换占位文本，省略不使用的服务商。文件不接受额外字段、注释或自定义服务地址。也可在宿主环境中设置 `BRAVE_API_KEY`、`EXA_API_KEY`、`FIRECRAWL_API_KEY` 中的一个或多个。存在的环境变量覆盖对应文件值；空值或无效值让该服务商未配置。修改环境后需重启宿主。

| 操作 | `primary` | `alternate` |
|---|---|---|
| `auto` / `news` 搜索 | Brave | Exa |
| `semantic` 搜索 | Exa | 不支持 |
| `academic` 搜索 | Firecrawl | Exa |
| `developer` 搜索 | Firecrawl | Brave |
| Fetch | Firecrawl | Exa |
| Map | Firecrawl | 不支持 |

核心每次调用选择一条路由，失败时不会静默切换服务商。`web_research_status` 在本地返回配置状态，不返回密钥；它不能证明线上认证或额度。`NONE` 不调用该工具。

你自行提供 Codex/模型访问并承担适用的服务商费用。本地服务向所选服务商发送经授权的查询、公开 URL、域名过滤与相关选项，避免其中包含秘密和私人细节。工作流预算计数操作，不限制金额。宿主内置工具需要获得覆盖研究范围的明确授权。

## 排查与验证

插件主动提问统一使用普通文字，不使用 Codex 选项卡。关键确认没有超时默认值；稍后回复
时从工作区 pending.md 和草稿继续。研究开始前先确认整理后的需求摘要，交付后再验收
实际报告版本。Codex 自身管理的系统权限窗口不受插件控制。

首次联网缺少适用配置时，可选择按上文在本地配置需要的服务商、授权内置网页工具或
离线处理。不要在聊天中粘贴 API Key。若项目已经记录可用解释器，所有角色复用它；
任务包中的 control_entry.argv_prefix 可直接执行，不要求每个角色重新解析 uv。

- 缺少插件：启用后新建任务，确认 Codex 支持本地市场流程。
- 找不到 `uv`/Python：检查桌面宿主看到的环境，准备 Python 3.11+ 与锁定依赖。
- `NOT_CONFIGURED`：配置所选服务商，或主动选择兼容且已配置的路由。
- 配置无效：检查 UTF-8 JSON 与精确支持字段。`CONFIGURED` 不证明密钥可用。
- 认证/额度/网络错误：检查所选服务商账户或连接，仅分享安全错误码与请求 ID。
- 工作流产物缺失/过期：保留文件，明确请求从有效保留输入重新生成，不虚构历史或重置计数。

自动检查覆盖结构、模拟服务商、工作流控制、打包与 stdio 注册，不能证明线上服务或已安装 Codex 的完整端到端体验通过。ZIP 包含运行所需资源，应记录在当前宿主实际观察到的行为。

采用 MIT 许可证；解压后的压缩包包含 `LICENSE` 与 `NOTICE.md`。问题反馈中不要携带凭据。若仓库平台启用了私密漏洞报告，请使用该渠道；否则先请求私密渠道，不要公开漏洞细节或秘密。
