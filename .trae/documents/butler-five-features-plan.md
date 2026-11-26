# Butler 五模块功能实施计划

## Context

当前仓库 `/workspace/repo`（Butler v2.0.0）已具备：多引擎语音服务、文档格式转换、带 bbox 的 OCR、dsh/Claude 插件声明式导入、Git 工具集、统一 CLI 与 TUI/Web 多界面。用户希望在此基础上补齐 5 组能力：

| 编号 | 功能 | 核心诉求 |
| :--- | :--- | :--- |
| A | 小说朗读 | 对白停顿与情绪、按文字描述调速、男女多音色区分且不重复念"某某说"、读到哪高亮到哪、重开续读、说清 token 消耗 |
| B | 文档扫描 | 本地图片/拍照 → 电子版；保留彩色笔勾画；铅笔/碳笔素描可转；单页默认 PDF；可继续转多格式 |
| C | 统一 CLI + 命令记录器 | 覆盖全部功能；AI 先查记录器再下命令；命令分类标注；未记录或高频命令自动补录；CLI 与 AI 命令同源 |
| D | dsh 插件适配器 | 不安装 dsh 官方软件，即可从市场/其它渠道装插件并在 Butler 使用 |
| E | Git 式版本管理 | 每次保存建版本点并展示前后 diff；图片/视频同样有版本记录 |

已确认选型：**edge-tts 为主 + pyttsx3 离线兜底**；扫描**轻量本地增强与手写识别都要有**（PaddleOCR 作为可选重依赖，缺失时降级 Tesseract）；版本存储**文本走真实 Git、图片/视频走内置内容寻址快照库**；界面**CLI+后端先行，TUI 与 Web 随后**。

目标结果：五组功能都能通过 `butler <子命令>`、REST `/api/features/<module>/<action>`、TUI 面板与 AI 工具四种入口使用，且行为一致（同一套核心实现）。

---

## 一、总体设计

1. **核心逻辑下沉到 `butler/core/`**，CLI（`butler/cli/*_cmd.py`）、技能（`skills/<name>/main.py` 的 `handle_request`）、TUI、Web、REST 都只做薄适配，避免四份实现漂移。
2. **复用优先**：`GitTools`、`file_converter`、`OcrEngine`、`plugin_bundle`、`VoiceService`、`event_bus` 均已存在，不重写。
3. **零新重依赖**：默认只新增 `edge-tts`（纯 Python、体积小）；PaddleOCR 放入可选 extra。
4. **默认不破坏现状**：新功能全部可配置关闭；保存钩子失败只告警不阻断。

新增共享底座（P0）：

| 文件 | 职责 |
| :--- | :--- |
| `butler/core/artifact_store.py` | 内容寻址存储：`put_file(path)->sha`、`get_path(sha)`、`stat(sha)`；落盘 `data/system_data/artifacts/<sha前2位>/<sha>` |
| `butler/core/version_store.py` | 统一版本门面：`snapshot(path, message, author)`、`list_versions(target)`、`diff(target, rev_a, rev_b)`、`restore(target, rev)`；文本委托 `GitTools`，媒体委托 `ArtifactStore` |
| `butler/core/command_recorder.py` | 命令登记与使用记录：`CommandSpec`、`upsert/get/search/list_by_category`、`track(name, argv, source, success)`、`sync_from_catalog()`、`stats()`、`promote(min_count)` |
| `butler/core/config_model.py`（改） | 新增 `ReadingConfig`、`ScannerConfig`、`VersioningConfig`、`DshConfig`、`CommandsConfig`；`VoiceConfig` 增 TTS 字段 |

SQLite 约定（均放 `data/system_data/`）：

- `command_registry.db`
  - `commands(name PK, aliases, category, purpose, usage, example, risk, source, updated_at)`
  - `usage(id PK, name, argv, argv_hash, source, success, count, last_used_at)`
  - `combos(id PK, name, intent, steps_json, count, updated_at)`
- `version_store.db`
  - `versions(id PK, target, kind, backend, ref, size, message, author, created_at, meta_json)`
- `reading_sessions.db`
  - `sessions(book_hash PK, file_path, segment, offset, profile, updated_at)`

---

## 二、A 小说朗读

新增 `butler/core/reading/`：

| 文件 | 关键内容 |
| :--- | :--- |
| `__init__.py` | 导出 `ReadingService` |
| `script_parser.py` | `parse(text) -> list[Segment]`；`Segment(index, speaker, text, kind, pause_before_ms, rate, emotion_hint)` |
| `voices.py` | 音色池与角色分配：女声 `XiaoxiaoNeural/XiaoyiNeural/XiaohanNeural`，男声 `YunxiNeural/YunyangNeural/YunjianNeural`；旁白默认 `XiaoxiaoNeural`；同角色稳定分配（哈希）并支持 `role-map.json` 覆盖 |
| `tts_edge.py` | `EdgeTTSEngine(VoiceEngine)`：`speak(text, voice, rate, pitch, volume)->bytes`、`list_voices()`；`is_available()` 判断 import + 网络探测（结果缓存）；不可用时由 `VoiceService.get_engine()` 的 native 引擎兜底 |
| `reader.py` | `ReadingService`：`open/play/pause/resume/seek/stop/status`；后台线程按段合成播放；每句 `event_bus.emit("reading.position", {...})`；断点按文件内容 sha256 写入 `reading_sessions.db` |
| `token_budget.py` | `explain(file)`：统计字数、估算可选 LLM 分析 token、说明 TTS 不按 token 计费 |

解析规则（本地、零 token）：

- 对白识别：`“…”`、`「…」`、`『…』`与 `"…"`；紧邻的 `某某说/道/问/答/喊/笑道/低声道` 只用于判定说话人，**不进入朗读文本**（解决"每换一行读一次某某说"）。
- 停顿：`，` 200ms、`；` 350ms、`。！？` 500ms、`……` 800ms、段落 900ms；对白前后各加 150ms。
- 语速：`低声/轻声/悄悄`→0.85，`缓缓/慢慢`→0.80，`大声/喊/吼`→1.15，`飞快/急促`→1.25；叠加全局 `--speed`。
- 音色分配：出场角色按性别词表与常见人名映射到男女声池，轮转分配，避免同段两角色同音色。

CLI（`butler/cli/read_cmd.py`）：

```text
butler read <文件> [--resume] [--start N] [--speed 1.0] [--role-map 文件] [--ai] [--dry-run --out 输出.mp3]
butler read voices
butler read explain-tokens <文件>
```

- `--ai`：可选调用 LLM 推断角色/情绪（消耗 token，见第九节），默认关闭。
- `--dry-run --out`：无音频设备环境（CI/服务器）下的验证路径。
- 播放方式：逐段合成、`pygame` 顺序播放，段间用 `time.sleep` 控制停顿，**不引入 pydub/ffmpeg**；导出时按顺序拼接 MP3 字节（文档注明为 best-effort）。

技能与界面：

- `skills/novel_reader/{SKILL.md, main.py}`：`handle_request(action, **kwargs)`，action ∈ `play/pause/resume/stop/status/voices/explain_tokens`。
- TUI：在 `butler/tui/main.py` 视图 id 列表增加 `view-reader` 与对应 `Vertical(id="view-reader")` 区块；正文用 Rich `Text` 逐句渲染，当前句套 `reverse` 样式并自动滚动；底部按钮 播放/暂停/停止 + 语速输入。
- Web：`frontend/src/components/reader.ts`（P4）。

---

## 三、B 文档扫描

新增 `package/document/scanner.py`：

| 函数 | 作用 |
| :--- | :--- |
| `detect_document_quad(img)` | OpenCV 灰度+边缘+轮廓+`approxPolyDP` 找纸张四角；失败返回 `None` 触发手动四角 |
| `warp_perspective(img, quad)` | 透视矫正 |
| `remove_shadow(img)` | 背景估计除法去阴影 |
| `enhance(img, mode)` | `color`（CLAHE+白平衡）、`gray`、`bw`、`pencil`（自适应阈值保留浅笔迹）、`charcoal`（对比拉伸） |
| `preserve_ink(original, enhanced)` | HSV 高饱和掩码提取彩色笔迹，与原图颜色合成回增强底图，保证勾画颜色不被漂白 |
| `scan_images(paths, out_pdf, mode, keep_ink, dpi)` | 多页合并 PDF，PIL `save(..., "PDF", resolution=dpi)`；单页默认 PDF |
| `scan_from_camera(out_pdf, index=0)` | `cv2.VideoCapture` 拍照；无设备/无权限抛出可读错误，CLI 提示改用本地文件 |
| `ocr_text(paths_or_pdf)` | 复用 `package/document/translate_system/ocr.py` 的 `OcrEngine.recognize`（PaddleOCR→pytesseract 已内置优先级） |

复用：`package/document/file_converter.py` 的 `convert_file()` / `images_to_pdf()` 负责后续转 `docx/md/txt/多图`。

CLI（`butler/cli/scan_cmd.py`）：

```text
butler scan <图片...> --out 输出.pdf [--mode color|gray|bw|pencil|charcoal] [--keep-ink] [--dpi 200] [--ocr] [--to md|docx|txt]
butler scan camera --out 输出.pdf [--camera 0]
butler scan convert <文件> --to <格式>
```

技能与界面：`skills/doc_scanner/{SKILL.md, main.py}`；TUI 增 `view-scan`（路径输入 → 模式选择 → 生成）；Web `frontend/src/components/scanner.ts`（P4）。

扫描深度说明（对应"都要有"）：默认 `--mode color --keep-ink` 保留原彩勾画；`--mode pencil/charcoal` 针对铅笔碳笔；`--ocr` 追加文字层（可复制/可搜索）；安装 `scan-ocr` extra 后自动使用 PaddleOCR 尝试手写识别，未安装则 Tesseract 兜底，并明确提示手写准确率有限。

---

## 四、C 命令行与命令记录器

1. `butler/core/command_recorder.py`（见 P0）是三张表的唯一读写入口。
2. `butler/cli/cmd_cmd.py`：

```text
butler cmd list [--category 分类]
butler cmd search <关键词>
butler cmd show <命令名>
butler cmd record <命令名> --purpose ... --usage ... --category ...
butler cmd stats
butler cmd sync                 # 从 command_catalog + 已装技能 + 插件 commands 收口
butler cmd combo add/list
butler cmd promote [--min-count 5]   # 高频/未登记命令补录为正式命令
```

3. **CLI 与 AI 同源**：
   - 所有新命令统一在 `butler/__main__.py` 增加分支（`read/scan/version/cmd/dsh`），并同步登记到 `butler/tui/command_catalog.py` 的 `COMMANDS`（含 `category`、`description`、`usage`、`tags`、`example`）。
   - 技能侧 `skills/command_advisor/{SKILL.md, main.py}` 提供 `lookup(query)` 与 `suggest_combo(intent)`，AI 在执行前先查记录器；查不到时回调 `track()` 记录。
   - 在 Agent 工具执行成功处（`butler/core/agent_runtime/` 内统一执行出口）调用 `track(name, argv, source="ai", success=True)`；CLI 入口调用 `source="cli"`。
   - `promote(min_count)` 把 `usage` 中高频但未登记的命令补进 `commands`，`source="learned"`。

---

## 五、D dsh 插件适配器

新增 `butler/core/dsh_adapter.py`：

- `search_market(keyword, index_urls)`：读取 JSON 索引（`[{name,version,description,source,keywords}]`），多源合并，缓存 `data/system_data/dsh_market_cache.json`；用 `urllib` + 超时，失败返回空并提示。
- `install(source, name, force)`：直接转调现成的 `plugin_bundle.install_plugin()`（已支持本地目录 / zip / tar / git / https / npm pack）。
- `register_commands(marker)`：把插件内 `commands/*.md` 的 frontmatter 转成 `CommandSpec` 写入命令记录器。
- `list_available()/enable(name)/disable(name)`。

新增 `butler/cli/dsh_cmd.py`：

```text
butler dsh search <关键词>
butler dsh install <来源|包名> [--name N] [--force]
butler dsh list | info <名> | enable <名> | disable <名>
```

安全边界（沿用现有设计）：**只用声明式资产**（skills/commands/agents），`.mcp.json`、`hooks`、`dsh_patch` 仅登记展示，不执行；配置 `dsh.allow_hooks` 默认 `false`。技能根目录发现复用 `butler/core/skill_registry.resolve_skill_roots()`。

---

## 六、E Git 式版本管理

`butler/core/version_store.py` 行为：

- 文本文件：若所在目录在 Git 仓库内 → 就地 `git add` + `commit`（复用 `GitTools`）；否则复制到影子仓 `data/system_data/version_repo/files/<绝对路径镜像>` 后提交。两种方式都在 `versions` 表记录 `backend=git|shadow`。
- 图片/视频：`ArtifactStore.put_file()` 存哈希对象，记录尺寸/时长/大小等 `meta_json`；`diff` 输出元信息对比 + 缩略图引用（不做像素级 diff，控制范围）。
- 每次 `snapshot` 写 `versions` 表；`restore` 从 Git 检出或从 ArtifactStore 取回覆盖目标。

自动保存钩子（点状接入，均 `try/except` 包裹，失败只告警）：

| 位置 | 挂钩 |
| :--- | :--- |
| `package/document/TextEditor.py` | `save_text_file`、`save_image_file` |
| `package/document/office_automator.py` | `create_word_document` / `create_excel_report` / `create_pdf` |
| `butler/core/agent_runtime/` 内置 write/edit 工具 | 写盘成功后 |
| `frontend/program/modern_app.py` | 编辑器保存桥接方法 |

CLI（`butler/cli/version_cmd.py`）：

```text
butler version log <目标>
butler version diff <目标> [--from 版本] [--to 版本]
butler version snapshot <目标> [-m 说明]
butler version restore <目标> --rev <版本>
butler version prune [--keep 50]
```

界面：TUI 复用现有 `view-timemachine` 增加"文件版本"页签（版本列表 + diff 文本）；Web 扩展 `frontend/src/components/time_machine_ui.ts` 或新增 `file_versions.ts`。REST 在 `butler/core/api.py:159` 的 handler 映射中新增 `version/reading/scanner/cmd/dsh` 五项。

---

## 七、配置与依赖变更

`config/config.yaml` + `butler/core/config_model.py` 新增：

```yaml
reading:
  backend: edge          # edge | native
  female_voices: [...]
  male_voices: [...]
  default_rate: 1.0
scanner:
  default_mode: color
  keep_ink: true
  pdf_dpi: 200
  ocr_backend: auto      # auto | paddle | tesseract
versioning:
  enabled: true
  text_backend: auto     # auto(就地/影子) | shadow
  max_artifact_mb: 512
  prune_keep: 50
dsh:
  market_index_urls: []
  auto_register_commands: true
  allow_hooks: false
commands:
  auto_record: true
  promote_min_count: 5
```

依赖：

- `requirements.txt` 增 `edge-tts>=6.1`。
- `pyproject.toml` 增可选组 `scan-ocr = ["paddleocr>=2.7", "paddlepaddle>=2.6"]`。
- 其余（opencv-python、Pillow、pytesseract、reportlab、pygame、pyttsx3）均已存在。

---

## 八、Token 消耗说明（回答用户第 3 问）

| 环节 | 是否消耗 LLM token | 说明 |
| :--- | :--- | :--- |
| edge-tts 合成 | 否 | 微软免费神经语音，按请求调用，不接入 LLM 计费 |
| pyttsx3 兜底 | 否 | 本地离线 |
| 对白/停顿/语速解析 | 否 | 纯本地正则与规则 |
| `--ai` 角色情绪推断（可选） | 是 | 仅在显式开启时调用你的 LLM |

可选 LLM 分析估算（中文约 0.7 token/字）：10 万字小说 ≈ 7 万输入 token，输出为角色清单 JSON 约 1–3 千 token；按所用模型单价换算（可用 `butler read explain-tokens <文件>` 现场计算并打印）。默认全本地 = **0 token**。

---

## 九、分阶段实施与验收

| 阶段 | 内容 | 验收命令 |
| :--- | :--- | :--- |
| P0 | artifact_store / version_store / command_recorder / 配置模型 + 单测 | `python -m butler cmd sync && python -m butler cmd stats`；`python -m pytest tests/unit/test_command_recorder.py tests/unit/test_version_store.py -q` |
| P1 | 朗读：解析器 → 音色 → edge TTS → 续读 → CLI/技能 | `python -m butler read voices`；`python -m butler read tests/fixtures/novel.txt --dry-run --out /tmp/a.mp3`；再次执行 `--resume` 校验断点；`pytest tests/unit/test_reading_parser.py -q` |
| P2 | 扫描：矫正/去阴影/增强/保留彩墨/PDF/OCR | `python -m butler scan tests/fixtures/page.jpg --out /tmp/scan.pdf`；`--mode pencil --keep-ink`；`--ocr --to md`；`pytest tests/unit/test_scanner.py -q` |
| P3 | 命令记录器接线（CLI/Agent）+ dsh 适配器 + 版本 CLI 与保存钩子 | `python -m butler dsh search pdf`；`python -m butler dsh install ./plugin.zip --force`；`python -m butler version snapshot README.md -m init && python -m butler version log README.md && python -m butler version diff README.md` |
| P4 | TUI 视图（reader/scan/timemachine）+ Web 组件 + REST 模块 | `python -m butler tui`；`python -m butler api` 后 `curl -s localhost:5001/health`；`ruff check butler package skills`；`pytest tests/unit -q` |

测试新增：`tests/unit/test_artifact_store.py`、`test_version_store.py`、`test_command_recorder.py`、`test_script_parser.py`、`test_scanner.py`（合成图，`tmp_path` 隔离）。

---

## 十、风险与取舍

- **edge-tts 需联网**：无网自动降级 pyttsx3；CI 用 `--dry-run` 落盘验证。
- **无摄像头/权限不足**：`scan camera` 抛可读错误并给出本地文件替代方案。
- **PaddleOCR 体积大、首次下载模型**：独立 extra，默认不装；手写识别准确率有限，需在输出中提示。
- **透视矫正失败**（背景杂乱）：回退为不矫正 + 手动四角参数。
- **版本库膨胀**：媒体走内容寻址去重 + `max_artifact_mb` + `prune_keep`；影子仓只在非 Git 目录产生。
- **两套 FastAPI**（`butler/core/runtime.py` 与 `butler/core/api.py`）端口可能冲突：新 REST 模块只挂 `butler/core/api.py`，Web 优先走 pywebview 桥接。
- **范围控制**：不重构既有语音/文档/插件/Git 模块，只做增量适配；`butler_cli.py`（legacy）不改，新命令只进统一入口 `butler`。
