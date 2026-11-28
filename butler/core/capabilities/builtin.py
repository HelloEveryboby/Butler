"""五大核心能力的注册与处理器实现。

这里只做薄适配：真正的逻辑位于 ``butler/core/reading``、``package/document``、
``butler/core/version_store``、``butler/core/command_recorder``、``butler/core/dsh_adapter``。
"""

from __future__ import annotations

from typing import Any

from .registry import CapabilityRegistry, CapabilitySpec, capability_registry

# ── 朗读 ──────────────────────────────────────────────────────────

_reading_service = None


def _reading():
    global _reading_service
    if _reading_service is None:
        from butler.core.reading import ReadingService

        _reading_service = ReadingService()
    return _reading_service


def handle_reading(action: str, payload: dict[str, Any]) -> Any:
    service = _reading()
    if action in ("play", "read"):
        source = payload.get("source") or payload.get("file") or payload.get("url")
        text = payload.get("text")
        if text:
            service.open_text(
                text,
                name=payload.get("name", "文本"),
                role_map_path=payload.get("role_map"),
                default_rate=payload.get("rate"),
            )
        elif source:
            service.open(
                source,
                role_map_path=payload.get("role_map"),
                default_rate=payload.get("rate"),
                ai=bool(payload.get("ai")),
            )
        else:
            return {"error": "需要 source（文件/URL）或 text"}
        service.start_background(
            start=payload.get("start"), resume=bool(payload.get("resume"))
        )
        return {"started": True, **service.status()}

    if action == "pause":
        service.pause()
        return {"paused": True}
    if action == "resume":
        service.resume()
        return {"resumed": True}
    if action == "stop":
        service.stop()
        return {"stopped": True}
    if action == "status":
        return service.status()
    if action == "voices":
        from butler.core.reading.tts_edge import EdgeTTSEngine

        return {"voices": EdgeTTSEngine().list_voices()}
    if action in ("explain_tokens", "tokens"):
        from butler.core.reading.token_budget import explain, explain_text

        if payload.get("text"):
            return explain_text(payload["text"], payload.get("name", "文本"))
        if payload.get("source") or payload.get("file"):
            return explain(payload.get("source") or payload.get("file"))
        return {"error": "需要 text 或 source"}
    return {"error": f"未知动作: {action}"}


# ── 文档扫描 ──────────────────────────────────────────────────────


def handle_scanner(action: str, payload: dict[str, Any]) -> Any:
    if action == "scan":
        from package.document.scanner import ocr_text, scan_images

        paths = payload.get("paths") or payload.get("path") or payload.get("images")
        if isinstance(paths, str):
            paths = [paths]
        if not paths:
            return {"error": "需要 paths（图片路径列表）"}
        result = scan_images(
            paths,
            payload.get("out") or payload.get("output") or "scan_output.pdf",
            mode=payload.get("mode", "color"),
            keep_ink=bool(payload.get("keep_ink", True)),
            dpi=int(payload.get("dpi", 200)),
            correct=bool(payload.get("correct", True)),
        )
        if payload.get("ocr"):
            result["text"] = ocr_text(paths)
        return result

    if action == "camera":
        from package.document.scanner import scan_from_camera

        return scan_from_camera(
            payload.get("out") or "scan_camera.pdf",
            index=int(payload.get("camera", 0)),
            mode=payload.get("mode", "color"),
            keep_ink=bool(payload.get("keep_ink", True)),
            dpi=int(payload.get("dpi", 200)),
        )

    if action == "convert":
        from pathlib import Path

        from package.document.file_converter import convert_file

        source = Path(payload.get("path") or payload.get("file") or "")
        target_format = str(payload.get("to", "pdf")).lstrip(".")
        if not source.is_file():
            return {"error": f"文件不存在: {source}"}
        target = source.with_suffix("." + target_format)
        convert_file(str(source), str(target), str(source.parent))
        return {"output": str(target)}

    return {"error": f"未知动作: {action}"}


# ── 版本管理 ──────────────────────────────────────────────────────


def _version_store():
    from butler.core.version_store import version_store

    return version_store


def handle_versioning(action: str, payload: dict[str, Any]) -> Any:
    store = _version_store()
    target = payload.get("path") or payload.get("file")
    if action == "snapshot":
        return store.snapshot(
            target,
            message=str(payload.get("message", "")),
            author=str(payload.get("author", "ai")),
        )
    if action in ("list", "log"):
        if not target:
            return {"error": "需要 path"}
        return {"versions": store.list_versions(target)}
    if action == "diff":
        return {
            "diff": store.diff(
                target,
                payload.get("from") or payload.get("rev_a"),
                payload.get("to") or payload.get("rev_b"),
            )
        }
    if action == "restore":
        rev = payload.get("rev")
        if rev is None:
            return {"error": "需要 rev"}
        return {"restored": store.restore(target, rev)}
    if action == "prune":
        return store.prune(payload.get("keep"))
    return {"error": f"未知动作: {action}"}


# ── 命令记录器 ────────────────────────────────────────────────────


def _recorder():
    from butler.core.command_recorder import command_recorder

    return command_recorder


def handle_commands(action: str, payload: dict[str, Any]) -> Any:
    recorder = _recorder()
    if action in ("lookup", "search"):
        query = str(payload.get("query") or payload.get("q") or "")
        return {
            "query": query,
            "commands": recorder.search(query),
            "combos": recorder.suggest_combo(query),
        }
    if action == "suggest":
        intent = str(payload.get("intent") or "")
        return {
            "intent": intent,
            "combos": recorder.suggest_combo(intent),
            "commands": recorder.search(intent),
        }
    if action == "record":
        name = str(payload.get("name") or "")
        if not name:
            return {"error": "需要 name"}
        argv = payload.get("argv") or []
        if isinstance(argv, str):
            argv = argv.split()
        recorder.track(
            name,
            argv,
            source=str(payload.get("source", "ai")),
            success=bool(payload.get("success", True)),
        )
        return {"recorded": name}
    if action == "stats":
        return recorder.stats()
    if action == "sync":
        return {"synced": recorder.sync_from_catalog()}
    if action == "promote":
        return {"promoted": recorder.promote(payload.get("min_count"))}
    return {"error": f"未知动作: {action}"}


# ── dsh 插件 ─────────────────────────────────────────────────────


def handle_dsh(action: str, payload: dict[str, Any]) -> Any:
    from butler.core.dsh_adapter import inspect, install, search_market, set_enabled
    from butler.core.plugin_bundle import get_plugin, list_plugins

    if action in ("search", "find"):
        keyword = str(payload.get("keyword") or payload.get("query") or "")
        return {"keyword": keyword, "plugins": search_market(keyword)}
    if action in ("install", "add"):
        source = str(payload.get("source") or payload.get("url") or "")
        if not source:
            return {"error": "需要 source（git URL / zip / npm 包名 / 本地目录）"}
        marker = install(source, name=payload.get("name"), force=bool(payload.get("force")))
        return {
            "installed": marker.get("name"),
            "version": marker.get("version"),
            "type": marker.get("type"),
            "assets": {
                kind: len((marker.get("assets") or {}).get(kind) or [])
                for kind in ("skills", "commands", "agents")
            },
        }
    if action in ("list", "ls"):
        return {"plugins": list_plugins()}
    if action == "info":
        name = str(payload.get("name") or "")
        plugin = get_plugin(name) if name else None
        return plugin or {"error": f"未找到插件: {name}"}
    if action in ("enable", "disable"):
        name = str(payload.get("name") or "")
        if not name:
            return {"error": "需要 name"}
        enabled = action == "enable"
        if not set_enabled(name, enabled):
            return {"error": f"未找到插件: {name}"}
        return {action + "d": name}
    if action == "inspect":
        source = str(payload.get("source") or "")
        return inspect(source) if source else {"error": "需要 source"}
    return {"error": f"未知动作: {action}"}


# ── 文档工具 ─────────────────────────────────────────────────────


def _doc_result(result: Any) -> dict[str, Any]:
    if isinstance(result, str) and result.startswith(("Error:", "错误")):
        return {"error": result}
    return {"result": result}


def handle_documents(action: str, payload: dict[str, Any]) -> Any:
    if action == "convert":
        from butler.core.documents.format_convert import handle_request

        entities = {
            "input": payload.get("input") or payload.get("path") or payload.get("file"),
            "from": payload.get("from") or payload.get("from_fmt") or payload.get("from_format"),
            "to": payload.get("to") or payload.get("to_fmt") or payload.get("to_format"),
            "save_to": payload.get("save_to") or payload.get("output"),
            "options": payload.get("options") or {},
        }
        if not entities["input"] or not entities["from"] or not entities["to"]:
            return {"error": "convert 需要 input、from、to"}
        return _doc_result(handle_request("run", entities=entities))

    if action in ("extract_text", "extract_tables", "merge", "split",
                  "create", "metadata", "rotate"):
        from butler.core.documents import pdf

        if action == "merge" and isinstance(payload.get("files"), str):
            payload = {
                **payload,
                "files": [item.strip() for item in payload["files"].split(",") if item.strip()],
            }
        return _doc_result(pdf.handle_request(action, entities=payload))

    if action in ("docx_read", "docx_create", "docx_edit", "docx_metadata", "docx_add_image"):
        from butler.core.documents import docx

        mapping = {
            "docx_read": "read",
            "docx_create": "create",
            "docx_edit": "edit",
            "docx_metadata": "metadata",
            "docx_add_image": "add_image",
        }
        return _doc_result(docx.handle_request(mapping[action], entities=payload))

    if action == "markdown":
        from butler.core.documents.markitdown_app import convert

        path = payload.get("path") or payload.get("file") or payload.get("file_path")
        if not path:
            return {"error": "需要 path"}
        return _doc_result(convert(path))

    if action == "xlsx_recalc":
        from butler.core.documents.xlsx_recalc import handle_request

        return _doc_result(handle_request("recalc", entities=payload))

    if action == "translate":
        text = payload.get("text") or payload.get("input")
        if not text:
            return {"error": "translate 需要 text"}
        from package.document.translate_system import translate_text

        target = payload.get("to") or payload.get("target")
        return {"result": translate_text(str(text), to=target)}

    return {"error": f"未知动作: {action}"}


# ── 语音域 ───────────────────────────────────────────────────────


def handle_audio(action: str, payload: dict[str, Any]) -> Any:
    if action in ("run", "start_bridge"):
        from butler.core.audio.audio_bridge import handle_request

        return {"result": handle_request("run")}

    if action in ("open", "launch"):
        from butler.core.audio.subtitles import handle_request

        return handle_request("open")

    if action == "push_subtitle":
        from butler.core.audio.subtitles import handle_request

        return handle_request(
            "push_subtitle",
            original=payload.get("original", ""),
            translated=payload.get("translated", ""),
            is_final=payload.get("is_final", True),
        )

    if action == "status":
        from butler.core.audio import subtitles

        engine = subtitles._subtitle_engine
        return {
            "running": engine.is_running,
            "source_lang": engine.source_lang,
            "target_lang": engine.target_lang,
            "bilingual": engine.show_bilingual,
        }

    return {"error": f"未知动作: {action}"}


# ── 技能/插件管理 ────────────────────────────────────────────────


def handle_skills_admin(action: str, payload: dict[str, Any]) -> Any:
    if action == "find":
        from butler.core.skills_admin.finder import find

        return find(
            str(payload.get("query") or payload.get("keyword") or ""),
            limit=int(payload.get("limit", 20)),
        )

    if action == "create":
        from butler.core.skills_admin.creator import handle_request

        return _doc_result(
            handle_request(
                "create",
                skill_id=payload.get("skill_id"),
                name=payload.get("name"),
                description=payload.get("description"),
            )
        )

    if action == "sync":
        from butler.core.skills_admin.sync import sync

        return sync()

    return {"error": f"未知动作: {action}"}


# ── 注册 ─────────────────────────────────────────────────────────


def handle_media(action: str, payload: dict[str, Any]) -> Any:
    from butler.core.media.capability import handle_media as _handle

    return _handle(action, payload)


def handle_system(action: str, payload: dict[str, Any]) -> Any:
    from butler.core.system.capability import handle_system as _handle

    return _handle(action, payload)


def handle_network(action: str, payload: dict[str, Any]) -> Any:
    from butler.core.network.capability import handle_network as _handle

    return _handle(action, payload)


_SPECS: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        name="reading",
        title="通用朗读",
        description=(
            "朗读任意文本：文件（txt/md/docx/pdf/epub/xlsx/pptx）、网页、剪贴板或直接文本。"
            "支持多音色区分角色、自动停顿、按描述调速与断点续读。"
        ),
        actions={
            "play": "开始朗读（source 或 text）",
            "pause": "暂停",
            "resume": "继续",
            "stop": "停止",
            "status": "查询当前进度",
            "voices": "列出可用音色",
            "explain_tokens": "估算 token 消耗",
        },
        handler=handle_reading,
        properties={
            "source": {"type": "string", "description": "文件路径或网页 URL"},
            "text": {"type": "string", "description": "直接朗读的文本"},
            "resume": {"type": "boolean", "description": "从上次断点续读"},
            "start": {"type": "integer", "description": "起始片段序号（0 基）"},
            "rate": {"type": "number", "description": "语速倍率，默认 1.0"},
        },
        tags=("朗读", "阅读", "tts"),
    ),
    CapabilitySpec(
        name="scanner",
        title="文档扫描",
        description=(
            "把图片或摄像头拍照转成电子版 PDF：透视矫正、去阴影、保留彩色笔迹，"
            "支持铅笔/碳笔增强，可追加 OCR 文本并转换格式。"
        ),
        actions={
            "scan": "图片转 PDF",
            "camera": "摄像头拍照转 PDF",
            "convert": "转换已生成文件格式",
        },
        handler=handle_scanner,
        properties={
            "paths": {"type": "array", "items": {"type": "string"}, "description": "图片路径列表"},
            "out": {"type": "string", "description": "输出 PDF 路径"},
            "mode": {
                "type": "string",
                "enum": ["color", "gray", "bw", "pencil", "charcoal"],
                "description": "增强模式",
            },
            "keep_ink": {"type": "boolean", "description": "保留彩色笔迹"},
            "dpi": {"type": "integer", "description": "输出 DPI"},
            "ocr": {"type": "boolean", "description": "追加 OCR 文本"},
            "to": {"type": "string", "description": "convert 的目标格式"},
        },
        required=("paths",),
        tags=("扫描", "ocr", "pdf"),
    ),
    CapabilitySpec(
        name="versioning",
        title="文件版本管理",
        description=(
            "Git 式版本管理：文本文件每次保存建立版本点并展示 diff；"
            "图片/视频走内容寻址快照，同样可查看历史与回滚。"
        ),
        actions={
            "snapshot": "建立版本点",
            "list": "查看历史",
            "diff": "对比版本差异",
            "restore": "回滚到指定版本",
            "prune": "清理旧版本",
        },
        handler=handle_versioning,
        properties={
            "path": {"type": "string", "description": "目标文件路径"},
            "message": {"type": "string", "description": "版本说明"},
            "rev": {"type": "string", "description": "回滚目标版本号"},
            "from": {"type": "string", "description": "diff 起始版本"},
            "to": {"type": "string", "description": "diff 结束版本"},
            "keep": {"type": "integer", "description": "保留版本数"},
        },
        required=("path",),
        tags=("版本", "git", "diff"),
    ),
    CapabilitySpec(
        name="commands",
        title="命令记录器",
        description=(
            "查询/登记 Butler 标准命令与组合，记录使用情况，自动补录高频命令；"
            "AI 执行动作前应先查这里，避免臆造命令。"
        ),
        actions={
            "lookup": "按关键词查询标准命令与组合",
            "suggest": "按意图推荐命令组合",
            "record": "记录一次命令使用",
            "stats": "统计命令使用情况",
            "sync": "从命令目录同步",
            "promote": "补录高频命令",
        },
        handler=handle_commands,
        properties={
            "query": {"type": "string", "description": "查询关键词"},
            "intent": {"type": "string", "description": "用户意图"},
            "name": {"type": "string", "description": "命令名"},
            "argv": {"type": "array", "items": {"type": "string"}, "description": "实际参数"},
            "source": {"type": "string", "description": "来源（cli/ai/manual）"},
            "success": {"type": "boolean", "description": "是否成功"},
            "min_count": {"type": "integer", "description": "补录门槛"},
        },
        tags=("命令", "cli", "记录"),
    ),
    CapabilitySpec(
        name="dsh",
        title="dsh 插件市场",
        description=(
            "搜索、安装、启停 dsh / Claude 插件包（git、zip、npm、本地目录），"
            "无需安装 dsh 官方软件；仅加载声明式 skills/commands/agents。"
        ),
        actions={
            "search": "搜索插件市场",
            "install": "安装插件",
            "list": "列出已装插件",
            "info": "查看插件详情",
            "enable": "启用插件",
            "disable": "禁用插件",
            "inspect": "检查插件来源",
        },
        handler=handle_dsh,
        properties={
            "keyword": {"type": "string", "description": "搜索关键词"},
            "source": {"type": "string", "description": "安装来源"},
            "name": {"type": "string", "description": "插件名"},
            "force": {"type": "boolean", "description": "覆盖安装"},
        },
        risk="caution",
        tags=("插件", "dsh", "市场"),
    ),
    CapabilitySpec(
        name="documents",
        title="文档工具",
        description=(
            "文档格式互转与处理：Markdown/HTML/DOCX/EPUB/PDF/图片互转，"
            "PDF 文本与表格提取、合并、拆分、创建、旋转，Word 读写编辑，"
            "任意文件转 Markdown，Excel 公式重算，文本翻译。"
        ),
        actions={
            "convert": "多格式互转（input/from/to，可选 save_to）",
            "extract_text": "提取 PDF 文本",
            "extract_tables": "提取 PDF 表格",
            "merge": "合并多个 PDF",
            "split": "拆分 PDF 每页",
            "create": "创建 PDF（text/output）",
            "metadata": "读取 PDF 元数据",
            "rotate": "旋转 PDF 页面",
            "docx_read": "读取 Word 文本",
            "docx_create": "创建 Word 文档",
            "docx_edit": "替换 Word 文本",
            "markdown": "文件转 Markdown",
            "xlsx_recalc": "重算 Excel 公式",
            "translate": "翻译文本（text，可选 to）",
        },
        handler=handle_documents,
        properties={
            "input": {"type": "string", "description": "输入文件路径或文本"},
            "from": {"type": "string", "description": "源格式，如 MD/HTML/DOCX/PDF"},
            "to": {"type": "string", "description": "目标格式/目标语言"},
            "save_to": {"type": "string", "description": "输出文件路径"},
            "path": {"type": "string", "description": "文件路径"},
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "待合并 PDF 列表",
            },
            "output": {"type": "string", "description": "输出文件路径"},
            "output_dir": {"type": "string", "description": "拆分输出目录"},
            "text": {"type": "string", "description": "文本内容（创建 PDF / 翻译）"},
            "title": {"type": "string", "description": "Word 标题"},
            "content": {"type": "string", "description": "Word 正文"},
            "old_text": {"type": "string", "description": "Word 中被替换文本"},
            "new_text": {"type": "string", "description": "Word 替换后文本"},
            "image_path": {"type": "string", "description": "插入 Word 的图片"},
            "degrees": {"type": "integer", "description": "旋转角度"},
        },
        tags=("文档", "pdf", "docx", "markdown", "excel", "转换"),
    ),
    CapabilitySpec(
        name="audio",
        title="语音域",
        description=(
            "系统音频采集与 FFT 频谱桥接，以及实时双语字幕悬浮窗："
            "启动采集桥、打开字幕窗、推送字幕事件、查询运行状态。"
        ),
        actions={
            "run": "启动系统音频采集桥接",
            "open": "打开 AI 字幕悬浮窗",
            "push_subtitle": "推送一条字幕事件",
            "status": "查询字幕引擎状态",
        },
        handler=handle_audio,
        properties={
            "original": {"type": "string", "description": "原文"},
            "translated": {"type": "string", "description": "译文"},
            "is_final": {"type": "boolean", "description": "是否为最终字幕"},
        },
        tags=("音频", "字幕", "fft", "asr"),
    ),
    CapabilitySpec(
        name="skills_admin",
        title="技能管理",
        description=(
            "技能与插件管理：搜索已发现技能、创建新技能模板并登记到 skills-lock，"
            "查看局域网技能同步状态。"
        ),
        actions={
            "find": "按关键词搜索技能",
            "create": "创建技能模板",
            "sync": "查看局域网同步状态",
        },
        handler=handle_skills_admin,
        properties={
            "query": {"type": "string", "description": "搜索关键词"},
            "limit": {"type": "integer", "description": "返回条数上限"},
            "skill_id": {"type": "string", "description": "新技能 ID"},
            "name": {"type": "string", "description": "技能显示名"},
            "description": {"type": "string", "description": "技能描述"},
        },
        tags=("技能", "插件", "创建", "搜索"),
    ),
    CapabilitySpec(
        name="media",
        title="媒体中心",
        description=(
            "本地视频/音乐播放与媒体库：播放控制、断点续播、库扫描与检索，"
            "图片/视频压缩，以及屏幕截图与录屏。"
        ),
        actions={
            "play": "播放视频/音乐（path 或 id）",
            "pause": "暂停播放",
            "resume": "继续播放",
            "stop": "停止播放",
            "next": "播放下一集",
            "prev": "播放上一集",
            "status": "查询播放器/媒体库状态",
            "list": "列出媒体库（kind=video|music|media）",
            "scan": "扫描媒体库（可指定 dirs）",
            "compress": "压缩图片/视频（path，可选 mode/format/quality）",
            "capture": "截图或录屏（op=full_screenshot|area_screenshot|long_screenshot|start_recording|stop_recording）",
        },
        handler=handle_media,
        properties={
            "kind": {
                "type": "string",
                "enum": ["video", "music", "media"],
                "description": "媒体类型，默认 video",
            },
            "path": {"type": "string", "description": "媒体文件或目录路径"},
            "id": {"type": "string", "description": "媒体库中的视频 ID"},
            "query": {"type": "string", "description": "媒体库搜索关键词"},
            "limit": {"type": "integer", "description": "返回条数上限"},
            "dirs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "scan 的扫描目录",
            },
            "start": {"type": "number", "description": "起始播放秒数"},
            "resume": {"type": "boolean", "description": "是否断点续播"},
            "mode": {"type": "string", "description": "压缩/截图模式"},
            "format": {"type": "string", "description": "压缩目标格式"},
            "quality": {"type": "integer", "description": "压缩质量 1-100"},
            "max_width": {"type": "integer", "description": "压缩最大宽度"},
            "max_height": {"type": "integer", "description": "压缩最大高度"},
            "output": {"type": "string", "description": "压缩输出目录"},
            "op": {"type": "string", "description": "截图/录制操作"},
            "rect": {"type": "object", "description": "区域截图/录制的矩形"},
            "save_path": {"type": "string", "description": "截图/录制保存路径"},
        },
        tags=("媒体", "视频", "音乐", "压缩", "截图", "录屏"),
    ),
    CapabilitySpec(
        name="system",
        title="系统管家",
        description=(
            "系统维护与云盘聚合：安装快照追踪与残留清理、软件深度卸载、垃圾扫描、"
            "7-Zip 压缩归档、多云盘浏览/搜索/转存、安全测试与 SYN 端口扫描。"
        ),
        actions={
            "clean": "清理系统垃圾（dry_run 默认 true）",
            "track": "安装前系统快照",
            "stop_track": "安装后快照并生成差异",
            "execute_clean": "按快照差异执行残留清理",
            "uninstall": "深度卸载软件（dry_run 默认 true）",
            "list_software": "列出已安装软件",
            "scan_leftovers": "扫描指定软件残留（name）",
            "scan_junk": "扫描系统垃圾",
            "archive": "压缩打包（archive_path + targets）",
            "extract": "解压压缩包（archive_path）",
            "list_archive": "列出压缩包内容",
            "preview_archive": "预览压缩包内文件内容（archive_path + file_in_zip，可选 password/max_bytes）",
            "storage": "列出已配置云盘",
            "list_files": "浏览云盘目录（drive/path）",
            "search_files": "搜索云盘文件（query）",
            "transfer": "云盘间转存（src_drive/dst_drive/file_name）",
            "transfer_status": "查询云盘转存任务（task_id）",
            "duplicates": "查找云盘重复文件",
            "audit": "安全测试/审计（module=web|api|llm|cloud|mobile|sdlc，target）",
            "sec_scan": "SYN 端口扫描（target）",
            "system_info": "系统信息快照",
            "top_processes": "进程资源排行（sort_by=cpu|memory）",
        },
        handler=handle_system,
        properties={
            "name": {"type": "string", "description": "软件名"},
            "dry_run": {"type": "boolean", "description": "仅模拟，不实际删除"},
            "categories": {"type": "string", "description": "垃圾类别，逗号分隔"},
            "archive_path": {"type": "string", "description": "压缩包路径"},
            "targets": {
                "type": "array",
                "items": {"type": "string"},
                "description": "待压缩文件/目录",
            },
            "output_dir": {"type": "string", "description": "解压输出目录"},
            "password": {"type": "string", "description": "压缩包密码"},
            "file_in_zip": {"type": "string", "description": "压缩包内的文件路径（用于预览）"},
            "max_bytes": {"type": "integer", "description": "预览内容大小上限（字节），超出则截断"},
            "drive": {"type": "string", "description": "云盘 ID"},
            "path": {"type": "string", "description": "云盘内路径"},
            "query": {"type": "string", "description": "云盘搜索关键词"},
            "src_drive": {"type": "string", "description": "源云盘 ID"},
            "dst_drive": {"type": "string", "description": "目标云盘 ID"},
            "file_name": {"type": "string", "description": "转存文件名"},
            "task_id": {"type": "string", "description": "转存任务 ID"},
            "module": {"type": "string", "description": "安全测试模块"},
            "target": {"type": "string", "description": "扫描/测试目标"},
            "sort_by": {"type": "string", "description": "进程排序字段"},
            "limit": {"type": "integer", "description": "返回条数上限"},
        },
        risk="caution",
        tags=("系统", "清理", "卸载", "压缩", "云盘", "安全"),
    ),
    CapabilitySpec(
        name="network",
        title="网络工具",
        description=(
            "下载与网盘挂载：Aria2 多线程下载（HTTP/FTP/BT/磁力）任务管理、"
            "AList/Rclone 云盘挂载为本地磁盘、媒体链接嗅探。"
        ),
        actions={
            "download": "添加下载任务（url / magnet / torrent）",
            "list": "列出下载任务与速度",
            "pause": "暂停任务（gid）",
            "resume": "恢复任务（gid）",
            "remove": "删除任务（gid）",
            "speed": "查询下载/上传速度",
            "status": "查询 Aria2 运行状态",
            "mount": "挂载网盘到本地磁盘",
            "unmount": "卸载网盘挂载",
            "mount_status": "查询挂载状态",
            "sniff": "媒体链接嗅探状态",
        },
        handler=handle_network,
        properties={
            "url": {"type": "string", "description": "下载链接"},
            "dir": {"type": "string", "description": "下载目录"},
            "name": {"type": "string", "description": "保存文件名"},
            "gid": {"type": "string", "description": "下载任务 GID"},
            "force": {"type": "boolean", "description": "强制删除"},
            "mount_point": {"type": "string", "description": "挂载点目录"},
            "letter": {"type": "string", "description": "Windows 盘符"},
            "webdav_url": {"type": "string", "description": "WebDAV 地址"},
            "username": {"type": "string", "description": "WebDAV 用户名"},
            "password": {"type": "string", "description": "WebDAV 密码"},
        },
        risk="caution",
        tags=("下载", "aria2", "云盘", "挂载", "嗅探"),
    ),
)


def register_builtin_capabilities(registry: CapabilityRegistry | None = None) -> CapabilityRegistry:
    """注册五大核心能力（幂等）。"""
    target = registry or capability_registry
    for spec in _SPECS:
        if target.get(spec.name) is None:
            target.register(spec)
    return target
