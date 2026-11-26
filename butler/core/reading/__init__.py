"""小说朗读子包（惰性导出，避免子模块导入时拉起语音/配置重依赖）。"""

from __future__ import annotations

__all__ = ["ReadingService"]


def __getattr__(name: str):
    if name == "ReadingService":
        from butler.core.reading.reader import ReadingService

        return ReadingService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
