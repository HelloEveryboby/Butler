---
name: translator
description: 一个简单的翻译技能，支持中英文互译。
keywords: [翻译, translate, 英语, 中文]
allowed-tools: Bash(python:scripts/translate.py)
---

# 翻译助手技能

当你需要翻译文字时，我会调用此技能。

## 使用指引
1. 如果用户输入中文，将其翻译为英文。
2. 如果用户输入英文，将其翻译为中文。
3. 调用 `scripts/translate.py` 来执行最终翻译逻辑。
