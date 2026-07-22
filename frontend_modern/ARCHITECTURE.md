# Butler 前端架构文档

## 系统总览

Butler 前端是一个纯 TypeScript + DOM 的单页应用，运行在 pywebview 桌面容器中，同时支持浏览器独立调试。

```
┌──────────────────────────────────────────────────┐
│                  pywebview 容器                    │
│  ┌────────────────────────────────────────────┐  │
│  │              Vite 构建产物                   │  │
│  │                                            │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐ │  │
│  │  │  index    │  │  flash   │  │ workflow │ │  │
│  │  │  .html    │  │  .html   │  │  .html   │ │  │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘ │  │
│  │       │              │              │       │  │
│  │       ▼              ▼              ▼       │  │
│  │  ┌──────────────────────────────────────┐  │  │
│  │  │           TypeScript 模块             │  │  │
│  │  │  ┌────────┐ ┌────────┐ ┌──────────┐ │  │  │
│  │  │  │ stores │ │ comps  │ │ effects  │ │  │  │
│  │  │  └───┬────┘ └───┬────┘ └────┬─────┘ │  │  │
│  │  │      │           │           │       │  │  │
│  │  │      ▼           ▼           ▼       │  │  │
│  │  │  ┌──────────────────────────────┐    │  │  │
│  │  │  │        api/bridge.ts         │    │  │  │
│  │  │  └──────────────┬───────────────┘    │  │  │
│  │  └─────────────────┼────────────────────┘  │  │
│  │                    │                        │  │
│  └────────────────────┼────────────────────────┘  │
│                       │                            │
│  ┌────────────────────▼────────────────────────┐  │
│  │        Python ModernBridge (pywebview)       │  │
│  │        modern_app.py → butler.butler_app     │  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## 模块详解

### 1. API 桥接层 (`src/api/`)

**职责**: 前端与 Python 后端的通信抽象。

```
bridge.ts          ← ButlerBridge 接口定义
bridge-native.ts   ← pywebview 实现 (生产)
bridge-web.ts      ← Mock 实现 (开发)
index.ts           ← 自动选择: pywebview ? Native : Web
```

**接口定义** (`ButlerBridge`):

| 方法 | 说明 | 调用链 |
|------|------|--------|
| `handleCommand(cmd)` | 发送用户命令 | → `ModernBridge.handle_command()` |
| `submitFlashCommand(cmd)` | 浮窗命令 | → `ModernBridge.submit_flash_command()` |
| `hideFlash()` | 隐藏浮窗 | → `ModernBridge.hide_flash()` |
| `callSkill(name, method, params)` | 调用技能 | → `ModernBridge.call_skill()` |
| `pauseOutput()` | 暂停 AI 输出 | → `ModernBridge.pause_output()` |
| `openOffice(path)` | 打开文件 | → `ModernBridge.open_office()` |
| `terminalInput(data)` | 终端输入 | → `ModernBridge.terminal_input()` |

**通信机制**:

```
前端 → Python:  window.pywebview.api.xxx()  (直接调用)
Python → 前端:  window.evaluate_js("window.onAIStreamChunk(...)")  (全局回调)
```

### 2. 状态管理 (`src/stores/`)

**职责**: 全局 UI 状态的单一来源 (Single Source of Truth)。

`StateMatrix` 使用发布-订阅模式：

```typescript
// 状态结构
interface StateShape {
  matrix:     { x, y, targetX, targetY, isMoving }
  metrics:    { cpu, memory, disk, network }
  drag:       { isDragging, sourceQuadrant, targetQuadrant, ... }
  wormhole:   { activeGate, pullStrength }
  editor:     { active, filePath }
  timemachine:{ active }
}
```

**数据流**:

```
用户操作 → MatrixController.moveTo()
         → stateMatrix.update('matrix', { targetX, targetY })
         → SpringPhysics.setTarget()
         → requestAnimationFrame 循环
         → stateMatrix.update('matrix', { x, y })
         → 订阅者收到通知
         → DOM 更新
```

### 3. 组件层 (`src/components/`)

每个组件遵循统一结构：

```
component-name/
├── ComponentName.ts    # 逻辑
├── component.module.css # 样式 (可选)
└── index.ts            # 公开导出
```

#### MatrixController

2x2 矩阵导航控制器。

- **输入**: 键盘 (Ctrl+方向键)、触摸滑动、Dock 栏点击
- **处理**: 弹簧物理动画过渡
- **输出**: 状态更新 → DOM transform

#### ChatPanel

智能对话面板 (象限 0,0)。

- 管理消息列表、流式响应、快捷指令
- 通过 Bridge 发送命令到 Python 后端
- 注册 `window.onAIStream*` 全局回调接收响应

#### DagEngine

DAG 可视化编辑器 (象限 0,1)。

- Canvas 2D 渲染
- 节点拖拽、连线绘制
- 支持从技能仓拖放创建节点

### 4. 物理引擎 (`src/effects/`)

`SpringPhysics` — 阻尼弹簧模型：

```
F = -k(x - target) - d·v
```

- **stiffness (k)**: 弹簧刚度，控制响应速度
- **damping (d)**: 阻尼系数，控制振荡衰减
- **半隐式欧拉积分**: 比显式欧拉更稳定

### 5. 样式系统 (`src/styles/`)

```
variables.css      ← 设计令牌 (颜色、间距、字体、阴影)
reset.css          ← 浏览器默认样式归零
glassmorphism.css  ← 玻璃拟态组件 (面板、卡片、按钮、输入框)
animations.css     ← 动画关键帧库
global.css         ← 布局、Dock、Toast、工具类
```

**CSS 变量层级**:

```
:root (variables.css)
  ├── --color-*      颜色系统
  ├── --space-*      间距系统 (4px 基准)
  ├── --radius-*     圆角
  ├── --text-*       字号
  ├── --shadow-*     阴影
  ├── --transition-* 过渡
  ├── --glass-*      玻璃拟态
  └── --z-*          层级
```

### 6. 全局回调注册 (`src/main.ts`)

Python 后端通过 `evaluate_js` 调用的函数：

| 函数名 | 触发时机 | 来源 |
|--------|---------|------|
| `onAIStreamStart()` | AI 开始响应 | `ModernBridge._run_command` |
| `onAIStreamChunk(text)` | 流式文本块 | `ModernBridge.web_ui_print` |
| `onAIStreamEnd()` | AI 响应结束 | `ModernBridge._run_command` |
| `onProgressUpdate(value)` | 进度更新 | `ModernBridge._on_progress_update` |
| `onNotificationPush(event)` | 通知推送 | `ModernBridge._on_notification_push` |
| `onTerminalOutput(output)` | 终端输出 | `ModernBridge.start_terminal` |
| `showToast(title, msg, type)` | Toast 通知 | 多处调用 |

---

## 数据流全景

```
┌─────────────────────────────────────────────────────┐
│                     用户操作                          │
│  键盘输入 / 鼠标点击 / 触摸 / 拖放                    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                  组件层 (components/)                  │
│  MatrixController / ChatPanel / DagEngine             │
│       │                    │                          │
│       ▼                    ▼                          │
│  stateMatrix.update()   bridge.handleCommand()       │
└───────┬────────────────────┬─────────────────────────┘
        │                    │
        ▼                    ▼
┌───────────────┐   ┌────────────────────────────────┐
│  StateMatrix  │   │     Bridge (api/bridge.ts)      │
│  (stores/)    │   │                                │
│       │       │   │  WebBridge (mock) ← 开发环境    │
│       ▼       │   │  NativeBridge     ← 生产环境    │
│  订阅者通知    │   │        │                        │
│       │       │   │        ▼                        │
│       ▼       │   │  pywebview.api → Python         │
│  DOM 更新     │   │        │                        │
└───────────────┘   │        ▼                        │
                    │  ModernBridge (modern_app.py)    │
                    │        │                        │
                    │        ▼                        │
                    │  evaluate_js → 全局回调          │
                    │        │                        │
                    │        ▼                        │
                    │  window.onAIStream*()           │
                    │        │                        │
                    │        ▼                        │
                    │  ChatPanel 接收并渲染            │
                    └────────────────────────────────┘
```

---

## 关键设计决策

### 为什么不用 React/Vue?

Butler 运行在 pywebview 中，DOM 操作简单直接，不需要虚拟 DOM 的开销。纯 TS + DOM 保持了：
- 零运行时依赖
- 构建产物最小化
- 与 pywebview evaluate_js 的天然兼容

### 为什么保留 window.* 全局函数?

Python 后端通过 `evaluate_js("window.onAIStreamChunk(...)")` 调用前端。这是 pywebview 的通信机制，无法绕过。我们在 `main.ts` 中注册这些函数，内部转发到模块系统。

### 为什么用弹簧物理而非 CSS transition?

2x2 矩阵导航需要自然的物理反馈。CSS transition 只能用 ease 曲线，而弹簧物理可以：
- 精确控制刚度和阻尼
- 支持过冲（overshoot）效果
- 与状态系统深度集成
