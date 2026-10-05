#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Butler 翻译 PWA 配套后端（纯 Python 标准库，零新增依赖）。

职责：
  1. 提供 REST 接口，包装只读翻译后端 `package.document.translate_system`
     （TranslationSystem 编排 / OCR / 术语表 / 历史 / 双语导出）；
  2. 直接服务 `frontend/pwa/` 下的 PWA 静态资源（index.html / app.js / sw.js ...）。

启动：
    python3 frontend/pwa/server.py --port 8766

设计说明：
  - 不使用 Flask / FastAPI，仅用 http.server + ThreadingHTTPServer；
  - 翻译后端按需惰性导入，导入失败时 /api/health 给出明确中文原因，前端不白屏；
  - `doc_export`（双语文件导出）可能缺失：用惰性导入探测，
    不存在时 PDF/EPUB 导出返回明确提示，TXT/SRT 由本服务内置双语导出兜底；
  - 所有 API 统一返回 JSON，错误结构为 {"error": "...", ...}。
"""

from __future__ import annotations

import argparse
import base64
import inspect
import json
import mimetypes
import os
import re
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# ---------- 路径 ----------
PWA_DIR = Path(__file__).resolve().parent          # frontend/pwa/
ROOT = PWA_DIR.parent.parent                       # Butler 仓库根目录
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MAX_BODY_BYTES = 32 * 1024 * 1024                  # 请求体上限（32MB，够 PDF/图片）

# 静态资源 MIME 补充（mimetypes 不一定认识这些后缀）
EXTRA_MIME = {
    ".webmanifest": "application/manifest+json",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".html": "text/html; charset=utf-8",
}

# 翻译后端全局单例（惰性加载，线程安全）
_ts_lock = threading.RLock()
_system = None
_system_error = ""


# ============================================================
# 翻译后端加载
# ============================================================

def _apply_env_keys(system) -> None:
    """从环境变量补齐翻译源 API Key（配置文件里没写 key 时）。

    支持：DEEPSEEK_API_KEY / OPENAI_API_KEY / DEEPL_API_KEY /
          BAIDU_TRANSLATE_KEY(appid:secret) / BUTLER_TRANSLATE_API_KEY(通用兜底)
    """
    generic = os.environ.get("BUTLER_TRANSLATE_API_KEY", "").strip()
    for p in system.config.providers:
        if p.api_key:
            continue
        key = ""
        if p.type in ("deepseek",):
            key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        elif p.type in ("openai-compat",):
            key = os.environ.get("OPENAI_API_KEY", "").strip() or os.environ.get(
                "DEEPSEEK_API_KEY", ""
            ).strip()
        elif p.type == "deepl":
            key = os.environ.get("DEEPL_API_KEY", "").strip()
        elif p.type == "baidu":
            key = os.environ.get("BAIDU_TRANSLATE_KEY", "").strip()
        if not key:
            key = generic
        if key:
            p.api_key = key


def get_system():
    """惰性获取全局翻译系统单例；失败时抛 RuntimeError（带中文原因）。"""
    global _system, _system_error
    with _ts_lock:
        if _system is not None:
            return _system
        if _system_error:
            raise RuntimeError(_system_error)
        try:
            from package.document.translate_system import get_default_system

            _system = get_default_system()
            _apply_env_keys(_system)
            return _system
        except Exception as exc:  # noqa: BLE001
            _system_error = f"翻译后端加载失败：{exc}"
            raise RuntimeError(_system_error) from exc


def _load_doc_export():
    """惰性导入双语导出模块。返回 (module | None, 错误说明)。

    优先使用后端 package.document.translate_system.doc_export（任务约定的
    双语导出入口）；后端缺失时降级 frontend/pwa/doc_export.py
    （本服务配套实现，纯标准库）。
    """
    try:
        from package.document.translate_system import doc_export  # noqa: F401

        return doc_export, ""
    except ImportError:
        pass
    except Exception as exc:  # noqa: BLE001
        return None, f"后端 doc_export 导入失败：{exc}"
    try:
        import doc_export  # frontend/pwa/doc_export.py（与本文件同目录）

        return doc_export, ""
    except ImportError:
        return None, "package 与 frontend/pwa 均未提供 doc_export 模块"
    except Exception as exc:  # noqa: BLE001
        return None, f"doc_export 模块导入失败：{exc}"


def _load_local_doc_export():
    """仅导入 frontend/pwa/doc_export.py（内置降级导出）。"""
    try:
        import doc_export

        return doc_export
    except Exception:  # noqa: BLE001
        return None


# ============================================================
# 小工具
# ============================================================

def split_paragraphs(text: str):
    """按空行切段；整段无空行时退化为按单行切（适配 OCR 结果）。"""
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(parts) == 1 and "\n" in parts[0]:
        parts = [p.strip() for p in parts[0].split("\n") if p.strip()]
    return parts


def decode_data_uri(data: str) -> bytes:
    """解码 base64（允许 data:image/png;base64, 前缀）。"""
    data = (data or "").strip()
    if data.startswith("data:") and "," in data:
        data = data.split(",", 1)[1]
    return base64.b64decode(data)


def guess_format(filename: str, fmt: str | None) -> str:
    ext = (os.path.splitext(filename or "")[1] or "").lstrip(".").lower()
    fmt = (fmt or "").strip().lower()
    if fmt and fmt != "auto":
        return fmt
    return ext or "txt"


# ============================================================
# API 实现
# ============================================================

def api_health():
    system_state = "ok"
    providers = []
    active = ""
    try:
        system = get_system()
        active = system.config.active_provider_id
        for p in system.config.providers:
            providers.append(
                {
                    "id": p.id,
                    "type": p.type,
                    "name": p.name,
                    "enabled": p.enabled,
                    "api_key_set": bool(p.api_key),
                    "model": p.model,
                }
            )
    except Exception as exc:  # noqa: BLE001
        system_state = str(exc)

    ocr_state = {"available": False, "engine": None, "error": ""}
    try:
        from package.document.translate_system.ocr import OCRUnavailable, ocr_engine

        try:
            ocr_state["available"] = True
            ocr_state["engine"] = ocr_engine.kind
        except OCRUnavailable as exc:
            ocr_state["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        ocr_state["error"] = f"OCR 组件导入失败：{exc}"

    doc_mod, doc_err = _load_doc_export()

    return {
        "status": "ok" if system_state == "ok" else "degraded",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "translate_system": system_state,
        "providers": providers,
        "active_provider": active,
        "ocr": ocr_state,
        "doc_export": {"available": doc_mod is not None, "error": doc_err},
    }


def api_languages():
    from package.document.translate_system.languages import LANGUAGES

    return {"languages": LANGUAGES}


def api_providers_get():
    system = get_system()
    items = []
    for p in system.config.providers:
        items.append(
            {
                "id": p.id,
                "type": p.type,
                "name": p.name,
                "enabled": p.enabled,
                "api_key_set": bool(p.api_key),
                "endpoint": p.endpoint,
                "model": p.model,
            }
        )
    return {
        "providers": items,
        "active": system.config.active_provider_id,
        "fallback_chain": list(system.config.fallback_chain),
    }


def api_providers_post(body: dict):
    """更新翻译源配置 / 切换默认翻译源。

    - {id, api_key?, endpoint?, model?, enabled?} → 更新字段
    - {id}（无更新字段）或 {id, select:true}      → 切换默认翻译源
    """
    pid = (body.get("id") or "").strip()
    if not pid:
        raise ValueError("缺少 id")
    system = get_system()
    provider = system.config.get_provider(pid)
    if provider is None:
        raise ValueError(f"未找到翻译源：{pid}")

    update_keys = [k for k in ("api_key", "endpoint", "model", "enabled") if k in body]
    if update_keys:
        for k in update_keys:
            setattr(provider, k, body[k])
        system.reload_providers()
    if body.get("select") is True or not update_keys:
        system.set_active_provider(pid)
    return api_providers_get()


def api_translate(body: dict):
    system = get_system()
    to = (body.get("to") or "").strip() or None
    from_lang = (body.get("from") or body.get("from_lang") or "auto").strip() or "auto"

    texts = body.get("texts")
    if not isinstance(texts, list):
        texts = split_paragraphs(str(body.get("text") or ""))
    texts = [str(t) for t in texts if str(t).strip()]
    if not texts:
        raise ValueError("文本为空，没有可翻译的内容")

    with _ts_lock:
        translations = system.translate_batch(texts, to=to, from_lang=from_lang)

    segments = [{"source": s, "target": t} for s, t in zip(texts, translations)]
    return {
        "translated": "\n\n".join(translations),
        "segments": segments,
        "to": to or system.config.target_lang,
        "from": from_lang,
        "provider": system.config.active_provider_id,
        "count": len(segments),
    }


def api_ocr(body: dict):
    image = body.get("image_base64") or body.get("image") or ""
    if not str(image).strip():
        raise ValueError("缺少 image_base64")
    try:
        from package.document.translate_system.ocr import OCRUnavailable, ocr_engine
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"OCR 组件导入失败：{exc}") from exc

    try:
        result = ocr_engine.recognize_base64(str(image))
    except OCRUnavailable as exc:
        raise RuntimeError(f"OCR 不可用：{exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"图片识别失败：{exc}") from exc

    text = (result.text or "").strip()
    return {
        "text": text,
        "confidence": round(float(result.confidence or 0.0), 3),
        "words": len(result.words or []),
        "engine": ocr_engine.kind,
    }


# ---------- 双语导出 ----------

def _bilingual_plain(text: str, system, to, from_lang) -> str:
    """纯文本双语导出：段落交错（原文一段 / 译文一段）。"""
    paras = split_paragraphs(text)
    with _ts_lock:
        translations = system.translate_batch(paras, to=to, from_lang=from_lang)
    out = []
    for src, tgt in zip(paras, translations):
        out.append(src)
        out.append(tgt)
    return "\n\n".join(out)


def _bilingual_srt(srt_text: str, system, to, from_lang) -> str:
    """SRT 双语导出：每条字幕块内先原文行、后译文行，时间轴保持不变。"""
    blocks = re.split(r"\n\s*\n", srt_text.replace("\r\n", "\n").strip())
    cues = []
    for block in blocks:
        lines = [ln for ln in block.split("\n")]
        if not lines:
            continue
        idx_line = lines[0].strip()
        pos = 0
        if re.match(r"^\d+$", idx_line):
            pos = 1
        if pos >= len(lines) or "-->" not in lines[pos]:
            # 非标准块：整体当作纯文本处理
            cues.append({"index": str(len(cues) + 1), "ts": "", "text": block.strip()})
            continue
        cues.append(
            {
                "index": idx_line if pos == 1 else str(len(cues) + 1),
                "ts": lines[pos].strip(),
                "text": "\n".join(lines[pos + 1:]).strip(),
            }
        )

    texts = [c["text"] for c in cues if c["text"]]
    with _ts_lock:
        translations = system.translate_batch(texts, to=to, from_lang=from_lang) if texts else []
    ti = 0
    out_blocks = []
    for cue in cues:
        if not cue["text"]:
            tgt = ""
        else:
            tgt = translations[ti] if ti < len(translations) else ""
            ti += 1
        body = cue["text"] + ("\n" + tgt if tgt else "")
        parts = [cue["index"]]
        if cue["ts"]:
            parts.append(cue["ts"])
        parts.append(body)
        out_blocks.append("\n".join(parts))
    return "\n\n".join(out_blocks) + "\n"


def _try_doc_export(mod, input_path: Path, output_path: Path, to: str, fmt: str):
    """尝试调用 doc_export 模块的导出入口（兼容多种命名）。

    找不到可调用入口时返回 None，由调用方给出明确提示。
    返回值可能是输出路径（str/Path）或文件字节（bytes）或 None（已写好文件）。
    """
    alias = {
        "input": ["input_path", "input_file", "src_file", "source_file", "path", "file", "src"],
        "output": ["output_path", "output_file", "out_file", "dest_file", "dest", "out"],
        "to": ["to", "target_lang", "lang", "target"],
        "fmt": ["fmt", "format", "output_format", "out_format", "file_format"],
    }
    for name in (
        "export_bilingual_file",
        "export_bilingual",
        "export_file",
        "export_document",
        "export",
    ):
        fn = getattr(mod, name, None)
        if not callable(fn):
            continue
        try:
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            params = {}
        kwargs = {}
        for group, value in (
            ("input", str(input_path)),
            ("output", str(output_path)),
            ("to", to),
            ("fmt", fmt),
        ):
            for candidate in alias[group]:
                if candidate in params:
                    kwargs[candidate] = value
                    break
        try:
            return fn(**kwargs)
        except TypeError:
            try:
                return fn(str(input_path), str(output_path))
            except TypeError:
                continue
    return None


def api_export(body: dict):
    raw = body.get("file_base64") or body.get("file") or ""
    filename = str(body.get("filename") or "document.txt")
    to = (body.get("to") or "").strip() or None
    from_lang = (body.get("from") or "auto").strip() or "auto"
    fmt = guess_format(filename, body.get("format"))
    if not str(raw).strip():
        raise ValueError("缺少 file_base64")

    try:
        data = decode_data_uri(str(raw))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"文件 base64 解码失败：{exc}") from exc
    if not data:
        raise ValueError("文件内容为空")

    system = get_system()
    stem = os.path.splitext(os.path.basename(filename))[0] or "document"

    import tempfile

    with tempfile.TemporaryDirectory(prefix="butler_pwa_export_") as tmp:
        tmpdir = Path(tmp)
        in_path = tmpdir / ("input." + fmt)
        out_path = tmpdir / (stem + ".bilingual." + fmt)
        in_path.write_bytes(data)

        doc_mod, doc_err = _load_doc_export()
        force_fallback = str(body.get("engine") or "").strip().lower() == "fallback"
        candidates = []
        if doc_mod is not None and not force_fallback:
            candidates.append(("doc_export", doc_mod))
        local_mod = _load_local_doc_export()
        if local_mod is not None and local_mod is not doc_mod:
            candidates.append(("pwa-doc-export", local_mod))

        last_err = None
        for engine_name, mod in candidates:
            try:
                result = _try_doc_export(mod, in_path, out_path, to or system.config.target_lang, fmt)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                continue
            if isinstance(result, (bytes, bytearray)):
                return _export_response(bytes(result), out_path.name, fmt, engine_name)
            if isinstance(result, (str, Path)) and Path(result).exists():
                out_path = Path(result)
            if out_path.exists() and out_path.stat().st_size > 0:
                return _export_response(out_path.read_bytes(), out_path.name, fmt, engine_name)
        if candidates and not force_fallback:
            # 导出入口是存在的，只是本次调用失败了——把真实原因如实说清楚，
            # 不要误报成“缺函数”，否则用户会往错误的方向排查。
            detail = str(last_err) if last_err else (doc_err or "未知错误")
            hint = ""
            low = detail.lower()
            if "404" in low or "translate/auth" in low or "unreachable" in low:
                hint = "建议：免费翻译源在当前网络不可达，请在设置里改用需 Key 的翻译源（如 DeepSeek）。"
            elif "api key" in low or "401" in low or "unauthorized" in low:
                hint = "建议：请在设置里填写对应翻译源的 API Key。"
            elif "connection" in low or "timeout" in low or "refused" in low:
                hint = "建议：请检查网络或本地模型服务是否已启动。"
            raise RuntimeError(f"双语导出失败：{detail}。{hint}".strip())
        if not candidates:
            raise RuntimeError(
                "doc_export 模块里没找到可调用的导出入口"
                "（期望 export_bilingual / export_bilingual_file 等函数）。"
                f"{doc_err or ''}".strip()
            )

        # ---- doc_export 不可用：TXT / SRT / MD / VTT 由本服务内置兜底 ----
        if fmt not in ("txt", "srt", "md", "vtt", "text"):
            raise RuntimeError(
                f"双语导出模块（doc_export）尚不可用，暂时无法导出 {fmt.upper()}。"
                f"原因：{doc_err or '模块缺失'}。"
                "目前支持 TXT / SRT / MD / VTT 的双语导出兜底，"
                "或等待 doc_export 就绪后重试。"
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("gbk", errors="replace")

        if fmt == "srt":
            out_text = _bilingual_srt(text, system, to, from_lang)
        else:
            out_text = _bilingual_plain(text, system, to, from_lang)

        out_name = f"{stem}.bilingual.{fmt if fmt != 'text' else 'txt'}"
        return _export_response(out_text.encode("utf-8"), out_name, fmt, "pwa-fallback")


def _export_response(payload: bytes, out_name: str, fmt: str, engine: str):
    mime = EXTRA_MIME.get("." + fmt) or mimetypes.guess_type("x." + fmt)[0] or "application/octet-stream"
    if fmt in ("txt", "text", "md"):
        mime = "text/plain; charset=utf-8"
    elif fmt == "srt":
        mime = "application/x-subrip; charset=utf-8"
    return {
        "ok": True,
        "filename": out_name,
        "mime": mime,
        "size": len(payload),
        "engine": engine,
        "file_base64": base64.b64encode(payload).decode("ascii"),
    }


# ---------- 术语表 / 历史 ----------

def api_glossary_get():
    system = get_system()
    terms = system.glossary.all()
    return {"terms": terms, "count": len(terms)}


def api_glossary_post(body: dict):
    system = get_system()
    if isinstance(body.get("terms"), dict):
        items = {str(k): str(v) for k, v in body["terms"].items()}
        if not items:
            raise ValueError("terms 为空")
        system.glossary.add_many(items)
    else:
        source = str(body.get("source") or "").strip()
        target = str(body.get("target") or "").strip()
        if not source or not target:
            raise ValueError("缺少 source / target")
        system.glossary.add(source, target)
    return {"ok": True, "terms": system.glossary.all(), "count": system.glossary.size}


def api_glossary_delete(params: dict, body: dict):
    source = str(params.get("source", [""])[0] or body.get("source") or "").strip()
    if not source:
        raise ValueError("缺少 source")
    system = get_system()
    removed = system.glossary.remove(source)
    return {"ok": removed, "removed": source, "terms": system.glossary.all()}


def api_history_get(params: dict):
    system = get_system()
    limit_raw = params.get("limit", [""])[0]
    limit = int(limit_raw) if str(limit_raw).isdigit() else None
    entries = [e.to_dict() for e in system.get_history(limit)]
    return {"entries": entries, "count": len(entries)}


# ============================================================
# HTTP Handler
# ============================================================

class PwaHandler(BaseHTTPRequestHandler):
    server_version = "ButlerPwa/1.0"
    protocol_version = "HTTP/1.1"

    # ---------- 基础输出 ----------

    def _send(self, status: int, content_type: str, payload: bytes,
              extra_headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, status: int, obj, extra_headers: dict | None = None) -> None:
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(status, "application/json; charset=utf-8", payload, extra_headers)

    def _error(self, status: int, message: str, **extra) -> None:
        body = {"error": message}
        body.update(extra)
        self._json(status, body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise ValueError(f"请求体过大（>{MAX_BODY_BYTES // 1024 // 1024}MB）")
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"请求体不是合法 JSON：{exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return data

    def log_message(self, fmt, *args):  # 精简访问日志
        sys.stderr.write("[pwa] %s %s\n" % (self.address_string(), fmt % args))

    # ---------- 路由 ----------

    def do_OPTIONS(self):  # noqa: N802
        self._send(204, "text/plain; charset=utf-8", b"")

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        try:
            if path == "/api/health":
                self._json(200, api_health())
            elif path == "/api/languages":
                self._json(200, api_languages())
            elif path == "/api/providers":
                self._json(200, api_providers_get())
            elif path == "/api/glossary":
                self._json(200, api_glossary_get())
            elif path == "/api/history":
                self._json(200, api_history_get(params))
            elif path.startswith("/api/"):
                self._error(404, f"未知接口：{path}")
            else:
                self._serve_static(path)
        except Exception as exc:  # noqa: BLE001
            self._handle_api_error(exc)

    def do_POST(self):  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            if path == "/api/translate":
                self._json(200, api_translate(body))
            elif path == "/api/ocr":
                self._json(200, api_ocr(body))
            elif path == "/api/export":
                self._json(200, api_export(body))
            elif path == "/api/glossary":
                self._json(200, api_glossary_post(body))
            elif path == "/api/providers":
                self._json(200, api_providers_post(body))
            elif path.startswith("/api/"):
                self._error(404, f"未知接口：{path}")
            else:
                self._error(404, f"未知路径：{path}")
        except Exception as exc:  # noqa: BLE001
            self._handle_api_error(exc)

    def do_DELETE(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        try:
            body = self._read_json()
            if path == "/api/glossary":
                self._json(200, api_glossary_delete(params, body))
            else:
                self._error(404, f"未知接口：{path}")
        except Exception as exc:  # noqa: BLE001
            self._handle_api_error(exc)

    def _handle_api_error(self, exc: Exception) -> None:
        msg = str(exc) or exc.__class__.__name__
        low = msg.lower()
        if isinstance(exc, ValueError):
            self._error(400, msg)
            return
        if "401" in low or "unauthorized" in low or "api key" in low or "invalid_api_key" in low:
            self._error(
                502,
                f"翻译失败：翻译源未配置或 API Key 无效。请在「设置」里填写 API Key，"
                f"或切换到免费翻译源。原始错误：{msg}",
                error_kind="auth",
            )
            return
        if msg.startswith(("Translation failed", "Batch translation failed", "翻译失败")):
            self._error(
                502,
                f"翻译失败：所有翻译源均不可用。常见原因：① 未配置 API Key；"
                f"② 免费翻译源在当前网络环境不可达。请在「设置」里填写 DeepSeek 等 API Key，"
                f"或切换翻译源后重试。原始错误：{msg}",
                error_kind="translate",
            )
            return
        if "connection" in low or "timed out" in low or "timeout" in low or "name resolution" in low:
            self._error(
                502,
                f"翻译失败：无法连接翻译服务（网络不可达）。请检查服务器网络，"
                f"或切换翻译源后重试。原始错误：{msg}",
                error_kind="network",
            )
            return
        traceback.print_exc()
        self._error(500, msg)

    # ---------- 静态资源 ----------

    def _serve_static(self, path: str) -> None:
        rel = unquote(path.split("?", 1)[0])
        if rel in ("", "/"):
            rel = "/index.html"
        candidate = (PWA_DIR / rel.lstrip("/")).resolve()
        try:
            candidate.relative_to(PWA_DIR.resolve())
        except ValueError:
            self._error(403, "禁止访问该路径")
            return
        if not candidate.is_file():
            self._error(404, f"文件不存在：{rel}")
            return

        ext = candidate.suffix.lower()
        ctype = EXTRA_MIME.get(ext) or mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        payload = candidate.read_bytes()
        cache = "no-cache" if candidate.name in ("index.html", "sw.js", "manifest.webmanifest") else "public, max-age=3600"
        self._send(200, ctype, payload, {"Cache-Control": cache})


# ============================================================
# 入口
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Butler 翻译 PWA 配套后端")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=8766, help="监听端口（默认 8766）")
    args = parser.parse_args()

    try:
        get_system()
        print("[pwa] 翻译后端加载成功")
    except Exception as exc:  # noqa: BLE001
        print(f"[pwa] 警告：翻译后端暂不可用（{exc}），接口将返回明确错误")

    server = ThreadingHTTPServer((args.host, args.port), PwaHandler)
    print(f"[pwa] Butler 翻译 PWA 已启动：http://{args.host}:{args.port}/")
    print(f"[pwa] 静态目录：{PWA_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[pwa] 已停止")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
