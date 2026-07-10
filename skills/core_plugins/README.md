# Butler 核心插件开发指南 (Core Plugins Developer Guide)

核心插件（Core Plugins）是 Butler 系统的“原生内脏”，位于 `skills/core_plugins/` 目录下。与限制在沙箱运行的标准技能（Standard Skills）不同，核心插件在系统启动时强行自动加载，常驻内存，享有特权级的系统访问权限（Privileged Access）。

---

## 1. 核心插件 vs 标准技能

| 维度 | 核心插件 (Core Plugins) | 标准技能 (Standard Skills) |
| --- | --- | --- |
| **存放路径** | `skills/core_plugins/<plugin_id>/` | `skills/<skill_id>/` |
| **加载时机** | 系统初始化（SetUp）时强行自动加载 | 按需延迟加载 (Lazy Loading) |
| **常驻状态** | 持续常驻内存，禁止热卸载 (Locked) | 可随时热插拔、热卸载 |
| **运行容器** | 主进程中直接运行 | 独立子进程或 Sandbox 运行 (Isolation) |
| **系统特权** | 享有 EventBus, MessageBus, HAL 传感器, 存储库及 GUI 桥接器直接注入 | 只能通过受限的 API 沙箱调用外部工具 |

---

## 2. 核心架构与生命周期 (Lifecycle)

每个核心插件均采用 **“One Folder = One Skill”** 的高内聚设计哲学。其标准文件结构如下：

```
skills/core_plugins/my_core_plugin/
├── SKILL.md          # 插件元数据（YAML Frontmatter）与描述
├── main.py           # 插件核心逻辑入口（handle_request + initialize_core）
└── requirements.txt  # 依赖声明（若有）
```

### 生命周期阶段：
1. **自动扫描 (Scan)**：`SkillManager.load_skills()` 在发现路径包含 `core_plugins` 时，自动标记 `is_core = True`。
2. **强行加载 (Force Load)**：在初始化结束前，系统自动运行 `_load_python_runtime`，将模块注入 `sys.modules`。
3. **特权注入 (Dependency Injection)**：若检测到入口模块中包含 `initialize_core(context)` 函数，系统会自动实例化 `CorePluginContext` 并调用该函数。
4. **常驻后台 (Constant Residence)**：阻止用户运行任何针对该插件的卸载（uninstall）指令。

---

## 3. 特权上下文 API (`CorePluginContext`)

当 `initialize_core(context)` 被调用时，注入的 `context` 参数包含以下核心设施的直接引用：

* **`context.event_bus`**：全局发布-订阅总线。
  - 订阅事件：`context.event_bus.subscribe("my_event", callback)`
  - 发布事件：`context.event_bus.emit("my_event", *args, **kwargs)`
* **`context.message_bus`**：多 Agent 或多系统间通信消息总线。
* **`context.blackboard`**：全局黑板，用于存储高频、短期的系统和传感器快照状态。
  - 写入：`context.blackboard.write("key", value)`
* **`context.data_storage`**：持久化键值存储。自动支持 Redis 和本地 JSON 文件双向降级。
  - 存储：`context.data_storage.save("my_plugin", "key", data_dict)`
  - 读取：`context.data_storage.load("my_plugin", "key")`
* **`context.system_sensor`**：`butler.core.hal` 的硬件传感器，可实时安全拉取 CPU、内存、磁盘和电池状态。
  - 读取：`context.system_sensor.read()`

---

## 4. 示例：开发一个自定义核心插件

### 步骤 1：创建目录和元数据 `SKILL.md`
在 `skills/core_plugins/hello_core/` 创建 `SKILL.md`：

```yaml
---
name: hello_core
description: 一个简单的特权核心示例插件。
provides:
  - system.hello.info
requires: {}
risk: low
---

# Hello Core 极简示例

本核心插件示范了如何接收注入的特权上下文，并在 EventBus 上发布自定义消息。
```

### 步骤 2：实现 main.py
创建 `skills/core_plugins/hello_core/main.py`：

```python
import logging

logger = logging.getLogger("hello_core")
_context = None

def initialize_core(context):
    """特权注入钩子"""
    global _context
    _context = context
    logger.info("Hello Core has privileged access now!")

    # 示范：订阅事件
    _context.event_bus.subscribe("system:tick", on_tick)

def on_tick():
    logger.info("Tick event received inside Hello Core!")

def handle_request(action, **kwargs):
    """标准执行入口"""
    global _context
    if action == "run":
        # 使用持久化存储
        cnt = _context.data_storage.load("hello_core", "count") or 0
        cnt += 1
        _context.data_storage.save("hello_core", "count", cnt)
        return f"Hello, Butler Core! This plugin has been run {cnt} times."
    return "Unsupported action."
```

恭喜！当 Butler 重新启动时，您的全新特权核心插件将被无缝加载，开始守卫系统安全。
