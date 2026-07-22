# 开发环境搭建指南

## 前置依赖

| 工具 | 版本 | 用途 |
|------|------|------|
| Node.js | >= 18 (推荐 20 LTS) | 前端构建 |
| npm | >= 9 | 包管理 |
| Python | >= 3.10 | 后端 (可选) |
| Git | >= 2.30 | 版本控制 |

## 快速搭建

### 仅前端开发 (推荐新手)

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000`，使用 WebBridge mock 模式，无需 Python。

### 完整 Butler 环境

```bash
# 1. 克隆仓库
git clone https://github.com/HelloEveryboby/Butler.git
cd Butler

# 2. Python 环境 (推荐 venv)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. 前端依赖
cd frontend
npm install
cd ..

# 4. 构建前端
cd frontend
npm run build
cd ..

# 5. 启动 Butler
python -m frontend.program.modern_app
```

## 开发模式

### 浏览器独立开发 (WebBridge)

```bash
cd frontend
npm run dev
# 访问 http://localhost:3000
```

- AI 命令返回模拟响应
- 工作流数据为 mock 数据
- 文件操作、终端等不可用

### pywebview 联调 (NativeBridge)

```bash
# 终端 1: 启动 Vite 开发服务器
cd frontend
npm run dev

# 终端 2: 启动 Butler (需设置环境变量)
cd frontend
BUTLER_DEV=1 python -m program.modern_app
```

`BUTLER_DEV=1` 让 pywebview 加载 `http://localhost:3000` 而非构建产物。

## 调试技巧

### 浏览器 DevTools

1. 访问 `http://localhost:3000`
2. F12 打开 DevTools
3. Console 中可直接访问模块：

```javascript
// 查看状态
window.stateMatrix.snapshot()

// 模拟 AI 响应
window.onAIStreamStart()
window.onAIStreamChunk('Hello')
window.onAIStreamEnd()
```

### pywebview 调试

pywebview 默认不启用 DevTools。启动时加参数：

```python
# modern_app.py 中
webview.start(debug=True)
```

### Vite HMR

修改任何 `src/` 下的文件，浏览器自动刷新，无需手动重启。

## 常见问题

### Q: `npm install` 报错网络超时

```bash
# 使用国内镜像
npm config set registry https://registry.npmmirror.com
npm install
```

### Q: TypeScript 编译报错

```bash
# 检查类型
npm run typecheck

# 常见原因: 缺少类型声明
npm install -D @types/node
```

### Q: pywebview 加载空白

检查构建产物是否存在：

```bash
ls frontend/dist/index.html
```

如果不存在，先执行 `npm run build`。

### Q: WebBridge mock 数据不够真实

编辑 `src/api/bridge-web.ts` 中的 `getMockSkillData` 方法，添加更多 mock 场景。

## 部署

### 生产构建

```bash
cd frontend
npm run build
```

产物在 `dist/` 目录，pywebview 直接加载 `dist/index.html`。

### Docker

```bash
# 构建镜像
docker build -t butler .

# 运行
docker run -p 5001:5001 butler
```

前端构建产物会被打包到 Docker 镜像中。
