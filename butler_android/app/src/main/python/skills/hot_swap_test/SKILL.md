---
skill_name: hot_swap_test
description: Butler 核心架构验证：热插拔与隔离运行示例。
provides: ["system.test.isolation"]
isolation: process
---

# Hot Swap & Isolation Test Skill

这是一个用于验证 Butler “One Folder = One Skill” 架构的示例技能。

### 特性：
1. **进程隔离**：该技能在独立的 Python 子进程中运行，不会污染主进程。
2. **JSON-RPC 通信**：通过标准输出发送 `{"action": "speak", "payload": {...}}` 与管家核心对话。
3. **环境自洽**：支持在目录下创建 `.lib` 并自动加载依赖。
