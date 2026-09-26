---
name: text_analyzer
description: 文本分析与统计工具。提供字数、词频、句子统计、中英文可读性评估、关键词提取等能力。
provides:
  - text.analyze
  - text.keywords
requires: {}
risk: low
keywords:
  - 文本
  - 统计
  - 词频
  - 可读性
  - 关键词
  - analyze
  - text
---

# 文本分析器 (Text Analyzer)

本技能对输入文本进行多维度统计分析，支持中英文混合文本。

## 核心能力

### 1. 全面统计 (`analyze`)
- 字符数（含/不含空格）
- 单词数（英文）、中文字符数
- 句子数、段落数
- 平均句长、平均词长
- 词频 Top 10

### 2. 可读性评估 (`readability`)
- 英文：Flesch Reading Ease 分数（0-100，越高越易读）
- 中文：基于平均句长和常用字比例的简化评估
- 给出对应年级水平

### 3. 关键词提取 (`keywords`)
- 基于词频和位置权重提取 Top N 关键词
- 内置中文停用词表过滤

### 4. 词频统计 (`wordfreq`)
- 返回词频排行，支持指定数量
- 过滤停用词
