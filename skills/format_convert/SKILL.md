---
name: format_convert
description: "全功能多格式文档互相转换工具，支持 Markdown、HTML、PDF、DOCX、EPUB、XLSX、CSV、JSON、YAML 以及图片格式的统一转换与倒查"
version: "2.0.0"
risk: "low"
provides:
  - "document.converted"
requires: {}
isolation: "process"
---

# 全功能文档格式转换中心 (Format Convert Skill)

整合全系统文档格式转换功能，提供统一的分布式与本地双引擎转换服务。

## 核心转换能力：
- **Markdown 导出**：Markdown -> HTML / DOCX / EPUB / PDF / PNG / JPG / WEBP
- **数据与表格**：JSON / YAML -> CSV / XLSX，CSV / JSON -> MD 表格
- **逆向转成 Markdown**：DOCX / PDF / HTML / EPUB / PPTX / XLSX / CSV / 图片 -> Markdown
- **图片编码处理**：PNG / JPG -> WEBP / BASE64
