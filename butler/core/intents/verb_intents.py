# -*- coding: utf-8 -*-
"""动词识别引擎产出的标准意图 handler（本地精确执行）。

由 butler/core/verb_engine.py 识别出规范意图后，经 intent_registry 分发到此。
签名约定与 butler/butler_app.py 的 handler_args 兼容:
    handler(entities=..., jarvis_app=..., programs=...)
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, Optional

from butler.core.intent_dispatcher import register_intent

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CAPTURE_DIR = PROJECT_ROOT / "data" / "captures"


def _capture_screen(scope: str = "fullscreen") -> Path:
    """按范围截取画面并落盘，返回文件路径。

    scope: fullscreen(全屏,含多显示器) / window(主屏) / region(主屏,待精确选区)
    """
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    out = CAPTURE_DIR / f"capture_{time.strftime('%Y%m%d_%H%M%S')}.png"

    try:
        import mss
        import mss.tools

        with mss.mss() as sct:
            monitor = sct.monitors[0] if scope == "fullscreen" else sct.monitors[1]
            shot = sct.grab(monitor)
            mss.tools.to_png(shot.rgb, shot.size, output=str(out))
        return out
    except Exception:
        pass
    try:
        from PIL import ImageGrab

        ImageGrab.grab().save(str(out))
        return out
    except Exception:
        pass
    try:
        import pyautogui

        pyautogui.screenshot(str(out))
        return out
    except Exception as exc:
        raise RuntimeError(f"截屏失败: {exc}")


@register_intent("screen.capture", requires_entities=False)
def handle_screen_capture(entities: Optional[Dict[str, Any]] = None,
                          jarvis_app=None, **kwargs) -> str:
    """截取当前画面（全屏/区域/窗口）。"""
    entities = entities or {}
    scope = str(entities.get("scope", "fullscreen"))
    path = _capture_screen(scope)
    scope_label = {"fullscreen": "全屏", "window": "当前窗口", "region": "区域"}.get(scope, scope)
    note = ""
    if scope in ("window", "region"):
        note = "（当前实现取主显示器画面）"
    return f"已{scope_label}记录当前画面{note}，保存到: {path}"


@register_intent("file.move")
def handle_file_move(entities: Optional[Dict[str, Any]] = None,
                     jarvis_app=None, **kwargs) -> str:
    """移动文件/文件夹到目标位置。"""
    entities = entities or {}
    src = entities.get("path") or entities.get("source")
    dst = entities.get("target")
    if not src or not dst:
        return "请告诉我要移动的文件和目标位置（例：把 report.docx 移动到 D:/docs）。"
    src_path, dst_path = Path(src).expanduser(), Path(dst).expanduser()
    if not src_path.exists():
        return f"找不到源路径: {src_path}"
    if dst_path.is_dir():
        dst_path = dst_path / src_path.name
    try:
        shutil.move(str(src_path), str(dst_path))
    except Exception as exc:
        return f"移动失败: {exc}"
    return f"已移动: {src_path} → {dst_path}"


@register_intent("file.copy")
def handle_file_copy(entities: Optional[Dict[str, Any]] = None,
                     jarvis_app=None, **kwargs) -> str:
    """复制文件/文件夹到目标位置。"""
    entities = entities or {}
    src = entities.get("path") or entities.get("source")
    dst = entities.get("target")
    if not src or not dst:
        return "请给出要复制的文件和目标位置（例：复制 /a/notes.txt 到 /b）。"
    src_path, dst_path = Path(src).expanduser(), Path(dst).expanduser()
    if not src_path.exists():
        return f"找不到源路径: {src_path}"
    if dst_path.is_dir():
        dst_path = dst_path / src_path.name
    try:
        if src_path.is_dir():
            shutil.copytree(str(src_path), str(dst_path))
        else:
            shutil.copy2(str(src_path), str(dst_path))
    except Exception as exc:
        return f"复制失败: {exc}"
    return f"已复制: {src_path} → {dst_path}"


@register_intent("file.rename")
def handle_file_rename(entities: Optional[Dict[str, Any]] = None,
                       jarvis_app=None, **kwargs) -> str:
    """重命名文件/文件夹。"""
    entities = entities or {}
    src = entities.get("path")
    new_name = entities.get("name")
    if not src or not new_name:
        return "请给出文件路径和新名字（例：把 /a/old.txt 改名为 \"new\"）。"
    src_path = Path(src).expanduser()
    if not src_path.exists():
        return f"找不到路径: {src_path}"
    dst_path = src_path.with_name(new_name)
    try:
        src_path.rename(dst_path)
    except Exception as exc:
        return f"重命名失败: {exc}"
    return f"已重命名: {src_path.name} → {dst_path.name}"


@register_intent("file.delete", requires_entities=False)
def handle_file_delete(entities: Optional[Dict[str, Any]] = None,
                       jarvis_app=None, **kwargs) -> str:
    """删除文件/文件夹（破坏性操作，必须显式确认）。"""
    entities = entities or {}
    src = entities.get("path")
    if not src:
        return "请告诉我要删除的文件路径。"
    if not entities.get("confirmed"):
        return f"删除是破坏性操作。确认删除 {src} 吗？回复「确认删除」后执行。"
    try:
        from package.file_system.guard import FileSystemGuard

        success, msg = FileSystemGuard().safe_delete(src)
        return msg if success else f"删除失败: {msg}"
    except Exception:
        import os
        target = Path(src).expanduser()
        if not target.exists():
            return f"找不到路径: {target}"
        if target.is_dir():
            shutil.rmtree(str(target), ignore_errors=True)
        else:
            os.remove(str(target))
        return f"已删除: {target}"


@register_intent("textfile.edit", requires_entities=False)
def handle_textfile_edit(entities: Optional[Dict[str, Any]] = None,
                         jarvis_app=None, **kwargs) -> str:
    """编辑文本文档：写入内容（原文件先备份为 .bak）。"""
    entities = entities or {}
    src = entities.get("path")
    content = entities.get("content")
    if not src or content is None:
        return "请给出文件路径和要写入的内容（例：编辑 notes.txt 写入 \"第一行内容\"）。"
    target = Path(src).expanduser()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.copy2(str(target), str(target) + ".bak")
        target.write_text(str(content), encoding="utf-8")
    except Exception as exc:
        return f"写入失败: {exc}"
    return f"已编辑文本文档: {target}（原文件备份为 {target.name}.bak）"
