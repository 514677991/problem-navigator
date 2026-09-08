[English home](../README.md) · [中文首页](../README.zh-CN.md)

# Verification record · 验证记录

Snapshot: Problem Navigator 2.1.0 / research MCP 0.2.0, verified on 2026-09-08.
Environment: Windows, Python 3.12.9, uv 0.12.9.

当前快照：Problem Navigator 2.1.0 / 研究 MCP 0.2.0，验证日期为 2026-09-08。
环境：Windows、Python 3.12.9、uv 0.12.9。

One release archive contains the shared core and optional Codex integration metadata.
This record describes local checks; it does not claim publication or installation into an AI host.

唯一发行包包含共享核心和可选 Codex 接入元数据。本记录描述本地检查，不表示已经公开发布或安装到 AI 宿主。

## Recorded results · 实测结果

| Check / 检查 | Observed result / 实际结果 |
|---|---|
| Final source suite / 最终源码全量回归 | **638 passed in 97.53s** |
| Extracted MCP: direct access / 解压后直接接入 MCP | Four expected tools, strict input schemas, callable local status, safe `NOT_CONFIGURED` search failure, exit code 0 / 四个预期工具、严格输入结构、本地状态可调用、搜索安全返回 `NOT_CONFIGURED`、退出码 0 |
| Extracted MCP: declared access / 解压后按清单接入 MCP | Same results using the inline manifest configuration, exit code 0 / 使用清单内联配置获得相同结果，退出码 0 |
| Single shared core / 单份共享核心 | **26 core files**, including nine skills, match canonical source byte for byte; no duplicate core or standalone MCP registration / 26 个核心文件含九个技能，与规范源码逐字节相同，无重复核心或独立 MCP 注册文件 |
| Structural checks / 结构检查 | Project and official Codex validators, all nine skill syntax checks, generated mirror checks passed / 项目及官方 Codex 校验、九个技能语法检查、生成镜像一致性检查通过 |
| Project identity / 项目标识 | Entry skill, release, marketplace and adapter use `problem-navigator`; workflow artifacts and user configuration use `.problem-navigator` / 入口技能、发行元数据、市场与适配器统一使用 `problem-navigator`，工作流产物与用户配置统一使用 `.problem-navigator` |
| Release regressions / 发行回归 | Single archive layout, package-root marketplace, deterministic builds, safe archive paths, isolated offline configuration, temporary-process cleanup and sync rollback covered / 覆盖单包布局、包根市场源、确定性构建、归档路径安全、隔离的离线配置、临时进程清理及同步回滚 |
| Documentation / 文档 | **171 source links**, **20 archive links**, **15 JSON examples**, including **10 configuration-model checks**, passed / 171 个源码链接、20 个包内链接、15 份 JSON 示例检查通过，其中 10 份经过实际配置模型校验 |
| Public inventory / 公开清单 | **159 public source files** and all 45 archive entries scanned for obsolete project names, reference remnants and private paths; no matches / 已扫描 159 个公开源码文件及包内全部 45 项，未发现旧项目名称、已清理的来源残留或私人路径 |

Both access modes used the same ZIP, separate temporary extraction directories and empty user
configuration. The verifier removed provider keys, forced uv offline, retained the selected
Python/dependency cache, and closed stdio before successful temporary-directory cleanup.
No research provider request or host installation was performed.

两种接入方式使用同一个 ZIP，各自在独立临时目录解压，使用空用户配置。验证器移除服务商
密钥、强制 uv 离线、保留指定 Python 和依赖缓存，并在成功清理临时目录前关闭 stdio。
没有向研究服务商发送请求，也没有安装宿主插件。

## Artifact · 产物

| Archive / 压缩包 | Files / 文件数 | Bytes / 字节数 | SHA-256 |
|---|---:|---:|---|
| `problem-navigator-2.1.0.zip` | 45 | 173,379 | `33d4925e12b85ad5d7511c4282b894d553e5d282d0615f943947aee2b102bb67` |

The adjacent `.zip.sha256` file is a checksum, not another installation package.
`release.json` identifies this project release. Optional Codex metadata lives in the same
archive; its embedded marketplace points to `.` and its manifest declares MCP inline.

相邻的 `.zip.sha256` 文件用于校验完整性，不是另一个安装包。`release.json` 标识项目版本。
可选 Codex 元数据包含在同一归档中；包内市场源指向 `.`，清单直接内联 MCP 配置。

## Reproduction · 复现方式

From the source repository root / 在源码仓库根目录执行：

```sh
uv sync --locked --project mcp/web-research-mcp --extra dev
uv run --locked --project mcp/web-research-mcp python scripts/sync_plugin_payload.py --check
uv run --locked --project mcp/web-research-mcp --extra dev python -m pytest -q
uv run --locked --project mcp/web-research-mcp python scripts/validate_plugin.py plugins/problem-navigator --marketplace .agents/plugins/marketplace.json
uv run --locked --project mcp/web-research-mcp python scripts/build_plugin_zip.py
uv run --locked --project mcp/web-research-mcp --extra dev python tests/verify_plugin_mcp_registration.py --archive dist/problem-navigator-2.1.0.zip --mode direct
uv run --locked --project mcp/web-research-mcp --extra dev python tests/verify_plugin_mcp_registration.py --archive dist/problem-navigator-2.1.0.zip --mode declared
```

Initial dependency sync may download packages. After extraction, the source repository's
`scripts/validate_plugin.py` can validate the extracted root directly. The runtime ZIP does
not include source-development scripts or tests. CI warms dependencies before offline
archive execution. Reproducible ZIP bytes require unchanged file contents and build tooling.

首次依赖同步可能下载软件包。解压后，可使用源码仓库的 `scripts/validate_plugin.py` 直接
校验解压根目录。运行包不包含源码开发脚本或测试。CI 先准备依赖，再离线运行归档。
ZIP 字节复现要求文件内容和构建工具保持一致。

## Interpretation · 结果边界

The full workflow needs complete skill loading, local file I/O, Python helper execution and
real user interaction. MCP-only integration supplies four research tools. The server is
stdio-only. Other capable hosts can integrate the same resource using their own discovery
and configuration mechanisms; this is not proof of universal one-click installation.

完整工作流需要完整技能加载、本地文件读写、Python 工具执行及真实用户交互。仅连接 MCP
可获得四个研究工具，当前服务只支持 stdio。其他具备相应能力的宿主可以按自己的发现及
配置方式接入同一资源；这不等于所有宿主均可一键安装。

The configured CI matrix covers Linux/Windows and Python 3.11/3.12. This local record does
not claim an executed GitHub Actions run, macOS validation, live-provider availability,
research quality, or an installed-host workflow end-to-end run.

CI 已配置 Linux/Windows 与 Python 3.11/3.12 矩阵。本地记录不表示已经运行 GitHub Actions、
验证 macOS、线上服务商可用性、研究质量，或真实安装宿主中的完整工作流端到端体验。
