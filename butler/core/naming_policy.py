# -*- coding: utf-8 -*-
"""命名策略 —— 中文显示名 → 英文/拼音真实文件名。

用户的原则: 真实文件名保持英文（跨平台/命令行/git 零风险），
中文只作为 Butler 界面里的**显示名**（见 butler/core/alias_store.py）。

    make_real_name("周报.docx")        -> "zhou_bao.docx"   （拼音，有 pypinyin 时）
    make_real_name("项目 Report v2")   -> "project_report_v2"
    make_real_name("！！！")            -> "file_<时间戳>"   （兜底）

只依赖 requirements.txt 里已有的 pypinyin（缺失时自动降级为 ASCII 清洗）。
"""

from __future__ import annotations

import re
import time
from typing import Optional

try:
    from pypinyin import lazy_pinyin
except ImportError:  # 可选依赖
    lazy_pinyin = None

CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def contains_cjk(text: str) -> bool:
    return bool(CJK_RE.search(str(text or "")))


def _split_ext(filename: str) -> tuple[str, str]:
    """拆出 (stem, ext)。"""
    name = str(filename or "")
    if "." in name[1:]:
        stem, ext = name.rsplit(".", 1)
        return stem, "." + ext.lower()
    return name, ""


def _to_ascii_stem(text: str) -> str:
    """中文转拼音、英文转小写蛇形，产出纯 ASCII 主干。"""
    text = str(text or "").strip()
    if not text:
        return ""

    if contains_cjk(text) and lazy_pinyin is not None:
        # 逐段转换：中文段→拼音，非中文段保留
        parts = []
        for seg in re.findall(r"[\u4e00-\u9fff\u3400-\u4dbf]+|[^\u4e00-\u9fff\u3400-\u4dbf]+", text):
            if CJK_RE.search(seg):
                parts.append("_".join(lazy_pinyin(seg)))
            else:
                parts.append(seg)
        text = "_".join(parts)

    stem = text.lower()
    stem = camel_split(stem)
    stem = NON_ALNUM_RE.sub("_", stem).strip("_")
    stem = re.sub(r"_+", "_", stem)
    return stem


def camel_split(text: str) -> str:
    """projectReport -> project report（驼峰断词，便于蛇形化）。"""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)


def make_real_name(display_name: str, ext: str = "",
                   date_suffix: bool = False, max_len: int = 48) -> str:
    """由中文/任意显示名生成安全的真实文件名（英文/拼音，snake_case）。

    display_name 可带扩展名（"周报.docx"），也可用 ext 显式指定。
    """
    stem, auto_ext = _split_ext(display_name)
    ext = (ext or auto_ext).lower()
    if ext and not ext.startswith("."):
        ext = "." + ext

    ascii_stem = _to_ascii_stem(camel_split(stem) if not contains_cjk(stem) else stem)
    if not ascii_stem:
        ascii_stem = f"file_{int(time.time())}"

    if date_suffix:
        ascii_stem = f"{ascii_stem}_{time.strftime('%Y%m%d')}"

    ascii_stem = ascii_stem[:max_len].strip("_")
    return f"{ascii_stem or 'file'}{ext}"


def make_unique_name(directory, display_name: str, ext: str = "",
                     date_suffix: bool = False):
    """生成不与目录内现有文件冲突的真实名（冲突自动追加 _2/_3...）。"""
    from pathlib import Path

    directory = Path(directory)
    base = make_real_name(display_name, ext=ext, date_suffix=date_suffix)
    stem, ext_part = _split_ext(base)
    candidate = base
    counter = 2
    while (directory / candidate).exists():
        candidate = f"{stem}_{counter}{ext_part}"
        counter += 1
        if counter > 9999:
            break
    return candidate
