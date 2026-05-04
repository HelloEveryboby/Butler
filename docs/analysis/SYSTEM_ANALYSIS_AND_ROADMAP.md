# Butler 系统深度分析与开发路线图 (2024-2026)

## 1. 现状分析 (System Audit)

Butler 目前是一个功能高度集成、架构多层演进的 AI 助手系统。经过对核心代码库（`butler/core/`）、扩展系统（`skills/`, `plugin/`, `package/`）以及前端桥接层（`frontend/program/`）的深入分析，总结现状如下：

### 1.1 架构亮点
*   **多模态扩展能力**：拥有 `Skill` (AI 友好)、`Plugin` (系统集成) 和 `Package` (独立脚本) 三套扩展机制，能够覆盖从简单脚本到复杂二进制程序的多种场景。
*   **KAIROS 协作套件**：初步构建了基于文件系统 `MessageBus` 的多智能体协作框架，支持任务分发 (`TaskManager`) 和自主决策循环。
*   **高性能本地化**：集成了 `Zvec` 向量库和 C++ 音频引擎，具备极强的离线工作能力和低延迟响应。
*   **精致的 UI 交互**：Modern UI 采用了现代化的玻璃拟态设计，且通过 `ModernBridge` 实现了前后端深度解耦。

### 1.2 核心问题与技术债 (Critical Issues)
*   **扩展系统碎片化 (System Fragmentation)**：
    *   `SkillManager`、`ExtensionManager` 和 `PluginManager` 功能重叠。
    *   `Skill` 是未来的方向（支持 SKILL.md），但旧的 `Plugin` 和 `Package` 仍占据大量存量逻辑，导致意图路由（Intent Routing）路径过长且逻辑复杂。
*   **意图分发链路不统一**：
    *   意图匹配在 `NLUService`、`IntentRegistry` (本地相似度) 和 `SkillManager.match_skill` 之间跳转，缺乏一个统一的“中央分发器”，增加了调试难度。
*   **异步与状态同步瓶颈**：
    *   大量任务在 `Jarvis` 主循环中启动线程，缺乏统一的生命周期管理。
    *   `ModernBridge` 中的 JS 注入式更新（`evaluate_js`）在并发任务多时可能存在时序风险。
*   **自主性（KAIROS）尚处于早期阶段**：
    *   `TeamManager` 的智能体循环（`_teammate_loop`）目前更多是占位符，缺乏真正的工具调用集成和复杂的规划能力。

---

## 2. 后续开发路线图 (Future Roadmap)

为了将 Butler 从“功能堆砌的工具箱”进化为“真正的个人 AI 代理架构”，建议分为以下三个阶段进行开发：

### 第一阶段：架构大一统 (Consolidation & Core Strengthening) - 3-6个月
**目标：消除冗余，统一标准。**

1.  **统一扩展协议 (Unified Skill Interface)**：
    *   全面转向以 `SKILL.md` 为核心的规范。
    *   将 `Plugin` 和 `Package` 逐步重构或包装为 `Skill`。
    *   实现统一的 `Manifest` 定义，包含意图触发词、工具声明和权限要求。
2.  **重构意图路由器 (Central Intent Hub)**：
    *   建立一个单点入口的 `Dispatcher`，按序尝试：精确命令 -> 本地语义匹配 -> 智能体 NLU 提取。
    *   引入“拦截器”机制，支持在执行前进行权限检查或数据预处理。
3.  **标准化日志与追踪 (Observability)**：
    *   利用 `TaskManager` 为每个任务分配唯一的追踪 ID (Trace ID)，贯穿日志、UI 反馈和记忆存储。

### 第二阶段：KAIROS 2.0 - 自主协作进化 (Autonomous Excellence) - 6-12个月
**目标：实现真正的多智能体协同作业。**

1.  **强化自主循环 (Agentic Loop)**：
    *   将 `Jarvis` 的主循环重构为可配置的 Agent 架构，支持多步规划（CoT）和自我修正。
    *   集成 `allowed-tools` 机制，让智能体能安全地调用系统脚本。
2.  **增强任务看板 (Business Logic Awareness)**：
    *   将 `TaskManager` 的持久化看板与 UI 深度绑定，允许用户通过自然语言管理长周期任务的依赖（如：“等我收到那封邮件后再处理这个 Excel”）。
3.  **多智能体记忆共享 (Shared Memory)**：
    *   实现团队级的向量索引，使不同 Agent 能共享对特定项目的理解。

### 第三阶段：生态与硬件融合 (Ecosystem & Hardware) - 12个月+
**目标：破圈与全场景覆盖。**

1.  **硬件联动深化**：
    *   利用已有的 `hardware_stm32` 和串口协议，将 Butler 部署为智能家居或桌面机器人的核心大脑。
2.  **移动端/跨平台控制**：
    *   开发轻量化 Web 控制台或手机端快捷入口，通过 `RunnerServer` 远程控制 Butler 宿主机。
3.  **Butler 商店/市场**：
    *   基于 `SkillManager` 的 Git 安装功能，建立非官方的技能分发机制。

---

## 3. 开发准则 (Implementation Principles)

*   **Surgical Changes**：只在需要重构时动刀，保持现有算法库的稳定性。
*   **Goal-Driven**：每一个新 Skill 的加入都必须有明确的 `SKILL.md` 验证路径。
*   **Privacy First**：所有的记忆整合（Dream Engine）必须在本地 Zvec 或用户私有向量库中完成。

---
*由 Jules 分析并撰写 | 2025年5月22日*
