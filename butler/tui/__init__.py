# -*- coding: utf-8 -*-
"""Butler TUI - Terminal User Interface for Butler AI Assistant.

惰性导出：仅在真正启动 TUI 时才加载 textual，避免命令目录等纯数据模块
在未安装 textual 的环境下不可用。
"""

from __future__ import annotations

__all__ = ["ButlerTUI", "run_tui"]


def __getattr__(name: str):
    if name in __all__:
        from butler.tui.main import ButlerTUI, run_tui

        return {"ButlerTUI": ButlerTUI, "run_tui": run_tui}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
