# Changelog / 变更记录

This log describes repository snapshots; an entry is not proof of a published release or a live-service test. / 本记录描述仓库快照，不代表已公开发布或完成线上服务测试。

## 2.1.0 — Open-source snapshot / 开源快照

- General-purpose skills and Python/MCP core, with host-neutral release metadata in `release.json`. Codex is an optional adapter. / 通用技能与 Python/MCP 核心，由 `release.json` 管理与宿主无关的发行元数据；Codex 为可选适配。
- One archive, `problem-navigator-2.1.0.zip`, contains a single shared skills/MCP core, general host instructions, and optional Codex metadata. / 唯一压缩包包含一份共享技能/MCP 核心、通用宿主说明与可选 Codex 元数据。
- Canonical adapter files live under `adapters/`; `plugins/problem-navigator/` is the generated unified mirror. Codex MCP registration is inline in `.codex-plugin/plugin.json`, and the released marketplace points to the bundle root. / 适配规范文件位于 `adapters/`，插件目录为生成的统一镜像；Codex MCP 注册内联于插件清单，发行市场指向包根。
- One archive is checked through direct MCP launch and the declared Codex registration. Host integration still requires appropriate file/Python capabilities; no universal import or host end-to-end compatibility is implied. / 同一压缩包检查直接 MCP 启动与声明的 Codex 注册；宿主集成仍需对应文件/Python 能力，不代表通用导入或宿主端到端兼容。
- Paired Chinese and English user/developer documentation and language-aware interviews and deliverables. / 配套中英文用户与开发文档，访谈与交付物遵循用户语言偏好。
- One workflow with independent `UNDERSTAND`/`DECIDE` goals and `GENERAL`/`PRODUCT_SOFTWARE` profiles; research reports, formal documents, `PRD_ONLY`, `TECHNICAL_SPEC_ONLY`, and optional `FINAL_SPEC_PACKAGE`. / 单一工作流，目标与内容类型独立，支持研究报告、正式文档、仅 PRD、仅技术规格及可选最终规格包。
- Evidence correction/resume controls, a shared research-call budget, explicit document acceptance, and lineage validation. / 证据纠正与续接、共享研究调用预算、明确文档接受及来源版本验证。
- Bundled research MCP remains `0.2.0`: local stdio, Brave/Exa/Firecrawl routes, user-supplied keys, and key-free `NONE` research. / 内置研究 MCP 为 `0.2.0`：本地 stdio、Brave/Exa/Firecrawl 路由、用户自备密钥与无需密钥的 `NONE` 研究。

See [verification scope / 验证范围](mcp/web-research-mcp/VERIFICATION.md) and [actual snapshot checks / 快照实际检查](docs/VERIFICATION.md).
