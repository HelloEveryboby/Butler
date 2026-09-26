---
name: calculator
description: 全能科学计算器与单位换算器。支持四则运算、幂运算、三角函数、对数、常量，以及长度/重量/温度/数据存储等单位换算。
provides:
  - math.calculate
  - math.convert
requires: {}
risk: low
keywords:
  - 计算
  - 计算器
  - 换算
  - 单位
  - 数学
  - calculator
  - convert
---

# 全能计算器 (Calculator)

本技能提供安全的数学表达式求值与多维度单位换算能力，全程不使用 `eval`，基于 AST 白名单解析，杜绝注入风险。

## 核心能力

### 1. 数学表达式求值 (`calculate`)
- **基础运算**：加 `+`、减 `-`、乘 `*`、除 `/`、取模 `%`、整除 `//`、幂 `**`
- **括号**：支持嵌套括号 `( )`
- **常量**：`pi` (π)、`e` (自然常数)、`tau` (τ)
- **函数**：
  - 三角函数：`sin`, `cos`, `tan`, `asin`, `acos`, `atan` (弧度)
  - 双曲函数：`sinh`, `cosh`, `tanh`
  - 对数：`log` (自然对数)、`log10`、`log2`
  - 其他：`sqrt` (平方根)、`abs` (绝对值)、`round` (四舍五入)、`floor`、`ceil`
- **示例**：
  - `2 + 3 * 4` → `14`
  - `sin(pi/2) + cos(0)` → `2.0`
  - `log(e**3)` → `3.0`
  - `sqrt(16) + 2**3` → `12.0`

### 2. 单位换算 (`convert`)
- **长度**：mm, cm, m, km, inch, foot, yard, mile
- **重量**：mg, g, kg, t, oz, lb
- **温度**：celsius, fahrenheit, kelvin (℃, ℉, K)
- **数据存储**：B, KB, MB, GB, TB, PB (二进制 1024)
- **时间**：ms, s, min, hour, day
- **速度**：m/s, km/h, mph, knot
- **示例**：
  - `100 km to mile`
  - `37 celsius to fahrenheit`
  - `1 GB to MB`
