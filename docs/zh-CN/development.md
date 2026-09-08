[English](../en/development.md) · [首页](../../README.zh-CN.md)

# 开发与维护

在本仓库开发共享技能与 Python/MCP 核心，构建一个包含可选 Codex 集成元数据的发行包。

## 从全新克隆开始

准备 Python 3.11+ 与 `PATH` 中的 `uv`，在仓库根目录运行：

```sh
uv sync --locked --project mcp/web-research-mcp --extra dev
uv run --locked --project mcp/web-research-mcp --extra dev pytest -q
```

首次同步需要下载依赖。运行环境和依赖缓存完成后，可以离线重复运行。这些测试不需要真实服务商密钥；配置夹具会隔离测试进程与用户的研究设置。

## 修改规范源文件

| 位置 | 作用 |
|---|---|
| `skills/` | 入口技能、阶段说明、产物结构与工作流控制工具 |
| `mcp/web-research-mcp/` | 独立研究核心、服务商适配器、stdio MCP 服务与锁文件 |
| `release.json` | 与宿主无关的发行元数据 |
| `adapters/generic/` | 发行包根部中英文 README 与宿主说明的规范源 |
| `adapters/codex/` | 内联 MCP 注册的 Codex 清单、UI 文件与中英文 README 的规范源 |
| `plugins/problem-navigator/` | 生成的统一发行镜像，不直接编辑 |
| `.agents/plugins/marketplace.json` | 源目录指向镜像，发行目录指向包根 |
| `tests/` | 工作流、协议、服务商与打包检查 |

在规范位置修改技能与 MCP 源码，在对应适配目录修改宿主专属文件。共享工作流路由不应依赖某个宿主的调用语法。随后重新生成统一镜像：

```sh
uv run --locked --project mcp/web-research-mcp python scripts/sync_plugin_payload.py --write
uv run --locked --project mcp/web-research-mcp python scripts/sync_plugin_payload.py --check
```

同步脚本保持生成发行包与规范源、许可证和说明文件一致。直接修改生成文件会被覆盖。若同步失败，请先修复原因，再重新运行 `--write` 与 `--check`。

## 验证与构建

```sh
uv run --locked --project mcp/web-research-mcp python scripts/validate_plugin.py plugins/problem-navigator
uv run --locked --project mcp/web-research-mcp python scripts/build_plugin_zip.py
uv run --locked --project mcp/web-research-mcp --extra dev python tests/verify_plugin_mcp_registration.py --archive dist/problem-navigator-2.1.0.zip --mode direct
uv run --locked --project mcp/web-research-mcp --extra dev python tests/verify_plugin_mcp_registration.py --archive dist/problem-navigator-2.1.0.zip --mode declared
```

启动验证器在每种模式下将同一压缩包解压到临时目录。`direct` 使用解压后项目的绝对路径构造 stdio 命令；`declared` 检查 `.codex-plugin/plugin.json` 内联的 `mcpServers` 注册。两者使用临时用户配置、无服务商密钥及规范项目初始化时缓存的离线依赖，检查四个工具名、严格输入结构、本地状态及安全的 `NOT_CONFIGURED` 失败。它们不启动 AI 宿主，也不在源镜像内创建运行文件。

构建输出 `dist/problem-navigator-2.1.0.zip` 及其 `.zip.sha256` 校验文件，名称与版本来自 `release.json`。压缩包包含一份共享技能/MCP、根部用户说明、可选 Codex 清单/UI 元数据、`adapters/codex/` 下的指南，以及 `source.path` 为 `.` 的包内市场。测试、缓存、凭据和工作流产物被排除。

若要单独验证解压布局，请先将 ZIP 解压到临时目录，再以实际路径运行：

```sh
uv run --locked --project mcp/web-research-mcp python scripts/validate_plugin.py "<EXTRACTED_BUNDLE_ROOT>"
```

验证器检查生成镜像或解压后的发行包，开发仓库使用不同布局。分享前请检查压缩包内容与校验值。

## 发布审阅

1. 保持中英文用户文档一致，包括示例和限制说明。
2. 审阅结构/工作流兼容性，更新发行元数据与变更记录；依赖变化时有意识地更新 `uv.lock`，保持适配元数据与 `release.json` 一致。
3. 同步统一镜像，运行相关测试及其验证器，再构建 ZIP、检查/验证解压布局，最后运行 direct 与 declared 启动检查。
4. 在[验证报告](../VERIFICATION.md)记录实际平台、工具版本、命令、结果与未测试范围。
5. 声称某宿主端到端通过前，在该宿主的新会话中测试有代表性的中英文提示词，检查完整技能加载、本地工具执行、产物持久化与接受过程。真实服务商测试需要明确提供凭据并授权研究范围。

Windows 与 Linux CI 定义提供了待运行的可移植性检查，不代表两种平台都已通过。只有实际完成的运行才能支撑通过结论。模拟测试与 stdio 检查不能证明线上服务兼容性，也不能证明生成分析的质量。详见[验证范围](../../mcp/web-research-mcp/VERIFICATION.md)。
