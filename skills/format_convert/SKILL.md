---
name: format_convert
description: "高效、模块化的分布式文档格式转换工具，支持 Markdown -> HTML 以及 JSON/YAML -> CSV"
version: "1.0.0"
risk: "low"
provides:
  - "document.converted"
requires: {}
isolation: "process"
---

# Document Format Conversion Tool

This skill converts document formats using efficient streaming, distributed Go runners, or local Python fallbacks.

## Supported Conversions:
- **Markdown (MD) -> HTML**: Parses Markdown content with CSS styling and optional watermark.
- **JSON -> CSV**: Flattens nested JSON objects or arrays and maps them to a CSV spreadsheet.
- **YAML -> CSV**: Flattens nested YAML objects or arrays and maps them to a CSV spreadsheet.
