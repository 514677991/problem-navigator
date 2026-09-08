简体中文 · [English](README.md)

# Problem Navigator｜问题导航

这是一个通用 AI 插件，用于将尚不清晰的问题整理成有证据支撑的研究报告、决策结论或设计规格。共享技能与 Python/MCP 核心面向通用问题和产品/软件问题，平等支持中文与英文。Codex 是其中一个宿主适配。

从已有信息开始，选择是否需要公开网页研究，审阅证据，然后得到清楚标注假设与未解决问题的文档。工作流止于分析和设计；实现代码与部署不在其范围内。

**当前快照：** 插件 `2.1.0`；内置研究 MCP `0.2.0`。**许可证：** [MIT](LICENSE)，另见[署名与依赖说明](NOTICE.md)。

## 快速开始

准备能够完整读取技能文件、写入本地产物并执行 Python 命令的 AI 宿主，以及 **Python 3.11+** 与宿主 `PATH` 中的 `uv`。克隆本仓库或解压 `problem-navigator-2.1.0.zip`，保持 `skills/` 与 `mcp/` 同根，在该根目录运行：

```sh
uv sync --locked --project mcp/web-research-mcp
```

首次 `uv sync` 可能下载 Python 依赖。让宿主完整加载入口 `skills/problem-navigator/SKILL.md`，遵循其引用，并在路由时加载相邻阶段技能。宿主没有技能机制时，也可明确要求它读取这些文件。核心不要求 `$` 或 `/` 命令前缀。详见[通用入门指南](docs/zh-CN/quickstart.md)或 [Codex 适配指南](adapters/codex/README.zh-CN.md)。

无需配置服务商密钥，即可尝试：

> 读取并遵循 `skills/problem-navigator/SKILL.md` 及其必需引用，用中文回答。只根据以下记录，分析每周例会为什么超时：计划时长 30 分钟；最近三次实际用了 45、50、55 分钟；每次会议中途都有新增议题。不要联网。输出研究报告，区分事实、推断与未知。

`NONE` 研究模式仅使用提供的材料和推理，不发起研究网络调用，也不检查服务商配置。宿主/模型本身的连接需求与首次依赖下载，和这里的离线研究模式是两回事。

需要公开网页证据时，在宿主中注册本地 stdio MCP 服务，并按照[配置指南](docs/zh-CN/configuration.md)提供自己的 Brave、Exa 或 Firecrawl API 密钥。仓库不提供密钥，也不要求同时配置三家服务。

唯一 ZIP 包含一份共享核心、通用宿主说明与可选 Codex 元数据。它是可移植文件包，不是所有宿主通用的一键导入格式。仅接入 MCP 会得到四个研究工具；完整工作流还需要技能加载与本地文件/命令执行能力。纯聊天宿主无法执行完整工作流；仅支持远程 HTTP MCP 的宿主无法直接连接当前 stdio 入口。包括 Claude Code 在内的其他宿主仅提供集成指引，不声称已完成宿主端到端验证。

## 可以得到哪些成果

工作流有两个独立维度：目标（`UNDERSTAND` 或 `DECIDE`）与内容类型（`GENERAL` 或 `PRODUCT_SOFTWARE`）。用自然语言说明希望得到什么即可，不需要手动修改这些字段。

| 希望得到的结果 | 交付端点 | 范围 |
|---|---|---|
| 理解问题 | `RESEARCH_REPORT` | 证据、综合分析、局限与待解问题 |
| 确定通用问题的解决方案 | `FORMAL_DOCUMENT` | 正式方案报告 |
| 设计完整的产品/软件方案 | `FORMAL_DOCUMENT` | PRD 与技术方案规格，保留需求追溯关系 |
| 仅定义产品需求 | `PRD_ONLY` | `01-prd.md`；产品范围与验收标准 |
| 解决纯技术设计问题 | `TECHNICAL_SPEC_ONLY` | `01-technical-solution-spec.md`；不虚构 PRD |
| 将已接受的设计整理为规格包 | `FINAL_SPEC_PACKAGE` | 可选，需明确约定范围的设计成果 |

一个工作流记录问题界定、研究设计、证据、决策准备、方案选择、细化、文档化和可选的规格拆分。只执行当前端点需要的阶段。最终文档在你接受之前保持预览状态。

中文与英文同等支持。访谈、解释和文档先遵循当前明确语言选择，再遵循适用的先前偏好，否则跟随当前请求的语言。只限定最终报告的偏好不会改变访谈语言。机器字段、枚举值、ID、文件名与原始来源引用保持不变。见[三组对应示例](docs/zh-CN/examples.md)。

## 费用与数据

本仓库按 MIT 提供代码与技能，不提供宿主/模型订阅或服务商额度。宿主/模型使用，以及 Brave、Exa、Firecrawl 的费用均取决于你自己的账户。工作流调用预算限制操作次数，并非金额上限。

MCP 服务通过 stdio 在本地运行。经授权的网页操作会将查询、URL、域名过滤条件及相关请求选项发送给所选服务商。核心每次调用选择一条路由，不会静默切换服务商。使用宿主内置研究工具需要覆盖相应范围的明确授权。不要把密钥或机密细节放进提示词、公开证据或问题反馈中。详见[配置指南](docs/zh-CN/configuration.md)与[安全说明](SECURITY.zh-CN.md)。

## 文档与开发

- [入门指南](docs/zh-CN/quickstart.md)、[服务商配置](docs/zh-CN/configuration.md)与[使用示例](docs/zh-CN/examples.md)
- [常见问题](docs/zh-CN/troubleshooting.md)与 [MCP 工具说明](mcp/web-research-mcp/README.md)
- [开发与维护](docs/zh-CN/development.md)、[贡献指南](CONTRIBUTING.zh-CN.md)与[变更记录](CHANGELOG.md)
- [验证范围](mcp/web-research-mcp/VERIFICATION.md)与[快照验证报告](docs/VERIFICATION.md)

规范源文件位于 `skills/` 与 `mcp/web-research-mcp/`；`release.json` 管理发行元数据。`adapters/generic/` 提供发行包根部用户说明，`adapters/codex/` 管理可选 Codex 元数据与指南。`plugins/problem-navigator/` 是生成的统一发行镜像。源仓库市场指向该镜像；发行包市场指向解压根目录。

只构建一个 `problem-navigator-2.1.0.zip`，见[开发指南](docs/zh-CN/development.md)。Codex MCP 注册内联在 `.codex-plugin/plugin.json` 中，使用该适配无需额外下载；本快照未包含其他原生宿主适配。

自动检查覆盖结构约束、工作流控制、模拟服务商行为、打包和 stdio 启动，但不能证明线上服务可用、研究质量达标或 AI 宿主中的完整端到端体验通过。实际运行记录与平台覆盖请查看验证报告。
