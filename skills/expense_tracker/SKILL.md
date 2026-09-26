---
name: expense_tracker
description: 个人记账与消费统计工具。记录收支、按类别/月份汇总、生成消费报告，数据本地 JSON 存储。
provides:
  - finance.expense.track
  - finance.expense.report
requires: {}
risk: low
keywords:
  - 记账
  - 消费
  - 支出
  - 收入
  - 账单
  - 预算
  - expense
  - finance
---

# 记账本 (Expense Tracker)

本技能提供轻量级个人财务管理，数据以 JSON 格式存储在技能目录下，不上传、不联网。

## 核心能力

### 1. 记录收支 (`add`)
- 记录一笔收入或支出
- 字段：金额、类别、描述、日期（可选，默认今天）
- 类别示例：餐饮、交通、购物、娱乐、住房、医疗、教育、工资、投资等

### 2. 查询记录 (`list`)
- 按月份、类别筛选
- 支持分页

### 3. 删除记录 (`delete`)
- 按记录 ID 删除

### 4. 消费统计 (`report`)
- 按月汇总收支
- 按类别统计占比
- 计算结余
- 输出可视化消费报告

### 5. 月度概览 (`summary`)
- 本月收入、支出、结余
- 本月消费 Top 类别
