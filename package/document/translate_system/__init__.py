"""Butler 统一翻译系统。

对外暴露 TranslationSystem 以及便捷函数。所有翻译入口（TUI / CLI / 技能 /
Chrome 扩展后端）都应通过本系统完成翻译。
"""

from __future__ import annotations

from typing import Optional

from .config import ProviderConfig, TranslateSystemConfig
from .engine import TranslationSystem
from .glossary import Glossary
from .history import TranslationHistory

__all__ = [
    "TranslationSystem",
    "TranslateSystemConfig",
    "ProviderConfig",
    "Glossary",
    "TranslationHistory",
    "TranslationMemory",
    "Preset",
    "PresetStore",
    "get_default_system",
    "translate_text",
    "translate_bilingual",
    "translate_file",
    "translate_website",
    "export_bilingual",
    "export_bilingual_html",
    "build_context",
]


_default_system: Optional[TranslationSystem] = None


def get_default_system() -> TranslationSystem:
    """获取全局默认翻译系统（懒加载单例）。"""
    global _default_system
    if _default_system is None:
        _default_system = TranslationSystem()
    return _default_system


# ---------- 便捷函数（向后兼容 translators.py） ----------

def translate_text(text: str, to: Optional[str] = None) -> str:
    return get_default_system().translate(text, to=to)


def translate_bilingual(text: str, context: Optional[str] = None,
                        to: Optional[str] = None):
    return get_default_system().translate_bilingual(text, to=to, context=context)


def translate_file(input_file: str, output_file: Optional[str] = None,
                   to: Optional[str] = None) -> str:
    return get_default_system().translate_file(input_file, output_file, to=to)


def translate_website(url: str, to: Optional[str] = None) -> dict:
    return get_default_system().translate_website(url, to=to)


# ---------- 双语导出 / AI 上下文 / 翻译记忆 / 预设（惰性导入） ----------

def __getattr__(name: str):
    """惰性导出重依赖模块的 API，避免无谓的 import 成本。"""
    if name in ("export_bilingual", "export_bilingual_html"):
        from . import doc_export
        return getattr(doc_export, name)
    if name == "build_context":
        from .context import build_context
        return build_context
    if name == "TranslationMemory":
        from .tm import TranslationMemory
        return TranslationMemory
    if name in ("Preset", "PresetStore"):
        from . import presets
        return getattr(presets, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
