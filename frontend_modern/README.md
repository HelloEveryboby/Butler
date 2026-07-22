# Butler Frontend

> Butler 智能管家前端 — 基于 Vite + TypeScript 的 Local-First 架构

## 快速开始

### 环境要求

- **Node.js** >= 18 (推荐 20 LTS)
- **npm** >= 9

### 安装

```bash
cd frontend
npm install
```

### 开发

```bash
# 启动开发服务器 (localhost:3000，支持 HMR)
npm run dev

# 启动完整 Butler (需要 Python 后端)
python -m frontend.program.modern_app
```

浏览器直接访问 `http://localhost:3000` 即可进行前端开发，无需 Python 后端（使用 WebBridge mock）。

### 构建

```bash
# 类型检查 + 生产构建
npm run build

# 预览构建产物
npm run preview
```

构建产物输出到 `dist/`，pywebview 会自动加载。

### 代码质量

```bash
# Lint 检查
npm run lint
npm run lint:fix

# 格式化
npm run format
npm run format:check

# 类型检查
npm run typecheck

# 测试
npm run test
npm run test:watch

# 一键检查 (lint + format + test)
npm run check
```

---

## 项目结构

```
frontend/
├── index.html                    # 主入口 HTML (Chat 象限)
├── flash_input.html              # Alt+Space 快捷浮窗入口
├── workflow.html                 # 工作流中心入口
├── vite.config.ts                # Vite 构建配置
├── tsconfig.json                 # TypeScript 配置
├── .eslintrc.cjs                 # ESLint 规则
├── .prettierrc                   # Prettier 格式规则
├── .editorconfig                 # 编辑器统一配置
├── package.json                  # 依赖与脚本
│
├── src/
│   ├── main.ts                   # 应用主入口
│   ├── env.d.ts                  # 全局类型声明
│   │
│   ├── api/                      # 后端通信层
│   │   ├── bridge.ts             # ButlerBridge 接口定义
│   │   ├── bridge-native.ts      # pywebview 原生桥接
│   │   ├── bridge-web.ts         # 浏览器调试 Mock
│   │   └── index.ts              # 自动选择桥接实现
│   │
│   ├── stores/                   # 状态管理
│   │   └── state-matrix.ts       # 全局 UI 状态 (发布-订阅)
│   │
│   ├── components/               # UI 组件
│   │   ├── matrix/               # 2x2 矩阵导航控制器
│   │   ├── chat/                 # 智能对话面板
│   │   └── dag/                  # DAG 可视化编辑器
│   │
│   ├── effects/                  # 视觉效果
│   │   └── physics.ts            # 弹簧物理引擎
│   │
│   ├── utils/                    # 工具函数
│   │   ├── escape.ts             # HTML 转义
│   │   ├── toast.ts              # Toast 通知
│   │   └── dom.ts                # DOM 操作工具
│   │
│   ├── onboarding/               # 新手引导
│   │   └── OnboardingTour.ts
│   │
│   └── styles/                   # 全局样式
│       ├── variables.css         # 设计令牌 (Design Tokens)
│       ├── reset.css             # CSS Reset
│       ├── glassmorphism.css     # 玻璃拟态基础样式
│       ├── animations.css        # 动画关键帧
│       └── global.css            # 全局布局与工具类
│
├── public/                       # 静态资源 (不经过构建)
│   └── assets/
│
└── tests/                        # 测试文件
```

---

## 架构概览

### 核心设计原则

1. **Local-First** — 前端可脱离后端独立开发调试
2. **模块化** — 每个组件独立目录，通过 `index.ts` 导出
3. **类型安全** — TypeScript strict 模式
4. **零运行时依赖** — 纯 TS + DOM，不引入 React/Vue

### Bridge 桥接层

前端通过 `ButlerBridge` 接口与 Python 后端通信：

```
┌─────────────┐     ButlerBridge      ┌─────────────────┐
│   Frontend   │ ◄──────────────────► │  Python Backend  │
│  (TypeScript) │                      │   (pywebview)    │
└─────────────┘                       └─────────────────┘
       │                                      │
       ▼                                      ▼
  WebBridge (mock)                    NativeBridge (real)
  浏览器调试用                         生产环境
```

- **WebBridge** — 模拟 AI 响应，前端可独立开发
- **NativeBridge** — 通过 `window.pywebview.api` 调用 Python

### 状态管理

`StateMatrix` 是全局 UI 状态的单一来源：

```typescript
import { stateMatrix } from '@/stores/state-matrix';

// 读取
const { x, y } = stateMatrix.get('matrix');

// 更新
stateMatrix.update('matrix', { x: 0.5 });

// 订阅
const unsub = stateMatrix.subscribe((state) => { ... });
```

### 2x2 矩阵导航

Butler UI 采用 2x2 多维空间矩阵，通过 `MatrixController` 管理：

| 象限 | 功能 | 快捷键 |
|------|------|--------|
| (0,0) | 智能对话 | Ctrl+←↑ |
| (1,0) | 时光机 | Ctrl+→↑ |
| (0,1) | DAG 画布 | Ctrl+←↓ |
| (1,1) | 技能仓 | Ctrl+→↓ |

---

## 开发指南

### 添加新组件

1. 在 `src/components/` 下创建目录：
   ```
   src/components/my-component/
   ├── MyComponent.ts      # 组件逻辑
   ├── my-component.module.css  # 组件样式 (可选)
   └── index.ts            # 导出
   ```

2. 在 `index.ts` 中导出：
   ```typescript
   export { MyComponent } from './MyComponent';
   ```

3. 在 `main.ts` 中初始化。

### 添加新的全局回调

Python 后端通过 `evaluate_js` 调用前端函数。在 `main.ts` 中注册：

```typescript
window.onNewEvent = (data: unknown) => {
  // 处理逻辑
};
```

同时在 `env.d.ts` 中添加类型声明。

### CSS 变量

所有视觉参数通过 `styles/variables.css` 中的 CSS 变量管理：

```css
/* 使用变量 */
.my-element {
  color: var(--color-accent-blue);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  transition: all var(--transition-normal);
}
```

### 测试

使用 Vitest，测试文件放在 `tests/` 目录：

```typescript
// tests/my-component.test.ts
import { describe, it, expect } from 'vitest';

describe('MyComponent', () => {
  it('should work', () => {
    expect(true).toBe(true);
  });
});
```

---

## 与旧版对照

| 旧版 (v2) | 新版 (v3) | 改进 |
|-----------|----------|------|
| 内联 `<script>` | ES Modules | 模块化、可 tree-shake |
| `window.*` 全局变量 | TypeScript 模块 | 类型安全、无污染 |
| 74KB 单体 CSS | CSS 变量 + 模块化 | 可维护、可复用 |
| 无构建工具 | Vite | HMR、生产优化 |
| 无类型检查 | TypeScript strict | 编译时错误捕获 |
| 无 Lint | ESLint + Prettier | 代码质量保障 |
| 无测试 | Vitest | 回归防护 |
| pywebview 强耦合 | Bridge 抽象层 | 可独立开发 |

---

## 相关文档

- [升级方案详情](./FRONTEND_UPGRADE_PLAN.md)
- [Butler 主仓库](https://github.com/HelloEveryboby/Butler)
- [Butler 架构文档](https://github.com/HelloEveryboby/Butler/blob/main/docs/Butler_Code_Wiki.md)
