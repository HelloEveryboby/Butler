"""保存钩子 — 文件写盘后自动建立版本点。

任何失败都只记日志，不阻断调用方；可通过 versioning.enabled 关闭。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("VersionHooks")


def _enabled() -> bool:
    try:
        from package.core_utils.config_loader import config_loader

        return bool(config_loader.get("versioning.enabled", True))
    except Exception:
        return True


def snapshot_after_save(path: str | Path | None, message: str = "") -> dict[str, Any] | None:
    """为刚保存的文件建立版本点；失败返回 None。"""
    if not path or not _enabled():
        return None
    target = Path(path)
    if not target.is_file():
        return None
    try:
        from butler.core.version_store import version_store

        return version_store.snapshot(
            target, message=message or f"butler: 保存 {target.name}"
        )
    except Exception as exc:
        logger.warning("版本点创建失败 %s: %s", target, exc)
        return None
