---
name: quick_launcher
description: 快捷指令与快速启动核心插件。支持注册和启动各种高频快捷命令与关联应用，支持通过 EventBus 拦截事件。
provides:
  - system.launcher.run
requires: {}
risk: low
---

# 快速启动面板 (Quick Launcher)

本核心插件致力于缩短高频操作的调用路径。

## 核心能力
1. **指令注册/映射**：配置常用的别名和对应的启动路径或系统命令行（如：`browser` -> 启动浏览器，`tasks` -> 查看任务）。
2. **EventBus 触发**：与 `EventBus` 联动，支持通过事件来触发快速启动动作。
3. **安全审计**：配合 `interpreter.py` 安全执行。
