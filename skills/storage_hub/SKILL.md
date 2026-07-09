---
name: Storage Hub
description: 极简网盘聚合引擎 (OneDrive, WebDAV/AList, Baidu, Quark)
version: 1.0.0
author: Jules
risk: high
provides:
  - storage.cloud.aggregate
  - storage.cloud.transfer
requires:
  - net.http
  - auth.vault
python_entry: hub_manager.py
frontend: ui/index.html
---

# 🏗️ Storage Hub: Local-First 网盘聚合引擎

基于 "One Folder = One Skill" 架构实现的网盘中间层，支持跨盘不落地中转。

## 核心特性
- **Local-First**: 零云端中转，所有 IO 均在本地 Go 引擎完成。
- **内存管道**: 跨盘传输无需占用本地磁盘。
- **极简视觉**: Glassmorphism 毛玻璃 UI，象限式容量监控。

## 支持厂商
- [x] OneDrive (Microsoft Graph API)
- [x] WebDAV / AList (Standard Basic Auth)
- [ ] 百度网盘 (PCS API)
- [ ] 夸克网盘 (Web Cookie)
