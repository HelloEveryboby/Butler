# Butler 前端安全策略

## 支持的版本

| 版本 | 支持状态 |
|------|---------|
| 3.x  | ✅ 活跃维护 |
| 2.x  | ❌ 已停止维护 |

## 报告漏洞

发现安全问题请通过以下方式报告：

- **GitHub**: [Security Advisories](https://github.com/HelloEveryboby/Butler/security/advisories)
- **邮箱**: error123456ew@outlook.com

请勿在公开 Issue 中披露安全漏洞。

---

## v3 安全加固清单

### 已实施措施

#### 1. CSP (Content Security Policy)

所有 HTML 入口均配置了严格的 CSP meta 标签：

```
default-src 'self';
script-src 'self' 'unsafe-inline';
style-src 'self' 'unsafe-inline';
connect-src 'self' http://localhost:5001 ws://localhost:5001;
object-src 'none';
base-uri 'self';
frame-ancestors 'none';
```

**效果**: 阻止外部脚本注入、禁止 iframe 嵌入、限制连接来源。

#### 2. XSS 防护

- **`escapeHTML()`**: 所有用户输入在渲染前转义
- **Toast 系统**: 改用 `textContent` 而非 `innerHTML`
- **DOM 工具**: `createElement` 使用 DOM API，禁止 attrs 中设置 `innerHTML`
- **技能加载器**: 使用 `textContent` 安全构建列表

#### 3. 输入验证 (`utils/security.ts`)

| 函数 | 用途 |
|------|------|
| `sanitizeCommand()` | 命令长度限制 (10K)、控制字符过滤 |
| `isValidFilePath()` | 路径遍历检测、敏感目录拦截 |
| `isValidSkillName()` | 只允许 `[a-zA-Z_][a-zA-Z0-9_]*` |
| `isValidMethodName()` | 同上 |
| `checkRateLimit()` | 1 秒内最多 5 条命令 |

#### 4. Bridge 层安全 (`bridge-native.ts`)

- 所有方法包装 try-catch，防止崩溃传播
- `callSkill()` 验证技能名和方法名格式
- `openOffice()` 验证文件路径合法性
- `handleCommand()` 对输入进行转义

#### 5. 错误边界 (`utils/error-boundary.ts`)

- 全局 `window.error` 和 `unhandledrejection` 捕获
- 过滤浏览器扩展注入的错误
- 严重错误显示友好 toast，非严重错误静默记录
- 防止应用白屏

#### 6. localStorage 安全封装 (`utils/security.ts`)

- `safeStorage.get()` — 捕获 JSON 解析错误
- `safeStorage.set()` — 捕获 QuotaExceeded 错误
- `safeStorage.remove()` — 安全删除

#### 7. DOM 安全 (`utils/dom.ts`)

- `setStyles()` 阻止 `position:fixed` (防止钓鱼覆盖)
- `createElement()` 禁止通过 attrs 设置 `innerHTML`
- `on()` 返回清理函数防止内存泄漏

#### 8. HTTP 安全头

HTML 入口配置:
- `X-Content-Type-Options: nosniff` — 阻止 MIME 类型嗅探
- `X-Frame-Options: DENY` — 阻止 iframe 嵌入
- `Referrer-Policy: no-referrer` — 不发送 referrer

#### 9. 事件绑定安全

- 移除 HTML 中的 `onclick` 内联事件
- 改用 `addEventListener` 绑定 (main.ts 中)
- 阻止内联事件处理器的注入风险

---

### 已知限制

| 限制 | 说明 | 缓解措施 |
|------|------|---------|
| `unsafe-inline` for scripts | Vite 开发模式需要 | 生产构建后可移除 |
| pywebview evaluate_js | Python 可执行任意 JS | 依赖系统层访问控制 |
| WebBridge mock | 控制台可直接调用 | 仅开发环境使用 |
| 无身份认证 | 前端不做 auth | 依赖 Butler 系统层 |

---

### 安全审计建议

定期执行:

```bash
# npm 依赖漏洞扫描
npm audit

# 生产构建检查
npm run build && ls -la dist/
```

---

## 安全设计原则

1. **本地优先 (Local-First)** — 数据不离开设备
2. **最小权限** — Bridge 只暴露必要方法
3. **纵深防御** — 输入验证 + 输出转义 + CSP 多层防护
4. **安全默认** — 新组件默认使用安全 API
5. **纵深防御** — 每一层都假设其他层可能失效
