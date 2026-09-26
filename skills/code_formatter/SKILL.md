---
name: code_formatter
description: 代码与数据格式化工具。支持 JSON、YAML、XML 的美化排版、压缩、校验，并可自动检测格式。
provides:
  - dev.format
  - dev.validate
requires: {}
risk: low
keywords:
  - 格式化
  - 美化
  - json
  - yaml
  - xml
  - 校验
  - format
  - beautify
---

# 代码格式化器 (Code Formatter)

本技能提供 JSON、YAML、XML 三种常见数据格式的美化、压缩与校验能力，自动检测输入格式。

## 核心能力

### 1. 美化排版 (`format`)
- 自动检测格式（JSON / YAML / XML）
- 缩进美化，对齐层级
- 返回格式化后的文本

### 2. 压缩 (`minify`)
- 去除所有空白和换行
- 生成最小体积的文本

### 3. 校验 (`validate`)
- 检查语法是否合法
- 返回错误位置和原因

### 4. 格式转换 (`convert`)
- JSON ↔ YAML 互转

## 支持格式
- **JSON**: 标准 JSON 语法
- **YAML**: YAML 1.1/1.2（需 PyYAML，未安装时优雅降级）
- **XML**: 标准 XML 语法
