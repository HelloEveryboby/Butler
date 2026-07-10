---
name: system_monitor
description: 系统资源监控核心插件。读取系统 CPU、内存、磁盘以及电池信息，写入黑板并在界面上输出精美的可视化进度条。
provides:
  - system.status.card
requires: {}
risk: low
---

# 系统资源监控器 (System Resource Monitor)

本核心插件常驻后台，定期或按需检测操作系统的 CPU、内存、硬盘和电池状态。

## 核心能力
1. **硬件读取**：依托 `butler.core.hal` 硬件抽象层安全读取物理/虚拟系统运行参数。
2. **黑板写入**：将最新监控数据定期写入全局黑板（Blackboard），供多 Agent 团队或决策链调用。
3. **极简卡片渲染**：为 Modern GUI 和 Classic Command Panel 提供圆角、带呼吸感的高亮进度条/仪表渲染格式。
