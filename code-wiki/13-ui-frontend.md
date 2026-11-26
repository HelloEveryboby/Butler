# 13 · UI 与前端

> Butler 提供 4 种界面形态 + 1 个 API 服务形态：Textual TUI、Tkinter 经典 GUI、pywebview 2×2 玻璃拟态 Web UI、PWA，以及 REST API/headless。

## 13.1 界面形态总览

| 形态 | 入口 | 技术 | 文件 |
| :--- | :--- | :--- | :--- |
| **TUI（默认）** | `butler` / `butler tui` | Textual 8.x + Rich | `butler/tui/main.py`（`class ButlerTUI(App)`，`run_tui()`）、`butler/CommandPanel.py` |
| **经典 GUI** | `butler gui` | Tkinter | `butler/gui/config_wizard*.py`、`butler/butler_app_enhanced.py` |
| **现代 Web UI** | `butler web` | pywebview + HTML/CSS/TS | `frontend/program/modern_app.py`（`ModernBridge`）、`frontend/index.html`、`frontend/src/**` |
| **PWA** | 浏览器访问 | Service Worker + Web App Manifest | `frontend/pwa/*` |
| **语言悬浮窗** | `Alt+Space` | HTML/JS | `frontend/flash_input.html`、`frontend/src/flash_input.ts` |
| **REST API** | `butler start` | FastAPI + Uvicorn | `butler/core/api.py` |

## 13.2 TUI（Textual）

`butler/tui/main.py` 是最大的单文件（≈14 万字节），实现完整终端界面：

- `class ButlerTUI(App)`：主应用；`run_tui()` 为入口。
- 组件：`Header/Footer`、`Tabs`、`ListView`、`Tree`、`DataTable`、`Input`、`ProgressBar`、`Markdown` 渲染等。
- 与内核通过 `event_bus` 订阅 `ui_output`，并调用 `Butler.handle_user_command()`。
- 配套：`butler/tui/command_catalog.py`（命令目录）、`os_command_adapter.py`（OS 命令适配）、`linux_parser.py`（Linux 风格命令解析）。
- 非交互终端（无 TTY）会给出明确提示，而不是静默失败。

`butler/CommandPanel.py` 是较早的 Textual 面板实现（`class CommandPanel(App)`），`butler_app._start_tui_panel()` 仍在使用。

## 13.3 经典 GUI（Tkinter）

- `butler/gui/config_wizard.py`：`show_config_wizard_if_needed()`，首次启动缺 Key 时弹出。
- `config_wizard_enhanced.py` / `config_wizard_enhanced_v2.py`：增强配置向导（服务商选择、Key 校验、API 测试）。
- `startup_wizard.py`：启动向导。
- `butler/butler_app_enhanced.py`：负责“向导 → 选择 GUI/Web → 回退”的启动编排。

## 13.4 现代 Web UI：2×2 玻璃拟态矩阵

`frontend/` 采用 **2×2 空间矩阵**，通过 `Ctrl + 方向键` 或双指滑动在四象限间切换：

| 象限 | 功能 | 关键前端模块 |
| :---: | :--- | :--- |
| (0,0) | 智能对话 + 多模态排障（截图激光扫描 OCR、一键修复） | `src/components/screen_capture.ts`、`popup.ts`、`modal.ts` |
| (1,0) | DAG 可视化任务流水线（拖拽、发光贝塞尔连线、弹簧物理） | `src/components/dag_engine.ts`、`effects/physics.ts`、`workflow.html` |
| (0,1) | 全局可观测时光机（时间轴回溯、异常高亮、指标） | `src/components/time_machine_ui.ts`、`telemetry.ts`、`heatmap.ts` |
| (1,1) | 技能抽屉 + 终端 + 备忘录 + 文件浏览器 | `components/skill_ui_loader.ts`、`memos.ts`、`browser.ts`、`slits_editor.ts` |

### 前端工程结构

```text
frontend/
├── index.html               # 主界面（约 60KB 单页）
├── flash_input.html         # Alt+Space 快捷浮窗
├── workflow.html            # DAG 工作流独立页
├── breath_hud.html          # 呼吸灯 HUD
├── program/modern_app.py    # pywebview 宿主 + ModernBridge（暴露 Python API 给 JS）
├── src/
│   ├── main.ts              # 入口：初始化样式、语音、唤醒词、BHL 客户端
│   ├── core/bridge.ts       # pywebview 桥接
│   ├── core/event_bus.ts    # 前端事件总线
│   ├── style.ts / style.css # 动态主题与玻璃拟态
│   ├── ui/glassmorphism.ts  # 毛玻璃/玻璃拟态
│   ├── components/*.ts      # 各功能组件
│   ├── voice/engine.ts      # 语音引擎
│   ├── voice/wake-word.ts   # 唤醒词
│   ├── canvas/ring-visualizer.ts
│   ├── ws/bhl-client.ts     # 与后端 BHL/WS 通信
│   └── config/index.ts
├── pwa/                     # PWA 版本（manifest + sw.js + server.py）
├── translate/               # 浏览器翻译扩展（Webpack + TS，独立工程）
└── download/                # 下载管理前端
```

### 通信方式

- pywebview 的 `js_api`：`ModernBridge` 暴露 Python 方法给 JS 调用。
- `event_bus`：Python 侧事件（`PROGRESS_UPDATE`、`NOTIFICATION_PUSH`、`ui_output`）推送到前端。
- WebSocket：`frontend/src/ws/bhl-client.ts` 与后端通信（Runner/BHL）。

## 13.5 PWA

`frontend/pwa/` 提供可安装的渐进式 Web 应用：
- `manifest.webmanifest`、`sw.js`（离线缓存）、`index.html`、`app.js`、`styles.css`、`server.py`（本地服务）。
- 适合手机端访问 Butler 的 Web 能力。

## 13.6 翻译系统与多语言

- `frontend/translate/`：独立浏览器扩展工程（Webpack + TypeScript），含 `background/content/popup/options`。
- 文档翻译核心在 `package/document/translate_system/`（引擎、翻译记忆 TM、术语表、双语导出 EPUB/PDF/HTML）。
- 相关文档：`docs/PWA_TRANSLATE.md`、`tests/translate_system/`。

## 13.7 UI 安全约定（XSS 防护）

来自 `docs/Butler_Code_Wiki.md` 的开发者规范：
- 前端渲染用户数据（文件名、聊天内容、翻译文本）**严禁使用 `innerHTML`**，必须用 `textContent` / `innerText`。
- 复杂结构用 `document.createElement` 逐步构建，或严格转义。
- `frontend/src/main.ts` 提供全局 `window.escapeHTML()`。

## 13.8 主题与动效

- 主题：`display.theme`（google/light、apple/dark 等），切换时 `event_bus.emit("theme_change")`。
- 动效：弹簧物理（`effects/physics.ts`）、发光连线、呼吸灯（`breathing_lights.js`、`breath_hud.html`）、AirDrop 甩出流转。

## 13.9 相关章节

- 主编排器如何驱动 UI：[04 核心编排器](./04-core-orchestrator.md)
- REST API 与 Runner：[11 运行时服务](./11-runtime-services.md)
- 启动现代 UI：[03 入口与运行模式](./03-entrypoints.md)
