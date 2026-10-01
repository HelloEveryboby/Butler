"""语言列表与简单语言检测。"""

from __future__ import annotations

import re
from typing import List, Dict


LANGUAGES: List[Dict[str, str]] = [
    {"code": "zh-CN", "name": "中文（简体）", "name_en": "Chinese (Simplified)"},
    {"code": "zh-TW", "name": "中文（繁体）", "name_en": "Chinese (Traditional)"},
    {"code": "en", "name": "英语", "name_en": "English"},
    {"code": "ja", "name": "日语", "name_en": "Japanese"},
    {"code": "ko", "name": "韩语", "name_en": "Korean"},
    {"code": "fr", "name": "法语", "name_en": "French"},
    {"code": "de", "name": "德语", "name_en": "German"},
    {"code": "es", "name": "西班牙语", "name_en": "Spanish"},
    {"code": "pt", "name": "葡萄牙语", "name_en": "Portuguese"},
    {"code": "ru", "name": "俄语", "name_en": "Russian"},
    {"code": "ar", "name": "阿拉伯语", "name_en": "Arabic"},
    {"code": "it", "name": "意大利语", "name_en": "Italian"},
    {"code": "th", "name": "泰语", "name_en": "Thai"},
    {"code": "vi", "name": "越南语", "name_en": "Vietnamese"},
    {"code": "id", "name": "印尼语", "name_en": "Indonesian"},
    {"code": "nl", "name": "荷兰语", "name_en": "Dutch"},
    {"code": "pl", "name": "波兰语", "name_en": "Polish"},
    {"code": "tr", "name": "土耳其语", "name_en": "Turkish"},
]

_CODE_TO_NAME = {lang["code"]: lang["name"] for lang in LANGUAGES}


def lang_name(code: str) -> str:
    return _CODE_TO_NAME.get(code, code)


def detect_language(text: str) -> str:
    """基于 Unicode 区间的简单语言检测。"""
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh-CN"
    if re.search(r"[\u3040-\u309f\u30a0-\u30ff]", text):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    if re.search(r"[\u0600-\u06ff]", text):
        return "ar"
    if re.search(r"[\u0e00-\u0e7f]", text):
        return "th"
    return "en"
