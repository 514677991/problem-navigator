[English](CONTRIBUTING.md) · [首页](README.zh-CN.md)

# 贡献指南

欢迎中文与英文贡献。请描述具体问题、预期行为与可复现的小例子。涉及安全敏感内容时，请使用[安全流程](SECURITY.zh-CN.md)。

## 开始修改

1. 阅读[开发指南](docs/zh-CN/development.md)，使用 Python 3.11+ 和锁定版本的 `uv` 依赖准备环境。
2. 在规范源位置 `skills/` 或 `mcp/web-research-mcp/` 进行聚焦修改，保留单一工作流、目标/内容类型的区别，以及不依赖宿主的路由。宿主专属元数据与文档放在 `adapters/`；Codex 是一个适配，不是共享核心的项目定位。
3. 为行为变化增加或更新有意义的回归覆盖。纯文案修改通常只需认真审阅并检查链接。
4. 同时更新对应中英文文档。翻译面向用户的正文，保留机器字段、枚举、ID、文件名和原始引用。无法审阅两种语言时，请说明哪一版需要语言复核。
5. 重新生成并检查统一发行镜像，验证其中的共享核心与可选适配元数据，在变更说明中记录实际结果。不要根据模拟测试或 stdio 检查声称线上服务或宿主端到端运行通过。

```sh
uv sync --locked --project mcp/web-research-mcp --extra dev
uv run --locked --project mcp/web-research-mcp python scripts/sync_plugin_payload.py --write
uv run --locked --project mcp/web-research-mcp python scripts/sync_plugin_payload.py --check
uv run --locked --project mcp/web-research-mcp --extra dev pytest -q
```

涉及打包或 MCP 的修改，还需按开发指南构建唯一压缩包，运行验证器与 direct/declared 两种启动检查。`release.json` 管理发行元数据；适配 README 在 `adapters/` 编辑，不修改生成的 `plugins/problem-navigator/` 镜像。真实密钥、本地工作流、私人来源材料、缓存和虚拟环境不得进入提交或发行包。

## 提交便于审阅的贡献

使用仓库托管平台提供的问题或拉取请求机制。说明改了什么、为何有用、如何检查，以及尚存限制。工作流/结构变化需要说明对已有产物和兼容性的影响；新增服务商或路由需要说明外发数据、配置、费用边界与失败行为。

共同维护规范源与生成发行包。变更记录和验证报告应反映实际发行内容与已完成的检查。

贡献内容必须是你有权按照仓库 [MIT 许可证](LICENSE)提交的材料。保留适用的版权与许可声明，必要时在 [NOTICE.md](NOTICE.md)记录第三方来源。审阅请具体、尊重他人并具有建设性；欢迎围绕证据与设计提出不同意见。
