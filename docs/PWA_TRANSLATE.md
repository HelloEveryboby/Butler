# 移动端翻译 PWA（frontend/pwa）

移动友好的翻译网页版（PWA）：不需要原生 App，手机浏览器打开即可使用，
可「添加到主屏幕」离线使用 UI。纯原生 HTML/CSS/JS 实现，**不引入任何前端框架和 CDN**。

- 前端：`frontend/pwa/index.html` / `app.js` / `styles.css` / `manifest.webmanifest` / `sw.js` / `icon.svg`
- 后端：`frontend/pwa/server.py`（Python **标准库** `http.server`，零新增依赖）
- 双语导出：优先调后端 `package/document.translate_system.doc_export`，
  不可用时降级 `frontend/pwa/doc_export.py`（本服务配套实现，纯标准库 + 项目已有依赖 reportlab）

## 快速开始

```bash
# 1. 启动后端（默认 0.0.0.0:8766，手机需与电脑同一局域网）
python3 frontend/pwa/server.py

# 2. 电脑浏览器：http://127.0.0.1:8766/
#    手机浏览器：http://<电脑IP>:8766/   （可「添加到主屏幕」）
```

无后端时直接双击 `index.html` 也能**打开界面**（file:// 可用），
此时调用会在页面上给出明确的中文错误提示（不会白屏）。

## 功能

| 功能 | 说明 |
|---|---|
| 粘贴文本 → 双语对照 | 主场景：粘贴/输入文本，逐段「原文 + 译文」对照展示，可复制译文（`POST /api/translate`） |
| 拍照 / 选图 → OCR → 双语对照 | `<input capture>` 调用相机或相册，OCR 识别后翻译（`POST /api/ocr`，OCR 引擎 PaddleOCR/pytesseract 可选装） |
| 上传文件 → 双语导出 | PDF / EPUB / SRT / VTT / TXT / Markdown → 双语文件下载（`POST /api/export`） |
| 翻译源切换 | DeepSeek / Google 免费 / 微软免费 / 本地 LLM 等，可设默认与 API Key（`GET|POST /api/providers`） |
| 目标语言切换 | zh-CN / en / ja / ko …（`GET /api/languages`） |
| 术语表编辑 | 查看 / 新增 / 编辑 / 删除术语（`GET|POST|DELETE /api/glossary`） |
| 历史记录 | localStorage 本地保存最近 100 条，可清空；后端另有 `GET /api/history` |
| 离线 UI | Service Worker 缓存静态资源，离线可打开界面；API 不可达时返回明确中文错误 JSON |

## REST API

| 方法 | 路径 | 请求 | 响应 |
|---|---|---|---|
| GET | `/api/health` | — | `{status, translate_system, providers, active_provider, ocr, doc_export}` |
| GET | `/api/languages` | — | `{languages: {...}}` |
| POST | `/api/translate` | `{text, to, from}` | `{translated, segments:[{source,target}], to, from, provider, count}` |
| POST | `/api/ocr` | `{image_base64}`（可带 data: 前缀） | `{text, confidence}` |
| POST | `/api/export` | `{file_base64, filename, to, from, format?, engine?}` | `{filename, format, engine, mime, size, file_base64}` |
| GET | `/api/providers` | — | `{providers, active, fallback_chain}` |
| POST | `/api/providers` | `{id, api_key?, endpoint?, model?, enabled?, select?}` | 同上 |
| GET | `/api/glossary` | — | `{terms, count}` |
| POST | `/api/glossary` | `{source, target}` | `{ok, terms, count}` |
| DELETE | `/api/glossary?source=xxx` | — | `{ok, removed, terms}` |
| GET | `/api/history?limit=50` | — | `{entries}` |

说明：

- `file_base64` 接受纯 base64 或 `data:` URL
- `engine: "fallback"` 强制使用 `frontend/pwa/doc_export.py`（默认优先后端 doc_export）
- `format` 指定导出格式（默认与输入文件扩展名一致）
- 所有接口出错返回 `{"error": "中文可读原因"}`，HTTP 4xx/5xx

## 双语导出（doc_export 链路）

1. **后端**：`package.document.translate_system.doc_export.export_bilingual`
   （任务约定的统一导出入口；PDF/EPUB/SRT/VTT/TXT/MD/HTML）
2. **降级**：`frontend/pwa/doc_export.py`
   - 输入抽取：TXT/MD 直读；SRT/VTT cue 解析；EPUB = zip + HTMLParser；PDF = pypdf → pdfminer.six → `pdftotext` 三选一
   - 输出：TXT/MD 逐段对照、SRT/VTT 每 cue 内双语行、EPUB（纯标准库生成 epub3）、PDF（reportlab 内置中文 CID 字体）
   - 翻译复用 `package.document.translate_system`（同一缓存/术语表/翻译记忆）
3. **内置兜底**：两者都不可用时，TXT/SRT/MD/VTT 由 server.py 内置逻辑生成

## 离线与本地优先

- 翻译源支持「本地 LLM（Ollama / llama.cpp 等 OpenAI 兼容接口）」，
  默认端点 `http://127.0.0.1:11430/v1`，与桌面 translate_hook 共用同一本地推理服务
- `BUTLER_TRANSLATE_API_KEY` 等环境变量可为云端翻译源注入密钥（不配置则用免费源/本地源）
- Service Worker：静态资源缓存优先；`/api/*` 网络优先，失败返回明确 JSON 错误

## 移动端 UI 约定

- 底部导航（翻译 / 拍照 / 文件 / 设置），单列布局，大按钮，触控友好
- 中文界面；`viewport-fit=cover` + `theme-color`，支持 iOS 安全区
- apple-touch-icon 由 `app.js` 在运行时用 canvas 生成（无需额外图片资源）

## 已知限制

- OCR 需要后端安装 PaddleOCR（推荐）或 pytesseract + 系统 tesseract，
  未安装时接口返回明确安装提示（前端不白屏）
- PDF **文本抽取**需要 pypdf / pdfminer.six / poppler（pdftotext）之一；
  纯图片扫描件需先 OCR
- `file://` 直开时 Service Worker 不生效（浏览器限制），API 也需通过 server.py 访问
- EPUB 导出为「文本级」双语重排（新生成的简洁 EPUB3），不保留原书排版/图片
