# Butler Translate — 沉浸式双语翻译

> 浏览器网页 + 桌面任意软件，外语 → 中文，全免费。

## 功能清单

### 🟢 核心体验
| # | 功能 | 快捷键 |
|---|------|--------|
| 1 | 网页全文翻译（双语对照/仅译文/悬停） | `Alt+Q` |
| 2 | DOM 智能分段（语义段落识别） | — |
| 3 | 译文注入不破坏原文（可还原） | — |
| 4 | 多翻译源切换（DeepSeek/Google/微软/DeepL/百度/OpenAI兼容/Butler本地） | — |
| 5 | 翻译缓存（相同文本不重复请求） | — |
| 6 | 划词翻译（选中文字弹出翻译气泡） | 自动 |
| 7 | Popup 弹窗（语言/源/模式切换） | 点击图标 |
| 8 | 右键菜单（翻译页面/翻译选中） | 右键 |

### 🟡 体验提升
| # | 功能 | 说明 |
|---|------|------|
| 9 | 页面悬浮球 | 可拖拽，点击翻译/还原，位置记忆 |
| 10 | 视口懒翻译 | IntersectionObserver，只翻译可见区域 |
| 11 | SPA 动态内容翻译 | MutationObserver + 路由拦截 |
| 12 | 渐进式渲染 | 逐段翻译逐段显示，loading 动画 |
| 13 | 站点规则引擎 | 内置主流站点适配规则 |
| 14 | 输入框翻译 | 在输入框打中文，Ctrl+Enter 翻译成目标语言 |
| 15 | 译文样式自定义 | 颜色/字号/主题 |
| 16 | 排除网站列表 | 指定网站不翻译 |
| 17 | 翻译失败重试 | 超时二分重试 + 降级链 |

### 🔴 Butler 独有（差异化）
| # | 功能 | 说明 |
|---|------|------|
| 18 | 视频字幕翻译 | YouTube / B站 / Netflix 实时双语字幕 |
| 19 | 截图翻译 | `Alt+S` 选区截图 → OCR → 翻译（需 Butler 后端） |
| 19 | 剪贴板翻译 | 复制外语自动翻译 |
| 20 | 本地模型翻译 | 通过 BHL 调 Butler 本地 LLM，完全离线 |
| 21 | PDF 本地翻译 | 本地解析 PDF，不走远程服务 |
| 22 | 翻译历史/收藏 | 对接 Butler 记忆库 |
| 23 | 术语表 | 自定义专有名词翻译 |

## 安装

```bash
# 1. 安装依赖
cd frontend/translate
npm install

# 2. 构建
npm run build

# 3. 加载扩展
# Chrome: 打开 chrome://extensions → 开发者模式 → 加载已解压的扩展程序 → 选择 dist/ 目录
# Edge:   打开 edge://extensions → 同上
```

## 开发

```bash
# 开发模式（自动监听文件变化）
npm run dev

# 构建生产版本
npm run build
```

## 翻译源配置

| 翻译源 | 需要 Key | 说明 |
|--------|:--------:|------|
| **DeepSeek（默认）** | ✅ | 与 Butler 主系统一致，默认模型 deepseek-chat |
| Google 免费 | ❌ | 开箱即用，速度快 |
| 微软免费 | ❌ | 开箱即用，质量好 |
| DeepL | ✅ | 中英翻译质量极好 |
| 百度翻译 | ✅ | 需要 appid + secretKey |
| OpenAI 兼容 | ✅ | 支持 GPT/DeepSeek/智谱/豆包/Kimi/Ollama 等 |
| Butler 本地 | ❌ | 通过 WebSocket 调 Butler Python 后端，完全离线 |

在设置页可以：
- 添加多个翻译源
- 切换当前使用的翻译源
- 设置降级链（主源失败自动切换备用源）
- 测试每个翻译源的连通性

## 项目结构

```
translate/
├── manifest.json              # Chrome MV3 清单
├── background/                # 后台 Service Worker
│   ├── service-worker.ts      # 消息路由、API 代理、缓存、右键菜单
│   ├── cache.ts               # LRU + chrome.storage 缓存
│   └── providers/             # 翻译源适配层
│       ├── base.ts            # Provider 基类接口
│       ├── google-free.ts     # Google 免费翻译
│       ├── bing-free.ts       # 微软免费翻译
│       ├── openai-compat.ts   # OpenAI 兼容（DeepSeek/GPT/…）
│       ├── deepl.ts           # DeepL API
│       ├── baidu.ts           # 百度翻译 API
│       ├── butler-bhl.ts      # Butler 本地（WebSocket）
│       └── registry.ts        # Provider 注册表 + 降级链
├── content/                   # 内容脚本（注入网页）
│   ├── index.ts               # 入口
│   ├── content.css            # 样式
│   ├── dom/                   # DOM 处理管线
│   │   ├── walker.ts          # TreeWalker 文本节点遍历
│   │   ├── segmenter.ts       # 段落识别 + 分组
│   │   ├── site-rules.ts      # 站点规则引擎
│   │   └── injector.ts        # 译文注入 + 还原
│   ├── features/              # 翻译功能模块
│   │   ├── full-translate.ts  # 全文翻译
│   │   ├── selection-translate.ts # 划词翻译
│   │   ├── input-translate.ts # 输入框翻译
│   │   ├── clipboard-translate.ts # 剪贴板翻译
│   │   └── screenshot-translate.ts # 截图翻译
│   ├── ui/                    # 页面内 UI
│   │   └── floating-ball.ts   # 悬浮球
│   └── observers/             # DOM 监听器
│       ├── mutation.ts        # SPA 动态内容
│       ├── viewport.ts        # 视口懒翻译
│       └── router.ts          # 路由变化拦截
├── popup/                     # 弹窗控制面板
├── options/                   # 设置页
└── utils/                     # 公共工具
    ├── types.ts               # 类型定义
    ├── config.ts              # 默认配置
    ├── storage.ts             # chrome.storage 封装
    ├── languages.ts           # 语言列表 + 检测
    ├── messaging.ts           # 消息通信
    └── retry.ts               # 超时 + 二分重试
```

## 架构

```
┌─────────────────────────────────────────────────────┐
│  Chrome Extension (Manifest V3)                      │
│                                                     │
│  ┌─────────────┐   ┌──────────────────┐            │
│  │ background/  │◄─►│ content/         │            │
│  │ service-worker│   │ DOM 管线 + 注入  │            │
│  │              │   │ 悬浮球 + 划词     │            │
│  │ · API 代理   │   │ 输入框 + 截图     │            │
│  │ · 缓存       │   └──────────────────┘            │
│  │ · 降级链     │                                    │
│  │ · 右键菜单   │   ┌──────────┐ ┌──────────┐      │
│  └──────┬───────┘   │ popup/   │ │ options/ │      │
│         │           │ 快捷控制  │ │ 完整设置  │      │
│         ▼           └──────────┘ └──────────┘      │
│  ┌──────────────────────────────────┐               │
│  │  翻译源（可切换、可降级）          │               │
│  │  DeepSeek · Google · 微软 · …    │               │
│  └──────────────────────────────────┘               │
└─────────────────────────────────────────────────────┘
         ↕ WebSocket (BHL)
    Butler Python 后端（截图 OCR + 本地模型）
```

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Alt+Q` | 翻译/还原当前页面 |
| `Alt+S` | 截图翻译 |
| `Ctrl+Enter` | 输入框翻译（在任意输入框内） |
| `Esc` | 关闭气泡/取消截图 |
