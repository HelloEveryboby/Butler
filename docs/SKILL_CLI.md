# Butler 技能操作手册

> 版本: 2.0 | 适用: Butler v3.x | 更新: 2026-08-08

---

## 目录

1. [架构概述](#1-架构概述)
2. [技能类型](#2-技能类型)
3. [命令行速查](#3-命令行速查)
4. [命令详解](#4-命令详解)
5. [Chat 内命令](#5-chat-内命令)
6. [TUI 图形界面](#6-tui-图形界面)
7. [开发指南](#7-开发指南)
8. [附录: 完整选项表](#8-附录-完整选项表)

---

## 1. 架构概述

Butler 采用 **"One Folder = One Skill"** 架构：

```
skills/
├── butler_expert/          # 一个技能 = 一个文件夹
│   ├── SKILL.md            # 技能指令 (AI 读取)
│   ├── manifest.json       # 元数据清单
│   ├── __init__.py         # Python 入口 (可选)
│   └── config.yaml         # 配置文件
├── pdf/
│   ├── SKILL.md
│   └── manifest.json
└── ...
```

每个技能文件夹会被自动发现，无需手动注册。系统支持递归扫描（深度 2 层）。

---

## 2. 技能类型

系统将技能分为两类，自动检测：

| | 🐍 USER (可调用) | 📖 AGENT (Agent) |
|---|---|---|
| **检测条件** | 有 Python 入口 + `handle_request` 或 `main` | 仅 SKILL.md / manifest，无 Python 入口 |
| **谁能调用** | 用户 + AI | 仅 AI 大模型 |
| **CLI 运行** | ✅ `skill run` | ❌ 被阻止 |
| **Chat 调用** | ✅ `/skill` | ✅ AI 自动匹配 |
| **TUI 运行** | ✅ ▶ 按钮 | ❌ 按钮禁用 |
| **典型示例** | `butler_expert`, `pixel_pet` | `wps-office-expert`, `docx`, `pdf` |

### 显式声明类型

在 `manifest.json` 或 `config.yaml` 中可手动声明类型，覆盖自动检测：

```json
{
  "callable": "user",
  "description": "可直接调用的技能"
}
```

```yaml
callable: agent
description: 仅供 AI 使用
```

---

## 3. 命令行速查

### 基本形式

```bash
python butler_cli.py skill <command> [options] [args...]
```

或直接：

```bash
python butler/cli/skill_cmd.py <command> [options] [args...]
```

### 一句话速查

```bash
# 列出所有技能 (分类显示)
python butler_cli.py skill list

# 仅查看可调用技能
python butler_cli.py skill list -t user

# JSON 输出 (供脚本使用)
python butler_cli.py skill list -j

# 仅输出 ID (管道友好)
python butler_cli.py skill list -q

# 详细列表
python butler_cli.py skill list -l

# 运行技能
python butler_cli.py skill run <技能ID> [action] [--key value]

# 查看技能详情
python butler_cli.py skill info <技能ID>

# 查看操作手册 (本手册)
python butler_cli.py skill help
```

---

## 4. 命令详解

### 4.1 `list` — 列出技能

```bash
python butler_cli.py skill list [options]
python butler_cli.py skill ls [options]    # 别名
```

**选项:**

| 短选项 | 长选项 | 说明 |
|--------|--------|------|
| `-t` | `--type user` | 仅显示可调用技能 |
| `-t` | `--type agent` | 仅显示 Agent 技能 |
| `-l` | `--long` | 详细列表模式 (边框表格) |
| `-j` | `--json` | JSON 格式输出 |
| `-q` | `--quiet` | 仅输出 ID (管道友好) |
| `-h` | `--help` | 显示帮助 |

**示例:**

```bash
# 默认: 分类显示 (USER / AGENT)，彩色输出
python butler_cli.py skill list

# 仅 Agent 技能
python butler_cli.py skill list -t agent

# JSON 输出 → 供 jq 处理
python butler_cli.py skill list -j | jq '.[].id'

# 管道: 查找 docx 相关技能
python butler_cli.py skill list -q | grep -i docx

# 统计 USER 技能数量
python butler_cli.py skill list -j | jq '[.[] | select(.access_level=="user")] | length'
```

### 4.2 `run` — 运行技能

```bash
python butler_cli.py skill run <技能ID> [action] [options] [--key value...]
```

**参数:**

| 参数 | 说明 |
|------|------|
| `技能ID` | skills/ 下的文件夹名 (必填) |
| `action` | 技能动作 (默认 `run`) |
| `--key value` | 自定义参数 (传递给技能) |

**选项:**

| 短选项 | 长选项 | 说明 |
|--------|--------|------|
| `-o` | `--output <file>` | 输出结果到文件 |
| `-j` | `--json` | JSON 格式输出 |
| `-q` | `--quiet` | 安静模式 (仅输出结果) |
| | `--iso` | 强制隔离进程运行 (跳过直接加载) |
| `-h` | `--help` | 显示帮助 |

**示例:**

```bash
# 基础运行
python butler_cli.py skill run butler_expert

# 指定动作和参数
python butler_cli.py skill run butler_expert ask --query 架构

# 另一个示例
python butler_cli.py skill run karpathy_guidelines show

# 保存结果到文件
python butler_cli.py skill run format_convert -o /tmp/result.txt

# JSON 输出 → 管道处理
python butler_cli.py skill run butler_expert -j | jq '.answer'

# 安静模式 (用于脚本)
python butler_cli.py skill run hello_cli -q
```

**错误情况:**

```bash
# 技能未找到 → exit code 1
python butler_cli.py skill run nonexistent
# ❌ 技能 'nonexistent' 未找到

# Agent 技能不可直接运行 → exit code 2
python butler_cli.py skill run wps-office-expert
# ❌ 技能 'wps-office-expert' 是 Agent 技能
#    类型: 仅 AI 大模型可用
#    转为手动技能: 在 ... 中添加 main.py 或 __init__.py
```

### 4.3 `info` — 查看技能详情

```bash
python butler_cli.py skill info <技能ID> [options]
```

**选项:**

| 短选项 | 长选项 | 说明 |
|--------|--------|------|
| `-j` | `--json` | JSON 格式输出 |
| `-p` | `--preview <N>` | SKILL.md 预览字符数 (默认 600) |
| `-h` | `--help` | 显示帮助 |

**示例:**

```bash
# 查看详情 (含 SKILL.md 指令预览)
python butler_cli.py skill info butler_expert

# JSON 输出 (便于程序化处理)
python butler_cli.py skill info butler_expert -j

# 更长的 SKILL.md 预览
python butler_cli.py skill info pdf -p 2000
```

### 4.4 `help` — 查看操作手册

```bash
python butler_cli.py skill help
python butler_cli.py skill -h
python butler_cli.py skill --help
```

输出 man-page 风格的完整帮助信息。

---

## 5. Chat 内命令

在 Butler 对话界面中，可以使用以下技能管理命令：

### `/skills` — 列出技能

```
/skills
```

显示当前所有技能，区分 **🐍 可调用** 和 **📖 Agent** 两类。

### `/skill <技能ID> [action]` — 手动调用

```
/skill butler_expert
/skill butler_expert ask
/skill butler_expert ask 架构
/skill karpathy_guidelines show
```

### `/skill-info <技能ID>` — 查看详情

```
/skill-info butler_expert
/skill-info wps-office-expert
```

### `/skills_list [user|agent|all]` — 分类列表

```
/skills_list user
/skills_list agent
/skills_list
```

### `/skill_run <技能ID> [action]` — 运行技能

```
/skill_run butler_expert ask
```

---

## 6. TUI 图形界面

### 技能视图

在 TUI 中切换到 **"技能管理"** 视图：

- **Tab 1: 🐍 可调用技能** — 显示所有 USER 类型技能
- **Tab 2: 📖 Agent 技能** — 显示所有 AGENT 类型技能

### 操作按钮

| 按钮 | 说明 |
|------|------|
| 🔄 刷新技能 | 重新扫描 skills/ 目录 |
| ▶ 运行 | 运行选中的可调用技能 (仅 USER) |
| 📖 查看指令 | 查看 SKILL.md 或 manifest.json 内容 |
| 📋 详情 | 显示技能完整元数据 |

### 状态指示

- 选中 **USER** 技能 → ▶ 运行按钮 **启用**
- 选中 **AGENT** 技能 → ▶ 运行按钮 **禁用**，提示 "Agent 技能仅 AI 调用"

---

## 7. 开发指南

### 创建一个可调用技能

在 `skills/` 下创建文件夹，包含 Python 入口：

```
skills/my_skill/
├── SKILL.md              # AI 指令 (可选)
├── manifest.json         # 元数据
└── main.py               # Python 入口
```

**manifest.json:**

```json
{
  "name": "My Skill",
  "version": "1.0.0",
  "description": "示例技能",
  "actions": ["run", "config"],
  "callable": "user",
  "keywords": ["example"]
}
```

**main.py:**

```python
def handle_request(action: str, **kwargs):
    """技能入口函数。action 由用户或 AI 指定。"""
    entities = kwargs.get("entities", {})
    
    if action == "run":
        return {"status": "ok", "message": "技能运行成功"}
    elif action == "config":
        return {"status": "ok", "config": {"key": "value"}}
    
    return {"status": "error", "message": f"未知动作: {action}"}
```

### 创建一个 Agent 技能 (纯 AI)

```
skills/my_agent/
├── SKILL.md              # AI 读取的完整指令
└── manifest.json
```

**SKILL.md:**

```markdown
---
name: My Agent
version: 1.0.0
description: 由 AI 大模型执行的技能
callable: agent
keywords: ["agent", "example"]
---

# 角色

你是一个...

# 任务

当用户请求 X 时，你应该...

# 输出格式

返回 JSON: {"result": "..."}
```

### 从 Agent 转为可调用

只需在技能目录中添加 `main.py` 或 `__init__.py`，定义 `handle_request` 函数：

```bash
cd skills/my_agent
# 添加 Python 入口后，技能自动转为 USER 类型
python butler_cli.py skill list  # 会出现在 USER 分类下
```

### exit codes 约定

| 代码 | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 错误 (技能未找到、执行失败) |
| 2 | 用法错误 (Agent 技能不可直接运行、缺少入口) |

### 环境变量

| 变量 | 说明 |
|------|------|
| `NO_COLOR=1` | 禁用彩色输出 (适合脚本管道) |

```bash
# 无颜色输出 → 管道友好
NO_COLOR=1 python butler_cli.py skill list | grep butler
```

---

## 8. 附录: 完整选项表

### `list` 选项

| 选项 | 类型 | 说明 |
|------|------|------|
| `-t`, `--type` | `user`\|`agent` | 按类型过滤 |
| `-l`, `--long` | flag | 详细边框表格 |
| `-j`, `--json` | flag | JSON 输出 |
| `-q`, `--quiet` | flag | 仅 ID |
| `-h`, `--help` | flag | 帮助 |

### `run` 选项

| 选项 | 类型 | 说明 |
|------|------|------|
| `-o`, `--output` | `file` | 输出到文件 |
| `-j`, `--json` | flag | JSON 输出 |
| `-q`, `--quiet` | flag | 安静模式 |
| `--iso` | flag | 隔离进程运行 |
| `-h`, `--help` | flag | 帮助 |

### `info` 选项

| 选项 | 类型 | 说明 |
|------|------|------|
| `-j`, `--json` | flag | JSON 输出 |
| `-p`, `--preview` | `N` | 预览字符数 (默认 600) |
| `-h`, `--help` | flag | 帮助 |

### 全量命令索引

```
butler skill list [-t user|agent] [-l] [-j] [-q] [-h]
butler skill ls   [-t user|agent] [-l] [-j] [-q] [-h]

butler skill run  <id> [action] [-o file] [-j] [-q] [--iso] [-h] [--key val...]

butler skill info <id> [-j] [-p N] [-h]

butler skill help
```

---

**Man page 风格帮助**: `python butler_cli.py skill help`

**© 2026 Butler Community**