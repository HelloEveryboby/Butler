---
id: geek_uninstaller
name: Geek Uninstaller
version: 1.0.0
description: 类 Geek Uninstaller 的深度卸载与系统管家。列出已装软件、执行残留扫描与强力卸载、清理系统垃圾、实时监控系统资源,纯 Python 无外部二进制依赖,与 sys_cleaner 的安装快照监视能力互补。
author: Butler Community
entry_point: main.py
frontend: index.html
icon: fa-trash-can-arrow-up
risk: medium
has_frontend: true
permissions:
  - File_System_Purge
  - Process_Enumerate
  - Package_Manager_Query
---

# Geek Uninstaller

为 Butler 打造的 **深度卸载 + 系统管家** 技能,灵感来自 Geek Uninstaller。
纯 Python 实现(psutil + 标准库),无需编译任何外部二进制,跨平台开箱即用。

## 与 sys_cleaner 的分工

| 能力 | sys_cleaner | geek_uninstaller |
|------|-------------|------------------|
| 安装前后快照监视 | ✅ 核心 | ➖ |
| 差异 Diff 清理 | ✅ | ➖ |
| 列出已安装软件 | ➖ | ✅ |
| 按名深度卸载 + 残留扫描 | ➖ | ✅ |
| 垃圾文件清理(临时/缓存/日志) | ➖ | ✅ |
| 实时系统监控(CPU/内存/进程) | ➖ | ✅ |

> 二者协同:先用 `sys_cleaner` 监视某次安装并捕获精确变更,日常的软件盘点、深度卸载与垃圾清理交给 `geek_uninstaller`。

## 核心功能

1. **软件盘点** — 跨平台枚举已安装软件
   - Linux: `.desktop` + dpkg / snap / flatpak
   - Windows: 注册表 Uninstall 项(64/32 位 + 用户级)
   - macOS: `/Applications` 下 `.app` 及其 Info.plist
2. **深度卸载** — 调用官方卸载程序 → 扫描用户目录残留(`~/.config`、`~/.cache`、`~/.local/share`)→ 清理残留
3. **垃圾清理** — 临时目录 / 用户缓存 / 包管理器缓存(pip·npm·apt·cargo 等)/ 回收站 / 旧日志(>7 天)
4. **系统监控** — CPU(每核)/ 内存 / Swap / 磁盘 / 网络 / 进程 Top 排行

## 安全设计

- 所有删除操作默认 **dry-run 模拟**,仅报告将做什么,不实际删除。
- 前端“执行”按钮需用户二次确认;目录类缓存只清空内容,保留目录本身。
- 注册表项扫描仅作展示,不在通用清理流程中误删(避免系统损坏)。

## 暴露的 Action(handle_request)

| action | 参数 | 说明 |
|--------|------|------|
| `list_software` | — | 返回已安装软件列表 |
| `scan_leftovers` | `name` | 扫描指定软件名的残留文件 |
| `uninstall` | `name`, `dry_run` | 深度卸载并清理残留 |
| `scan_junk` | `categories` | 扫描系统垃圾文件 |
| `clean_junk` | `dry_run`, `categories` | 清理垃圾文件 |
| `system_info` | — | 返回系统静态信息 + 资源快照 |
| `top_processes` | `limit`, `sort_by` | 返回占用最高的进程 |

## 依赖

- `psutil>=5.9`
- `rich>=13.0`(CLI 模式可选,前端模式不需要)
