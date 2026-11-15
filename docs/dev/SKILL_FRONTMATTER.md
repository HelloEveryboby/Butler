# SKILL.md Front-Matter 规范（技能元数据）

> 目标：让每个技能**可被发现**——目录（`skills/CATALOG.md`）、搜索、`butler skill info` 都依赖这份元数据。
> 原则：**有 front-matter 最好，没有也能跑**（自动降级解析），但新技能请按本规范编写。

## 规范

每个技能的 `skills/<name>/SKILL.md` **推荐**以 YAML front-matter 开头：

```markdown
---
name: pdf
description: PDF 文档处理：格式转换、合并拆分、文本提取
tags: [文档, 效率]
version: 1.0.0
---

# PDF 助手

（正文：用法、示例、接口说明……）
```

### 字段说明

| 字段 | 必填 | 说明 |
| :--- | :--- | :--- |
| `name` | 推荐 | 技能显示名（缺省用目录名） |
| `description` | 推荐 | 一句话说明（≤120 字），会出现在目录与搜索结果里 |
| `tags` | 可选 | 分类标签列表，如 `[文档, 效率]` |
| `version` | 可选 | 语义化版本 |
| `user-invocable` | 可选 | 用户是否可直接调用（默认 true） |
| `disable-model-invocation` | 可选 | 是否禁止 LLM 自动调用（默认 false） |

### 降级规则（无 front-matter 时）

1. 名称 ← 首个 `# 标题`（再降级用目录名）；
2. 描述 ← 正文首个段落（截断 120 字）；
3. 标签 ← 空。

## 与工具链的关系

| 工具 | 用途 |
| :--- | :--- |
| `scripts/gen_skill_catalog.py` | 生成 `skills/CATALOG.md` 目录页 |
| `butler skills catalog` | 同上（CLI 入口） |
| `butler skill info <name>` | 展示技能详情（读取同一份元数据） |
| `butler.core.skill_registry` | 运行时加载元数据（`load_skill_metadata`） |

## 示例

```markdown
---
name: expense_tracker
description: 记账与开支分析：快速记录、分类统计、月度报表
tags: [效率, 财务]
version: 0.2.0
---

# Expense Tracker

## 用法
...
```

改完 SKILL.md 记得跑 `butler skills catalog` 刷新目录。
