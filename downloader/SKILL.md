---
id: downloader
name: 资源下载器
description: 极速、稳定、全协议支持的智能下载引擎，基于 Motrix 视觉蓝本与 Linux 风格 CLI/TUI 下载体验。
version: 2.1.0
author: Jules
icon: fa-download
risk: low
has_frontend: true
frontend: ui/index.html
python_entry: __init__.py
---

# 🚀 资源下载器 (Resource Downloader)

高可用、多线程、跨端联动的全能下载套件，支持 Linux 风格 CLI/TUI 终端指令与 Motrix 蓝本 UI。

## 核心特性
- **Motrix 蓝本 GUI**：基于 Glassmorphism 毛玻璃视觉设计，包含任务分类侧边栏、实时网速与数据分片实时填充图。
- **Linux 风格 CLI / TUI 指令**：`butler download <URL> [存放位置]` 或 `下载 <URL> [存放位置]`，支持 `-o / --output` 指定保存路径与 `-d / --daemon` 后台守护进程下载。
- **路径自动补全与创建**：未指定保存路径时默认保存至 `./download/`，自动执行 `mkdir -p` 递归创建。
- **Rich TUI 动态进度**：终端模式下实时渲染多线程分片进度块、网速仪表盘与 ETA 剩余时间。
