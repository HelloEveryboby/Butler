# Butler Code Wiki

> 本套文档基于仓库 [`HelloEveryboby/Butler`](https://github.com/HelloEveryboby/Butler) 的快照生成：
> 版本 `2.0.0`，提交 `2105b5c`（2026-11-26）。共 18 篇，覆盖整体架构、模块职责、关键类与函数、依赖关系与运行方式。

Butler 是一个 **Local-First（本地优先）的智能管家 / AI 数字员工操作系统**。它以 Python 为核心编排器，通过 BHL（Butler Hybrid Link）把 C / C++ / Go / Rust 模块接到同一条 JSON-RPC 链路上，并叠加了多级降级记忆库、LLM 原生工具调用循环、One Folder = One Skill 热插拔技能、KAIROS 后台自动化（做梦 / 自愈 / 主动代理）以及多形态 UI（TUI / Tkinter / pywebview 2×2 矩阵）。

---

## 文档目录

| 编号 | 文档 | 内容概要 |
| :--- | :--- | :--- |
| — | [README.md](./README.md) | 本文：阅读路径与项目速览 |
| 01 | [项目概览](./01-overview.md) | 定位、核心特性、技术栈、代码规模 |
| 02 | [整体架构](./02-architecture.md) | 分层架构、运行时视图、依赖注入、启动时序 |
| 03 | [入口与运行模式](./03-entrypoints.md) | `butler` 统一入口、6 种界面/服务模式、CLI 子命令 |
| 04 | [核心编排器](./04-core-orchestrator.md) | `Butler` 类初始化链、命令处理、意图循环 |
| 05 | [Agent 运行时](./05-agent-runtime.md) | `AgentRuntime` 循环、工具、权限、上下文压缩、子代理、沙箱 |
| 06 | [意图与 NLU](./06-intent-nlu.md) | LLM 意图抽取、本地 NLU、意图注册表、弹性层、legacy 命令 |
| 07 | [技能系统](./07-skills.md) | One Folder = One Skill、发现/加载/执行、LDST/DRAS、热插拔、CLI |
| 08 | [BHL 混合链路](./08-bhl.md) | `HybridHub`/`HybridLink`、manifest、跨语言模块、Python 回退 |
| 09 | [记忆系统](./09-memory.md) | Redis→Zvec→SQLite 多级降级、两套记忆实现、习惯/做梦整合 |
| 10 | [KAIROS 自动化](./10-kairos.md) | 做梦引擎、自愈系统、主动代理、专注模式、时光机、Cron、集群 |
| 11 | [运行时服务与通信](./11-runtime-services.md) | 事件总线、消息总线、黑板、任务/团队、Runner、REST API、gRPC、HAL、密钥库、DB 迁移 |
| 12 | [package 能力层](./12-package-layer.md) | 安全/文档/网络/设备/视觉/算法/文件系统/存储等通用能力 |
| 13 | [UI 与前端](./13-ui-frontend.md) | TUI、Tkinter、pywebview 2×2 矩阵、PWA、翻译、浮窗 |
| 14 | [配置与 CLI](./14-config-cli.md) | `config.yaml`、`.env`、强类型配置模型、CLI 命令、doctor/init |
| 15 | [依赖关系](./15-dependencies.md) | 内部模块依赖图、第三方依赖分层、可选依赖 |
| 16 | [运行、部署与测试](./16-deployment-testing.md) | 安装、启动、Docker、PyInstaller、pytest、CI |
| 17 | [目录结构索引](./17-directory-map.md) | 全目录树与文件角色速查 |
| 18 | [开发指南](./18-dev-guide.md) | 新增技能/模块/意图/工具，代码规范与约定 |

---

## 推荐阅读路径

- **初次了解项目**：01 → 02 → 03 → 16
- **想改核心逻辑**：02 → 04 → 05 → 06 → 07
- **想接入高性能模块**：08 → 18
- **想做技能扩展**：07 → 18
- **运维 / 部署**：14 → 16
- **排障**：11 → 14（doctor）→ 06（错误码）

---

## 符号约定

| 记号 | 含义 |
| :--- | :--- |
| `butler/core/xxx.py` | 仓库相对路径（以仓库根为起点） |
| **类** / `函数()` | 关键类与关键函数 |
| ✅ / ⚠️ / 🧪 | 稳定可用 / 部分可用 / 实验性（README 原文标注） |
| 端口 `5001` / `8000` / `9000` | REST API / Runner WebSocket / 显示协议 |

> 说明：本文档中的“行号”与代码片段以提交 `2105b5c` 为准。代码演进后请以源码为准。
