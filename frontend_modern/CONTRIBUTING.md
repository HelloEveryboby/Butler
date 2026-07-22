# 贡献指南

感谢你对 Butler 前端的兴趣。以下是参与开发的规范。

## 开发环境

```bash
# 1. 克隆仓库
git clone https://github.com/HelloEveryboby/Butler.git
cd Butler/frontend

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev
```

浏览器访问 `http://localhost:3000`，前端会自动使用 WebBridge mock，无需 Python 后端。

## 分支规范

- `main` — 稳定版本
- `dev` — 开发分支
- `feature/*` — 功能分支
- `fix/*` — 修复分支

## 代码规范

### TypeScript

- **严格模式**: `tsconfig.json` 中 `strict: true`
- **路径别名**: 使用 `@/` 代替相对路径 (`@/components/chat` 而非 `../../components/chat`)
- **导出**: 每个组件目录通过 `index.ts` 导出公开 API
- **类型**: 优先使用 `interface` 而非 `type`（联合类型除外）

```typescript
// ✅ 好
import { ChatPanel } from '@/components/chat';

// ❌ 避免
import { ChatPanel } from '../../components/chat/ChatPanel';
```

### CSS

- 使用 CSS 变量（定义在 `styles/variables.css`）
- 组件样式使用 CSS Modules (`.module.css`)
- 全局样式只放在 `styles/` 目录

```css
/* ✅ 使用变量 */
.my-element {
  color: var(--color-accent-blue);
  padding: var(--space-4);
}

/* ❌ 硬编码值 */
.my-element {
  color: #007aff;
  padding: 16px;
}
```

### 提交信息

遵循 [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: 添加备忘录搜索功能
fix: 修复矩阵导航触摸事件
docs: 更新架构文档
style: 格式化代码
refactor: 重构 Bridge 接口
test: 添加 StateMatrix 单元测试
chore: 更新依赖版本
```

## 添加新组件

1. 在 `src/components/` 下创建目录
2. 创建主文件、样式文件、`index.ts`
3. 在 `main.ts` 中初始化
4. 如需与后端通信，通过 `bridge` 实例调用

```
src/components/my-feature/
├── MyFeature.ts
├── my-feature.module.css
└── index.ts
```

## 测试

```bash
npm run test          # 运行一次
npm run test:watch    # 监听模式
npm run test:coverage # 覆盖率
```

测试文件放在 `tests/` 目录，命名 `*.test.ts`。

## 提交 PR 前

```bash
npm run check   # lint + format + test 一键检查
```

确保无报错后再提交。
