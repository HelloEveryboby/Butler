# 03 · 入口与运行模式

## 3.1 统一入口 `butler/__main__.py`

安装后由 `pyproject.toml` 的 `[project.scripts]` 暴露为 `butler` 命令：

```toml
[project.scripts]
butler = "butler.__main__:main"
```

`main()` 按“第一个参数”决定行为，无参数时默认启动 TUI。

```mermaid
flowchart TD
    A["butler 命令参数"] --> B{argv[0]?}
    B -- 无 --> T["tui (默认)"]
    B -- tui --> T
    B -- gui --> G["Tkinter 经典 GUI"]
    B -- web --> W["pywebview 2×2 矩阵"]
    B -- headless --> H["无头后台 + API"]
    B -- api / start --> API["ButlerRuntime + FastAPI"]
    B -- cli --> CLI["功能型 CLI (crawl/email/encrypt...)"]
    B -- agent --> AG["数字员工 list / run"]
    B -- hybrid --> HY["BHL 构建/状态/调用"]
    B -- package --> PKG["包 list / install"]
    B -- config --> CFG["AI 服务商与密钥配置"]
    B -- init --> INIT["首次配置向导"]
    B -- doctor --> DOC["系统体检"]
    B -- download --> DL["资源下载器"]
    B -- 未知 --> ERR["打印帮助 + exit(2)"]
```

### 模式 → 实现函数 → 底层模块

| 命令 | 处理函数 | 底层调用 |
| :--- | :--- | :--- |
| `butler` / `butler tui` | `_launch_tui()` | `butler.tui.main.run_tui()`（Textual） |
| `butler gui` | `_launch_gui()` | `butler.butler_app_enhanced.main()`（强制 `--classic`） |
| `butler web` | `_launch_web()` | `frontend.program.modern_app.main()`（pywebview） |
| `butler headless` | `_launch_headless()` | `Butler(..., headless=True).main()` + 常驻循环 |
| `butler api` / `butler start` | `_launch_api()` | `butler.core.runtime.ButlerRuntime.start()` |
| `butler cli ...` | `_launch_old_cli()` | `butler_cli.main()` |
| `butler agent ...` | `_launch_agent()` | `butler.cli.agent_cmd` |
| `butler hybrid ...` | `_launch_hybrid()` | `butler.cli.hybrid_cmd.run_hybrid()` |
| `butler package ...` | `_launch_package()` | `butler.cli.package_cmd` |
| `butler config ...` | `_launch_config()` | `butler.cli.config_cmd.run_config()` |
| `butler init` | `_launch_init()` | `butler.cli.init_cmd.run_init()` |
| `butler doctor` | `_launch_doctor()` | `butler.cli.doctor_cmd.run_doctor()` |
| `butler download ...` | `_launch_download()` | `downloader.cli` |

### 向后兼容（已废弃）

`--tui`、`--legacy`、`--headless`、`--cli`、`legacy` 仍在解析，但会向 stderr 打印废弃提示并转调新命令。`butler start` 是 `butler api` 的友好别名。

### 宿主/端口参数

`_extract_host_port(args)` 解析 `--host` / `--port`，默认 `0.0.0.0:5001`（headless 默认 `0.0.0.0:5001`，REST 线程默认 `127.0.0.1:5001`）。

## 3.2 兼容启动文件

仓库根目录还有若干兼容入口，主要供打包与旧用户使用：

| 文件 | 作用 |
| :--- | :--- |
| `butler.py` | 顶层启动封装（导出 `main`） |
| `butler_cli.py` | 功能型 CLI：`crawl` / `email` / `encrypt` / `translate` / `manage_skills` 等子命令（`argparse`，约 23 个 parser） |
| `butler_launcher.py` | 便携启动器（定位 `lib_external` 与运行时） |
| `bin/run.sh` / `bin/run.bat` | 双击式启动（经典 UI） |
| `bin/run_modern.sh` / `bin/run_modern.bat` | 启动现代 Web UI |
| `bin/install.sh` / `bin/install.ps1` | 环境隔离安装 |

## 3.3 各模式的服务栈差异

| 组件 | TUI | GUI | Web(pywebview) | headless | api/start |
| :--- | :--: | :--: | :--: | :--: | :--: |
| `Butler` 主编排器 | ✅ | ✅ | ✅ | ✅ | ❌ |
| `ButlerRuntime` | ❌ | ❌ | ❌ | ❌ | ✅ |
| AgentRuntime | ✅ | ✅ | ✅ | ✅ | 使用旧 `Agent` |
| 语音 | ✅ | ✅ | ✅ | 视配置 | ❌ |
| KAIROS | ✅ | ✅ | ✅ | ✅ | ❌ |
| RunnerServer | ✅ | ✅ | ✅ | ✅ | ❌ |
| REST API | 后台线程 | 后台线程 | 后台线程 | ✅ | ✅（主服务） |
| 本地记忆引擎(三级降级) | ✅ | ✅ | ✅ | ✅ | SQLite(旧 MemoryManager) |

> 快速判断：**需要完整能力（技能/语音/KAIROS/2×2 UI）走桌面主程序；只需要远程 API 走 `butler start`。**

## 3.4 `butler.butler_app.main()` 的独立入口

`butler/butler_app.py` 自身也有 `main()`，支持 `--headless`、`--classic`、`--tui`、`doctor`，并被 Dockerfile 使用：

```dockerfile
CMD ["python", "-m", "butler.butler_app", "--headless"]
```

## 3.5 相关章节

- 各运行模式初始化细节：[04 核心编排器](./04-core-orchestrator.md)
- CLI 命令与配置：[14 配置与 CLI](./14-config-cli.md)
- 安装/部署：[16 运行、部署与测试](./16-deployment-testing.md)
