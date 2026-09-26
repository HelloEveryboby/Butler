---
name: password_generator
description: 安全密码与口令生成器。基于密码学安全随机数生成高熵密码、易记口令短语、PIN 码，并支持强度评估。
provides:
  - security.password.generate
requires: {}
risk: low
keywords:
  - 密码
  - 口令
  - 生成
  - 安全
  - passphrase
  - password
  - pin
---

# 安全密码生成器 (Password Generator)

本技能基于 Python `secrets` 模块（密码学安全随机数源）生成各类凭证，全程不写入磁盘，不落日志。

## 核心能力

### 1. 随机密码 (`generate`)
- 可配置长度（默认 16 位）
- 可选字符集：大写字母、小写字母、数字、特殊符号
- 默认开启全部字符集，可按需关闭

### 2. 易记口令短语 (`passphrase`)
- 使用常用英文单词组合（5-8 个单词）
- 单词间用分隔符连接（默认 `-`）
- 可选择是否插入随机数字增强熵

### 3. PIN 码 (`pin`)
- 生成 4-8 位纯数字 PIN

### 4. 密码强度评估 (`strength`)
- 分析长度、字符种类、常见模式
- 返回弱/中/强等级及改进建议
