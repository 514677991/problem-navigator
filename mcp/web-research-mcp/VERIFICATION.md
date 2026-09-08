# Verification scope / 验证范围

This page explains what checks mean. Actual commands, dates, platforms, and results belong in the [snapshot verification report](../../docs/VERIFICATION.md). / 本页说明检查能够证明什么；实际命令、日期、平台和结果见[快照验证报告](../../docs/VERIFICATION.md)。

| Check / 检查 | Establishes / 能说明 | Does not establish / 不能说明 |
|---|---|---|
| Schema and workflow tests / 结构与工作流测试 | Covered state transitions, bindings, budget and artifact constraints / 已覆盖的状态转换、绑定、预算和产物约束 | Factual truth or every model-followed instruction / 事实真实性或模型遵循每项指令 |
| Mock provider tests / 模拟服务商测试 | Adapter request/response behavior for supplied fixtures / 给定夹具下的适配器请求和响应行为 | Current live APIs, key validity, billing, or availability / 当前线上 API、密钥、计费或可用性 |
| Protocol tests / 协议测试 | Tool schemas, validation and exercised MCP behavior / 工具结构、验证和已执行的 MCP 行为 | Complete AI-host workflow behavior / AI 宿主完整工作流行为 |
| Direct stdio launch / 直接 stdio 启动 | Absolute-path launch from the archive exposes four tools and fails safely without keys / 从压缩包以绝对路径启动，暴露四个工具且无密钥时安全失败 | Skill loading or end-to-end integration in any host / 任一宿主的技能加载或端到端集成 |
| Declared registration / 声明的注册 | The same archive's inline Codex registration exposes the expected tools / 同一包内联的 Codex 注册暴露预期工具 | A fresh Codex task actually loading and completing the workflow / 新 Codex 任务实际加载并完成工作流 |
| Bundle and ZIP checks / 发行布局与 ZIP 检查 | Covered release/adapter metadata, single core, paths, synchronization and exclusions / 已覆盖的发行/适配元数据、单份核心、路径、同步与排除规则 | Absence of every possible secret or legal issue / 不存在任何秘密或法律问题 |
| CI configuration / CI 配置 | The declared platform matrix and commands / 声明了平台矩阵和命令 | A passing run until jobs actually complete / 作业实际完成前的平台通过结论 |

## Reproduce / 复现

From a clean clone's root with Python 3.11+ and `uv` on `PATH`: / 准备 Python 3.11+ 与 `uv` 后，在全新克隆的根目录运行：

```sh
uv sync --locked --project mcp/web-research-mcp --extra dev
uv run --locked --project mcp/web-research-mcp --extra dev pytest -q
uv run --locked --project mcp/web-research-mcp python scripts/sync_plugin_payload.py --check
uv run --locked --project mcp/web-research-mcp python scripts/validate_plugin.py plugins/problem-navigator
uv run --locked --project mcp/web-research-mcp python scripts/build_plugin_zip.py
uv run --locked --project mcp/web-research-mcp --extra dev python tests/verify_plugin_mcp_registration.py --archive dist/problem-navigator-2.1.0.zip --mode direct
uv run --locked --project mcp/web-research-mcp --extra dev python tests/verify_plugin_mcp_registration.py --archive dist/problem-navigator-2.1.0.zip --mode declared
```

First-time canonical sync downloads and caches dependencies. Each verification mode extracts the single ZIP to a temporary directory and launches a child with a temporary user home, no provider keys, and offline dependency resolution. `direct` constructs an absolute-path command; `declared` uses the inline `mcpServers` object in `.codex-plugin/plugin.json`. Both check `web_research_status`, `web_search`, `web_fetch`, and `web_map`, strict schemas, a status response, and `NOT_CONFIGURED` for an unconfigured search. They leave the generated source mirror untouched. / 首次规范项目 sync 下载并缓存依赖。每种验证模式将唯一 ZIP 解压到临时目录，使用临时用户目录、无服务商密钥及离线依赖解析启动子进程。`direct` 构造绝对路径命令，`declared` 使用插件清单内联的 `mcpServers` 对象。两者检查四个工具、严格结构、状态响应和无配置搜索的 `NOT_CONFIGURED`，不修改生成源镜像。

To validate an extracted release, run `python scripts/validate_plugin.py <EXTRACTED_BUNDLE_ROOT>` through the same locked Python environment, replacing the path. The source repository itself has a development layout; use its generated mirror or the extracted release as the validation root. / 验证解压发行包时，通过同一锁定 Python 环境运行上述命令并替换实际路径。源仓库自身采用开发布局，应以生成镜像或解压发行包作为验证根。

Do not infer Linux or macOS success from a Windows run, or live provider success from fixtures. A host end-to-end evaluation requires a fresh session in that host, complete skill loading, local helper execution, representative Chinese and English prompts, artifact review/resume, and separately recorded live calls when authorized. The generic format and official integration guides do not certify Claude Code or other host compatibility. / 不要从 Windows 运行推断 Linux 或 macOS 通过，也不要从夹具推断线上服务成功。宿主端到端评估需要在该宿主新建会话，完整加载技能、执行本地工具、运行代表性中英文提示词、审阅/续接产物，并在授权后单独记录真实调用。通用格式与官方集成指南不认证 Claude Code 或其他宿主兼容性。

The examples in the user guides are illustrative and do not represent completed host end-to-end runs. / 用户指南中的示例是说明性内容，不代表已完成的宿主端到端运行。
