---
name: ClipMagic
description: Smart clipboard background service with AST/Regex detection.
triggers:
  - "clipboard"
  - "clip"
provides:
  - "clipboard.text"
  - "clipboard.type"
python_entry: clip_analyzer.py
binary_src: clip_listener.go
risk: low
---

# ClipMagic

Non-polling clipboard listener. Detects code, URLs, and IP addresses automatically.
Uses Go for OS event hooks and Python for AST/Regex analysis.
