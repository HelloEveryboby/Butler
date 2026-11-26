"""BHL 原生加速入口 — 新能力可用 C/C++/Go/Rust 开发并以 Python 兜底。

只有在 ``programs/<name>/manifest.json`` 中注册了同名方法时才会调用原生模块；
没有原生实现时返回 None，调用方继续走 Python 实现。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("HybridAccel")


def try_native(method: str, params: dict[str, Any] | None = None,
               timeout: float | None = None) -> Any | None:
    """尝试调用已注册的原生方法；无原生实现或调用失败返回 None。"""
    try:
        from butler.core.hybrid_hub import hybrid_hub
    except Exception:
        return None

    try:
        if not hybrid_hub.method_index().get(method):
            return None
        envelope = hybrid_hub.call(method, params or {}, timeout=timeout)
        if envelope.get("ok"):
            return envelope.get("result")
    except Exception as exc:
        logger.debug("原生方法 %s 不可用: %s", method, exc)
    return None
