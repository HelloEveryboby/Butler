# Changelog

本文件记录 Butler 前端的主要变更。

## [3.0.0] - 2026-07-22

### 架构升级

**构建系统**
- 引入 Vite 6 作为构建工具，支持 HMR 热更新
- 多页面应用配置：`index.html` / `flash_input.html` / `workflow.html`
- 路径别名 `@/` 指向 `src/`
- 生产构建启用 Terser 压缩，移除 console/debugger

**TypeScript 迁移**
- 全面迁移至 TypeScript strict 模式
- 新增 `env.d.ts` 全局类型声明（pywebview、CSS Modules、静态资源）
- 所有组件提供完整类型定义

**模块化重构**
- 消除 `window.*` 全局变量污染
- 引入 ES Modules，组件通过 `index.ts` 导出
- 状态管理从全局单例迁移到 `StateMatrix` 类（发布-订阅模式）

**样式工程化**
- 提取 CSS 设计令牌（`variables.css`），统一管理颜色、间距、字体、阴影
- 74KB 单体 CSS 拆分为模块化文件
- 新增玻璃拟态基础组件（面板、卡片、按钮、输入框）
- 新增动画关键帧库
- 支持 `prefers-reduced-motion` 无障碍偏好

**代码质量**
- 新增 ESLint 9 配置
- 新增 Prettier 配置
- 新增 `.editorconfig`
- 新增 Vitest 测试框架

### 新增文件

```
src/
├── api/
│   ├── bridge.ts             # ButlerBridge 接口定义
│   ├── bridge-native.ts      # pywebview 原生桥接
│   ├── bridge-web.ts         # 浏览器调试 Mock
│   └── index.ts              # 自动选择桥接
├── stores/
│   └── state-matrix.ts       # 全局状态管理
├── components/
│   ├── matrix/MatrixController.ts
│   ├── chat/ChatPanel.ts
│   └── dag/DagEngine.ts
├── effects/physics.ts        # 弹簧物理引擎
├── utils/
│   ├── escape.ts
│   ├── toast.ts
│   └── dom.ts
├── onboarding/OnboardingTour.ts
└── styles/
    ├── variables.css
    ├── reset.css
    ├── glassmorphism.css
    ├── animations.css
    └── global.css
```

### 向后兼容

- `window.onAIStream*` 等全局回调名保持不变
- `window.stateMatrix` 仍暴露（过渡期）
- `pywebview.evaluate_js` 调用链路不受影响
- `ModernBridge` (modern_app.py) 无需修改

---

## [2.0.0] - 原始版本

- 单体 HTML (40KB) + 内联 script/style
- 全局变量状态管理
- 无构建工具、无类型检查、无测试
