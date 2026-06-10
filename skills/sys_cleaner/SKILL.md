---
id: sys_cleaner_pro
name: System Cleaner Pro
version: 1.0.0
description: 基于低权限双向快照比对技术的软件安装监视与深度残留强力清理工具
author: Butler Developer
entry_point: main.py
frontend: index.html
icon: fa-shield-halved
permissions:
  - UAC_Dynamic_Elevate
  - Registry_Read_Write
  - File_System_Purge
---

# SysCleaner Pro

这是一个专门为 Butler 打造的专业级系统清理与安装监视扩展模块。

## 核心功能
1. **安装监视**：生成安装前后的系统快照并比对差异。
2. **残留清理**：根据分析日志执行强力物理擦除。
3. **跨平台支持**：适配 Windows (Registry/Files), macOS 和 Linux (Files)。

## 使用说明
- 点击“开启安装监视”捕捉当前系统状态。
- 安装您想监视的软件。
- 再次点击按钮停止监视并分析日志。
- 如果需要彻底清除，点击“强力清除残留”并授予系统权限。

## 安全性
平时以无害的低权限安全运行，仅在执行物理擦除时经用户授权触发系统 UAC/sudo。
