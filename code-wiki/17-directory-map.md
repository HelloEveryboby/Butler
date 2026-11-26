# 17 · 目录结构索引

> 以仓库根为起点，标注目录/文件角色。用于快速定位代码。

## 17.1 顶层

```text
Butler/
├── butler/                     # 核心系统（编排器 + core + agent + workflow + memory + cli + tui + gui + hal）
├── package/                    # 通用能力层（算法/工具/设备/文档/文件/媒体/网络/安全/存储/视觉）
├── programs/                   # BHL 混合语言模块（C/C++/Go/Rust/TS/Python）
├── skills/                     # One Folder = One Skill 技能（含 core_plugins / third_party）
├── frontend/                   # 2×2 Web UI（HTML/TS）、PWA、翻译扩展、下载器
├── docs/                       # 深度文档、规范、错误码、gRPC proto
├── tests/                      # 单元 + 集成 + 翻译测试
├── verification/               # 前端/能力验证
├── config/                     # config.yaml / settings.yaml / system_config.json
├── data/                       # 运行期数据（记忆/密钥/团队/习惯/日志）
├── assets/                     # Logo、UI 截图
├── bin/                        # 一键启动/安装脚本
├── scripts/                    # 安装、打包、生成、验证脚本
├── release/                    # 发布产物
├── .github/workflows/ci.yml    # CI
├── butler.py                   # 兼容启动封装
├── butler_cli.py               # 功能型 CLI（crawl/email/encrypt/skill/plugin…）
├── butler_launcher.py          # 便携启动器
├── build.py / build.bat        # PyInstaller 打包
├── pyproject.toml / requirements.txt
├── Dockerfile / docker-compose.yml / .dockerignore
├── README.md / README_EN.md / AGENTS.md / LICENSE
└── skills-lock.json            # 技能启用与外部来源哈希
```

## 17.2 `butler/` 核心

```text
butler/
├── __main__.py                 # 统一入口：模式调度
├── butler_app.py               # 桌面主编排器 Butler
├── butler_app_enhanced.py      # 增强启动器（向导→GUI/Web）
├── CommandPanel.py             # 旧版 Textual 面板
├── interpreter.py              # Python/Shell 解释器（带技能拦截）
├── resource_manager.py         # 性能模式（NORMAL/ECO/HIGH）
├── usb_screen.py               # USB 字符屏
├── data_storage.py             # 通用键值/文件存储
├── redis_client.py             # Redis 封装（向量记忆用）
├── code_execution_manager.py   # 外部程序/代码执行注册
├── computer.py                 # 桌面自动化（截屏/点击/输入）
├── edit.py / bash.py / base.py / collection.py   # 工具基础
├── binary_extensions.py        # 二进制扩展探测
├── program_mapping.json        # 程序名→路径映射
├── prompts.json                # 系统提示词
│
├── core/                       # ★ 核心子系统（见 17.3）
├── agent/                      # 数字员工：agent.py（驱动 AgentRuntime）、planner/executor/verifier/context
├── workflow/                   # v2 工作流：engine/parser/state
├── memory/                     # v2 记忆：manager/short_term/long_term
├── security/                   # audit.py（安全审计日志）
├── package_runtime/            # 安装式包：loader/manifest/registry
├── cli/                        # CLI 实现：main/agent_cmd/config_cmd/doctor_cmd/hybrid_cmd/init_cmd/package_cmd/plugin_cmd
├── gui/                        # Tkinter 配置向导：config_wizard*.py、startup_wizard.py
├── tui/                        # Textual TUI：main、command_catalog、os_command_adapter、linux_parser
├── hal/                        # 硬件驱动抽象：base.py、drivers/pc
└── data/                       # installed_packages（运行期）
```

## 17.3 `butler/core/`（重点）

```text
butler/core/
├── 编排/Agent
│   ├── container.py            # AppContainer 依赖注入
│   ├── bootstrap.py            # 服务装配 + 安全 token
│   ├── runtime.py              # ButlerRuntime（v2 服务）
│   ├── intent_dispatcher.py    # 意图注册表 + 弹性层
│   ├── intents/                # 各领域 LLM 意图 handler（@register_intent）
│   ├── legacy_commands.py      # 历史意图（排序/斐波那契/云盘…）
│   ├── verb_engine.py          # 动词归一
│   ├── agent_runtime/          # AgentRuntime 全套（见 05）
│   ├── workflow_engine.py      # DAG 工作流（Desktop）
│   ├── action_bridge.py        # Webhook/REST 动作桥（SSRF 防护）
│   └── agent_node.py           # gRPC 数字员工服务
│
├── 能力
│   ├── skill_manager.py        # 技能核心（发现/加载/执行/LDST/DRAS）
│   ├── skill_registry.py       # 技能发现根与元数据
│   ├── skill_interceptor.py    # Shell 命令拦截重定向
│   ├── skill_sdk.py            # 移动端/嵌入式 SDK
│   ├── tool_bridge.py          # 技能访问内置工具
│   ├── nlu_service.py          # 云端 NLU / LLM
│   ├── local_nlu.py            # 本地 NLU
│   ├── llm_providers.py        # 多提供商 OpenAI 兼容解析
│   ├── memory/                 # memory_engine.py（三级降级）、input_memory、PluginManager
│   ├── voice_service.py        # 多引擎语音
│   ├── algorithms.py           # 排序/图/相似度/LDST/DRAS
│   ├── dream_engine.py + dream/ # 做梦引擎
│   ├── self_healing.py         # 自愈
│   ├── proactive_agent.py      # 主动代理
│   ├── focus_mode.py           # 专注模式
│   ├── habit_manager.py        # 用户习惯画像
│   ├── topic_manager.py        # 话题管理
│   ├── sensing_api.py          # 传感 API
│   └── notifier_system.py      # 通知器
│
├── 通信/基础设施
│   ├── event_bus.py            # 事件总线
│   ├── message_bus.py          # 文件持久化消息总线
│   ├── blackboard.py           # 带 TTL 的黑板
│   ├── task_manager.py         # 线程池 + 业务任务
│   ├── team_manager.py         # 团队协作
│   ├── cron_scheduler.py       # 持久化 Cron（电池感知）
│   ├── scheduler.py            # 轻量后台调度
│   ├── runner_server.py        # Go Runner WebSocket（HMAC）
│   ├── api.py                  # FastAPI REST 网关
│   ├── display_protocol.py     # TCP 显示协议
│   ├── secret_vault.py         # 零信任密钥库
│   ├── db_migrations.py        # SQLite 迁移
│   ├── config_manager.py / config_model.py / constants.py
│   ├── lifecycle.py            # 生命周期状态机
│   ├── errors.py               # BTL-xxxx 错误码
│   ├── environment.py / doctor.py / capability_reporter.py / api_validator.py
│   ├── extension_manager.py    # 插件/包/程序统一管理
│   ├── plugin_bundle.py        # dsh/Claude 插件包兼容
│   ├── time_machine.py         # 时光机
│   ├── cluster_manager.py      # 集群发现
│   ├── session_modes.py / project_manager.py / window_registry.py
│   ├── git_tools.py            # 内置 Git
│   ├── code_sandbox.py / windows_sandbox.py / sec_utils/
│   ├── hybrid_hub.py / hybrid_link.py / hybrid_router.py / hybrid_fallbacks.py / hybrid_scaffold.py
│   ├── naming_policy.py / alias_store.py / ipc_tlv.py
│   └── gui/ (bridge/theme)、hal/ (base/sensors)
```

## 17.4 `package/`（能力层）

| 子目录 | 代表文件 | 角色 |
| :--- | :--- | :--- |
| `algorithm/` | `algorithm1.py` | DP 路径优化；数学工具 |
| `core_utils/` | `log_manager`、`config_loader`、`dependency_manager`、`quota_manager`、`autonomous_switch`、`health_monitor`、`knowledge_base_manager` | 日志/配置/依赖/配额/健康/知识库 |
| `device/` | `stm32_hw_bridge`、`hardware_manager`、`ble_connector`、`ir_manager`、`adbsploit`、`terminal`、`high_perf_terminal`、`os_utils`、`virtual_keyboard`、`standalone_manager` | 硬件与设备控制 |
| `document/` | `document_interpreter`、`excel_master_processor`、`xlsx_recalc_tool`、`office_automator`、`file_converter`、`markdown_converter`、`marker_tool`、`translate_system/` | 文档处理/翻译 |
| `file_system/` | `file_manager`、`OrganizeIT`、`archiver`、`data_recycler`、`guard`、`migration_engine` | 文件管理 |
| `media/` | `music.py`、`music_library.json` | 媒体库/播放 |
| `network/` | `crawler`、`e-mail`、`cloud_storage_manager`、`weather`、`image_search_tool`、`go_net_tool` | 网络能力 |
| `security/` | `encrypt`、`crypto_core`、`AccountPassword`、`asymmetric_tool`、`high_perf_crypto`、`quarantine` | 加密/密码/隔离 |
| `storage_hub/` | `storage_hub.py`、`drivers/`、`migrations/` | 云存储聚合 + DB 迁移 |
| `vision/` | `PictureRecognition`、`QR-Code-Recognition`、`Word_reading` | 视觉/OCR |

## 17.5 `programs/`（BHL）

| 目录 | 语言 | 说明 |
| :--- | :--- | :--- |
| `hybrid_sysutil` | C | 系统信息/进程/grep/glob/patch/显示/连接 |
| `hybrid_compute` | C++ | 质因数分解、Fibonacci |
| `hybrid_math` | C++ | 统计、矩阵测试 |
| `hybrid_doc_processor` | C++ | 文档分析 |
| `hybrid_vision` | C++ | 视觉处理 |
| `hybrid_memory` | Go | 记忆搜索/统计 |
| `hybrid_net` | Go | 网络检查/端口扫描/基准/并发下载/批量 ping |
| `hybrid_system_executor` | Go | 审计/日志扫描/远程派发/节点发现 |
| `hybrid_memos` | Go | 备忘 CRUD |
| `hybrid_crypto` | Rust | SHA256/文件哈希/加解密 |
| `hybrid_terminal` | Go | 终端服务 |
| `hybrid_ts_tool` | TS | TS 工具 |
| `hybrid_archive` | C++ (cli) | 流式替换 |
| `c_word_counter` | C (cli) | 词数统计 |
| `butler_runner` | Go | 远程执行节点 |
| `bcli` / `ble_framework` | C/C++ | STM32 串口 / BLE |
| `7zip` / `markitdown_gui` | 其他 | 归档/转换 GUI |

## 17.6 `skills/`（技能）

- 原生技能约 49 个：`calculator`、`text_analyzer`、`translator`、`office-suite-expert`、`wps-office-expert`、`pdf`、`docx`、`xlsx_recalc`、`markitdown`、`storage_hub`、`media_manager`、`music_player`、`video_player`、`screen_capture`、`sys_cleaner`、`archive_manager`、`download_manager`、`expense_tracker`、`habit_tracker`、`task_management`、`password_generator`、`skill_creator`、`butler_expert`、`karpathy_guidelines`、`hello_cli`、`xiaomi` 等。
- 核心插件：`core_plugins/{clipboard_history, quick_launcher, system_monitor}`。
- 第三方：`third_party/`。
- 技能目录索引：`skills/CATALOG.md`。

## 17.7 `frontend/`

| 路径 | 作用 |
| :--- | :--- |
| `index.html` | 主界面（单页，约 60KB） |
| `flash_input.html` | Alt+Space 浮窗 |
| `workflow.html` | DAG 工作流页 |
| `breath_hud.html` | 呼吸灯 HUD |
| `program/modern_app.py` | pywebview 宿主 + `ModernBridge` |
| `src/main.ts` | 前端入口 |
| `src/core/` | bridge、event_bus |
| `src/components/` | dag_engine、screen_capture、time_machine_ui、memos、browser、telemetry、heatmap、modal… |
| `src/voice/` | engine、wake-word |
| `src/ws/bhl-client.ts` | WebSocket 客户端 |
| `src/ui/glassmorphism.ts` | 玻璃拟态 |
| `pwa/` | PWA（manifest/sw/server） |
| `translate/` | 浏览器翻译扩展 |
| `download/` | 下载管理 |

## 17.8 `docs/` 与测试

| 路径 | 内容 |
| :--- | :--- |
| `docs/index.md` | 文档中心索引 |
| `docs/Butler_Code_Wiki.md` | 精简版技术内参（本 Code Wiki 为其扩展） |
| `docs/bhl.md` / `docs/agent-runtime.md` | BHL / Agent 运行时说明 |
| `docs/SKILLS_GUIDE.md`、`docs/dev/SKILL_FRONTMATTER.md` | 技能规范 |
| `docs/dev/ERROR_CODES.md` | `BTL-xxxx` 错误码 |
| `docs/start/*` | 安装、环境变量 |
| `docs/DREAM.md`、`docs/SECURITY_AUDIT_REPORT.md`、`docs/PRD_NOTIFIER_SYSTEM.md` | 专题 |
| `docs/butler_agent.proto` + `pb2*.py` | gRPC 定义 |
| `tests/unit/`、`tests/integration/`、`tests/translate_system/` | 测试 |
| `verification/` | 验证脚本与截图 |
