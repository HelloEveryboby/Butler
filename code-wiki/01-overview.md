# 01 · 项目概览

## 1.1 一句话定位

Butler 是一个 **Local-First（本地优先）的智能管家 / AI 数字员工操作系统**：Python 作为“大脑与编排器”，通过 BHL 混合链路调用 C/C++/Go/Rust 高性能能力，在完全离线的环境下也能完成文件管理、文档处理、语音交互、多级降级语义记忆与 AI 驱动的后台自动化。

## 1.2 核心特性

| 特性 | 说明 | 关键实现 |
| :--- | :--- | :--- |
| **One Folder = One Skill** | 功能目录包含 `SKILL.md` + 代码即可在运行时自动发现、热加载并被 LLM 感知 | `butler/core/skill_manager.py`、`butler/core/skill_registry.py` |
| **BHL 混合链路** | C/C++/Go/Rust 模块经统一 JSON-RPC 行协议接入，按 manifest 构建、路由、懒启动、超时重启 | `butler/core/hybrid_hub.py`、`butler/core/hybrid_link.py`、`programs/*` |
| **多级降级记忆库** | Redis 向量库 → 本地 Zvec 嵌入式向量库 → SQLite（FTS5）逐级降级，保证离线可用 | `butler/core/memory/memory_engine.py` |
| **LLM 原生工具调用** | 聊天与 `butler agent run` 均由 `AgentRuntime` 驱动，可连续调用内置工具与技能 | `butler/core/agent_runtime/*` |
| **KAIROS 后台自动化** | 做梦引擎（记忆整合）、自愈系统、主动代理、专注模式、时光机 | `butler/core/dream_engine.py`、`self_healing.py`、`proactive_agent.py` 等 |
| **多形态 UI** | Textual TUI / Tkinter 经典 GUI / pywebview 2×2 玻璃拟态 Web UI / REST API / headless | `butler/tui/main.py`、`butler/gui/`、`frontend/` |
| **多引擎语音** | 原生 SAPI / 本地 Whisper / 百度 / Google / Azure 自动降级 | `butler/core/voice_service.py` |
| **零信任密钥库** | PBKDF2 + AES-256-GCM 本地加密，支持 Keyring | `butler/core/secret_vault.py` |
| **便携 / Docker 部署** | `lib_external` 隔离依赖、一键安装脚本、多阶段 Dockerfile | `package/core_utils/dependency_manager.py`、`scripts/install.sh` |

> 注：README 将「做梦引擎 / 自愈系统 / 硬件 HAL」标注为实验性或路线图；文档中对应模块已存在可运行实现，但需谨慎评估生产可用性。

## 1.3 技术栈与语言构成

| 维度 | 采用 |
| :--- | :--- |
| 主语言 | Python（`requires-python >= 3.10`，CI 使用 3.11，Docker 使用 3.12-slim） |
| 混合语言 | C、C++、Go、Rust、TypeScript（`programs/` 下各模块） |
| Web / API | FastAPI + Uvicorn（REST）、WebSocket（Runner / 前端 BHL 客户端）、Flask（部分遗留端点） |
| TUI | Textual 8.x + Rich |
| 桌面 GUI | Tkinter（经典）、pywebview（现代 2×2 矩阵） |
| 前端 | HTML/CSS/TypeScript（`frontend/src/**`）、PWA、xterm.js |
| 数据存储 | SQLite（`data/system_data/*.db`，含 FTS5）、JSON/YAML 配置、Redis/Zvec（可选） |
| LLM | OpenAI 兼容协议：DeepSeek / OpenAI / 智谱 / Anthropic / Gemini / 通义 / 文心 / Ollama |
| 配置校验 | Pydantic（`ButlerConfig`） |
| 质量工具 | ruff、mypy、pytest、pytest-cov |

## 1.4 代码规模（快照 `2105b5c`）

| 指标 | 数值 |
| :--- | :--- |
| 文件总数 | ≈ 1146（不含 `.git`） |
| Python 文件 | 599 |
| Markdown 文档 | 116 |
| TypeScript 文件 | 101 |
| Go 文件 | 33 |
| `butler/` Python 代码行数 | ≈ 42,179 行 |
| 单文件最大 | `butler/tui/main.py`（≈ 14 万字节）、`butler/butler_app.py`（≈ 6.4 万字节） |
| 技能目录 | 49 个（`skills/*`），含 3 个核心插件（`core_plugins/`） |
| BHL 模块 | `programs/` 下 19 个目录，其中 18 个声明 `manifest.json`（C/C++/Go/Rust/TypeScript/Python） |

## 1.5 仓库顶层结构（速览）

```text
Butler/
├── butler/              # 核心编排器、core/、agent/、workflow/、memory/、cli/、tui/、gui/、hal/
├── package/             # 通用能力层：安全/文档/网络/设备/视觉/算法/文件系统/存储
├── programs/            # BHL 混合语言模块（C/C++/Go/Rust…）
├── skills/              # One Folder = One Skill 技能目录（含 core_plugins）
├── frontend/            # 2×2 玻璃拟态 Web UI（HTML/TS）、PWA、翻译
├── docs/                # 深度文档、规范、错误码、Agent 协议
├── tests/ verification/ # 单元测试、集成测试、前端/能力验证
├── config/              # config.yaml、settings.yaml、system_config.json 等
├── data/                # 运行期数据（记忆库、密钥库、团队收件箱、习惯画像）
├── bin/ scripts/        # 一键启动 / 安装 / 打包脚本
├── butler.py butler_cli.py butler_launcher.py   # 兼容启动入口
├── pyproject.toml requirements.txt Dockerfile docker-compose.yml
└── README.md README_EN.md AGENTS.md LICENSE
```

## 1.6 与文档其他部分的关系

- 想知道 **怎么跑起来** → [16 运行、部署与测试](./16-deployment-testing.md)
- 想知道 **启动后初始化了什么** → [04 核心编排器](./04-core-orchestrator.md)
- 想知道 **LLM 如何执行任务** → [05 Agent 运行时](./05-agent-runtime.md)
- 想知道 **如何扩展功能** → [07 技能系统](./07-skills.md) 与 [18 开发指南](./18-dev-guide.md)
