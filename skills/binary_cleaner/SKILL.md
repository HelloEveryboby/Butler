---
id: binary_cleaner
name: Binary Cleaner
version: 1.0.0
description: 扫描并清理项目和系统中不必要的二进制文件、构建产物、编译缓存。支持 Python/Node/C++/Rust/Go/Java/Docker 等多语言生态，dry-run 安全预览。
author: Butler
entry_point: main.py
icon: fa-broom
risk: medium
permissions:
  - File_System_Read
  - File_System_Purge
  - Docker_API
---

# Binary Cleaner

为 Butler 打造的**不必要的二进制文件扫描与清理**技能。

## 与现有 Skill 的分工

| 能力 | sys_cleaner | geek_uninstaller | binary_cleaner |
|------|:-:|:-:|:-:|
| 安装快照差异 | ✅ | | |
| 软件卸载 | | ✅ | |
| 垃圾/缓存清理 | | ✅ | |
| **构建产物扫描** | | | ✅ |
| **.pyc / __pycache__** | | | ✅ |
| **C/C++ .o .so 编译产物** | | | ✅ |
| **Docker 孤立资源** | | | ✅ |
| **多语言项目扫描** | | | ✅ |
| **项目级深度扫描** | | | ✅ |

## 扫描类别

| 类别 | 目标 | 典型节省 |
|------|------|---------|
| python_build | `__pycache__` `*.pyc` `build/` `dist/` `*.egg-info` | 50-500 MB |
| node_build | `.next/` `.nuxt/` `dist/` `.cache/` | 100 MB - 2 GB |
| cpp_build | `*.o` `*.obj` `*.a` 项目内 `*.so` `*.dylib` | 100 MB - 5 GB |
| rust_build | `target/debug/` `target/release/` (中间产物) | 500 MB - 10 GB |
| go_build | `bin/` 缓存的编译二进制 | 100 MB - 2 GB |
| java_build | `*.class` `build/` `target/` | 50 MB - 1 GB |
| docker | dangling images / unused volumes / build cache | 1-50 GB |
| pkg_cache | pip/npm/cargo/go/brew 缓存 | 100 MB - 5 GB |
| ide_cache | `.idea/caches` `.gradle/caches` `.vscode` 缓存 | 50-500 MB |
| temp_binaries | `/tmp` 下超期可执行文件、core dump | 不定 |

## 安全设计

- 默认 **dry-run** 模式：只扫描报告，不删除
- 系统级 `.so` / `.dll` 自动排除（只扫项目目录）
- 删除前生成清单文件，支持回滚
- 高风险操作需二次确认

## 暴露的 Action

| action | 参数 | 说明 |
|--------|------|------|
| `scan` | `path`, `categories`, `depth` | 扫描指定路径的不必要二进制文件 |
| `clean` | `path`, `categories`, `dry_run` | 清理扫描到的文件 |
| `quick_scan` | — | 快速扫描 home 目录 |
| `project_scan` | `path` | 深度扫描单个项目目录 |
| `docker_clean` | `dry_run` | 清理 Docker 孤立资源 |
| `stats` | — | 返回上次扫描统计 |

## 依赖

- Python 标准库（无外部依赖）
- Docker CLI（可选，用于 Docker 清理）
