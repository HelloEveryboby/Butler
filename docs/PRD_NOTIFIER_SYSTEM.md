# Butler (Jarvis) 智能事件提醒系统 (Notifier) 需求文档 (PRD)

## 1. 项目背景与目标
为了提升 Butler 系统的实时响应能力与交互体验，我们需要设计一套高度解耦、视觉优雅且低延迟的**智能事件提醒系统 (Notifier)**。该系统旨在将后端事件（如硬件状态、定时任务、Skill 触发）以标准化的方式推送到前端 UI，并提供交互与记录功能。

### 核心目标
*   **三端解耦**：实现主前端、逻辑中台与后端核心的完全分离。
*   **极致视觉**：采用 Glassmorphism (毛玻璃) 设计与“呼吸感”动态效果。
*   **零依赖 (Zero-dependency)**：严格基于 Python 标准库与原生 Web 技术（HTML/CSS/JS）。
*   **高可扩展性**：支持“One Folder = One Skill”模式下的无缝调用。

---

## 2. 系统架构设计

### 2.1 三层解耦模型
1.  **Backend (后端系统)**：
    *   位于 `programs/bcli/` 及 `butler/core/`。
    *   负责事件监测（硬件信号、系统状态、传感器数据）。
    *   通过 BHL (Butler Hybrid Link) 协议向逻辑层发送指令。
2.  **Logic Layer (逻辑中台)**：
    *   作为 `notifier_system.py` 核心服务运行于 Python 侧。
    *   在前端容器（pywebview）内作为不可见的桥接层运行。
    *   负责事件的分发、持久化、定时销毁逻辑以及音量反馈调度。
3.  **Main UI (主前端)**：
    *   基于 HTML/CSS/JS 实现。
    *   仅负责通知的渲染（Toast、全屏覆盖）与用户交互。

---

## 3. 核心功能需求

### 3.1 触发与分发机制
*   **标准化接口**：提供 `Notifier.push(event_data)` 接口供所有核心组件与 Skill 调用。
*   **BHL 联动**：C++ 后端通过 JSON-RPC 格式触发 Python 侧的提醒逻辑。
*   **观察者模式**：支持多个 UI 组件订阅同一事件流。

### 3.2 UI 表现与交互
*   **视觉风格**：
    *   **暗黑模式 + 毛玻璃**：使用 `backdrop-filter: blur()`。
    *   **呼吸感**：通过 CSS 动画实现背景或边框的轻微光效起伏。
    *   **时间标注**：每个弹窗左上角显示精确到秒的事件发生时间。
*   **显示模式**：
    *   **Toast 弹窗**：非侵入式，出现在屏幕角落。
    *   **全屏/区域覆盖**：高优先级事件，覆盖当前 UI 并应用模糊滤镜，中心高亮。
*   **自动关闭**：5-10 秒无操作后自动消失，逻辑层需精准控制计时。
*   **交互逻辑**：点击提醒内容可弹出详细对话框进行数据修改。

### 3.3 联动逻辑 (Volume Algorithm)
*   **环境音量自适应**：在触发提醒前，调用 `HardwareManager` 获取环境噪音。
*   **反馈策略**：根据环境噪音频率（Distance/Freq）动态调整提醒音效的输出音量。

### 3.4 持久化与日志
*   **存储位置**：`data/notifications.db` (SQLite)。
*   **记录内容**：事件 ID、来源 Skill、触发时间、内容摘要、交互状态（已忽略/已修改）。
*   **目的**：支持后续的历史回溯与数据审计。

---

## 4. 开发要求与约束
*   **技术栈**：Python 3.x (标准库), HTML5, CSS3, JavaScript (ES6), SQLite3。
*   **模块化**：确保代码符合 `butler/core/` 的系统服务标准，易于被外部 Skill 引用。
*   **性能**：UI 响应延迟应低于 100ms，且在高并发提醒下不发生界面卡顿。

---

## 5. `notifier_system.py` 类结构草拟

```python
class Notifier:
    def __init__(self):
        # 初始化数据库连接与事件总线
        pass

    def push(self, event_data: dict):
        """
        供外部调用的主接口
        event_data: {
            "title": str,
            "content": str,
            "priority": int,
            "source": str,
            "action_data": dict
        }
        """
        # 1. 记录日志到数据库
        # 2. 调用音量调节算法
        # 3. 通过 EventBus/Bridge 发送给前端
        # 4. 启动 5-10s 销毁计时器
        pass

    def _apply_volume_linkage(self):
        # 调用 hardware_manager 调整音量
        pass

    def _persist_event(self, event):
        # SQLite 存储逻辑
        pass
```

---

**批准人**：[User Name]
**创建日期**：2024-05-22
**状态**：草案待评审
