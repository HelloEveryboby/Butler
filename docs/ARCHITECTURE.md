# Butler 系统架构设计 (System Architecture)

本文档详细描述了 Butler 智能助手的核心架构设计、模块化策略以及各组件之间的协作机制。

## 1. 核心设计哲学

Butler 采用**核心轻量化、功能插件化**的设计理念。系统的核心（Core）仅负责基础的生命周期管理、事件调度和跨语言通信，而所有的具体业务功能（如文件处理、网络爬虫、加密算法等）均以“插件（Plugin）”或“包（Package）”的形式动态加载。

## 2. 整体架构图

系统的逻辑架构可以分为四个层次：

1.  **接入层 (Access Layer)**: 提供用户交互界面，包括基于 Web 的现代化 UI (Modern UI)、基于 Tkinter 的经典管理界面 (Classic UI) 以及语音交互接口。
2.  **编排层 (Orchestration Layer)**: 以 `Jarvis` 类为核心，负责解析用户意图、分发任务、管理系统状态及资源调度。
3.  **协议层 (Protocol Layer)**: Butler Hybrid-Link (BHL) 协议，实现 Python 与高性能二进制模块（C++/Go/Rust）的透明通信。
4.  **执行层 (Execution Layer)**: 包含各类功能实现。
    *   **Internal Skills**: 深度集成的专业技能。
    *   **Plugins**: 具有复杂生命周期和钩子的高级扩展。
    *   **Packages**: 独立的 Python 工具函数。
    *   **BHL Modules**: 高性能的底层二进制程序。

---

## 3. Jarvis 编排引擎

`Jarvis` 类（位于 `butler/butler_app.py`）是整个系统的“大脑”。其主要职责包括：

-   **生命周期管理**: 启动/关闭各服务（NLU、语音、内存系统、BHL 客户端）。
-   **环境自检**: 启动时自动检查依赖并进行自修复。
-   **全局分发**: 将用户输入路由至最合适的处理单元。
-   **资源治理**: 配合 `AutonomousSwitch` 监控系统负载并实施熔断保护。

---

## 4. 阶梯式指令分发系统 (Tiered Dispatching)

Butler 处理用户指令时遵循“由简入深”的优先级策略：

1.  **斜杠命令 (Slash Commands)**: `/theme`, `/encrypt`, `/py` 等。绕过 NLU 模块，直接执行高优先级的系统级操作。
2.  **技能系统 (Skills)**: 匹配定义良好的任务模式（如 `/xlsx_recalc`）。
3.  **意图识别 (Intent Matching)**: 使用 DeepSeek API 将自然语言转换为结构化的意图 (Intent) 和实体 (Entities)。
4.  **扩展分发 (Extension Manager)**: 在 `plugin/` 和 `package/` 中搜索可处理该意图的模块。
5.  **自主开发 (LLM Interpreter)**: 如果所有预定义功能均无法处理，系统会触发“自主代码开发模式”，由 LLM 编写 Python 脚本实时解决问题。

---

## 5. 混合链接系统 (BHL)

为了平衡开发效率与运行性能，Butler 引入了 **BHL (Butler Hybrid-Link)**。

-   **跨语言透明性**: 开发者可以使用 Go 处理并发，用 C++ 处理数学运算，而 Python 层只需像调用普通函数一样发送 JSON-RPC 请求。
-   **解耦设计**: BHL 模块作为独立的子进程运行，通过管道通信。这意味着即使某个二进制模块崩溃，也不会导致 Butler 主进程异常退出。

---

## 6. 存储与记忆系统

系统采用多级存储架构：

-   **短期记忆 (Buffer)**: 记录当前会话的上下文，用于 NLU 连贯性。
-   **长期记忆 (Vector DB)**:
    -   优先使用 **Redis** 提供大规模向量检索。
    -   无 Redis 环境下自动降级至 **Zvec**（阿里云开源的极速向量数据库）实现纯本地索引。
    -   极端环境下使用 **SQLite** 存储结构化数据。
-   **日志与画像**: 通过 `HabitManager` 分析用户行为，实现个性化响应。

---

## 7. 安全防护体系

-   **FileSystemGuard**: 核心代码目录（如 `butler/`, `package/`）被锁定，防止误删或恶意篡改。
-   **双重加密**: 结合主密码与 6 位安全核心码，对用户敏感数据进行 AES-256 加密。
-   **自动化治理**: `AutonomousSwitch` 充当内核监护人，处理僵尸进程和资源冲突。
