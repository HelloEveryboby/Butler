---
id: pixel_pet
name: Pixel Pet
version: 1.0.0
description: 极致优雅、伴随启动、基于 PyWebview 独立透明置顶微型窗口的 Butler 像素电子宠物。
author: Butler Developer
entry_point: main.py
frontend: ui/index.html
icon: fa-ghost
is_core: true
is_long_running: true
permissions: []
---

# 像素电子宠物 (Pixel Pet)

这是一个专为 Butler 打造的“像素电子宠物”核心插件。

## 核心设计
1. **完全解耦 (One Folder = One Skill)**：遵循无外部依赖原则，采用事件驱动架构与 AI 系统绝对解耦。
2. **Apple 级极简与玻璃拟态**：圆角浮动气泡，结合 Apple 设计美学。
3. **独立透明微型视窗**：基于 PyWebview 容器，高亮置顶常驻桌面。
