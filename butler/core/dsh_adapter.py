"""dsh 插件市场适配器 — 无需安装 dsh 官方软件即可搜索/安装/启用插件。

复用 plugin_bundle 的声明式资产导入：只会导入 skills/commands/agents，
不执行 hooks / JS 运行时 / dsh_patch。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from butler.core.command_recorder import CommandSpec, command_recorder
from butler.core.constants import DATA_DIR
from butler.core.plugin_bundle import (
    MARKER_FILE,
    _read_json,
    detect_bundle,
    install_plugin,
    list_plugins,
)

logger = logging.getLogger("DshAdapter")

MARKET_CACHE = DATA_DIR / "system_data" / "dsh_market_cache.json"


def _market_urls(index_urls: list[str] | None = None) -> list[str]:
    if index_urls:
        return list(index_urls)
    try:
        from package.core_utils.config_loader import config_loader

        return list(config_loader.get("dsh.market_index_urls", []) or [])
    except Exception:
        return []


def search_market(
    keyword: str = "", index_urls: list[str] | None = None, timeout: int = 10
) -> list[dict[str, Any]]:
    """从配置的插件市场索引检索；无索引地址时读本地缓存。"""
    urls = _market_urls(index_urls)
    entries: list[dict[str, Any]] = []
    if urls:
        import requests

        for url in urls:
            try:
                data = requests.get(url, timeout=timeout).json()
                if isinstance(data, dict):
                    data = data.get("plugins") or data.get("items") or []
                if isinstance(data, list):
                    entries.extend(item for item in data if isinstance(item, dict))
            except Exception as exc:
                logger.warning("插件市场索引不可用 %s: %s", url, exc)
        try:
            MARKET_CACHE.parent.mkdir(parents=True, exist_ok=True)
            MARKET_CACHE.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    else:
        try:
            entries = json.loads(MARKET_CACHE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            entries = []

    if keyword:
        needle = keyword.lower()
        entries = [
            item for item in entries
            if needle in json.dumps(item, ensure_ascii=False).lower()
        ]
    return entries


def _plugin_dir(name: str) -> Path:
    from butler.core.skill_registry import get_project_root

    return get_project_root() / "plugins" / name


def _parse_markdown_meta(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    try:
        import yaml

        data = yaml.safe_load(match.group(1)) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def register_commands(plugin: dict[str, Any], recorder=None) -> int:
    """把插件内 commands/*.md 登记到命令记录器，返回登记数量。"""
    recorder = recorder or command_recorder
    name = plugin.get("name")
    if not name:
        return 0
    root = _plugin_dir(name)
    assets = plugin.get("assets") or {}
    count = 0
    for item in assets.get("commands", []) or []:
        directory = Path(item)
        if not directory.is_absolute():
            directory = root / item
        if not directory.is_dir():
            continue
        for md_file in sorted(directory.glob("*.md")):
            meta = _parse_markdown_meta(md_file)
            command_name = str(meta.get("name") or md_file.stem)
            recorder.upsert(
                CommandSpec(
                    name=command_name,
                    category=str(meta.get("category") or f"插件:{name}"),
                    purpose=str(meta.get("description") or ""),
                    usage=str(meta.get("usage") or ""),
                    example=str(meta.get("example") or ""),
                    aliases=list(meta.get("aliases") or []),
                    source=f"plugin:{name}",
                )
            )
            count += 1
    return count


def register_all_plugin_commands(recorder=None) -> int:
    total = 0
    for plugin in list_plugins():
        if plugin.get("enabled") is False:
            continue
        total += register_commands(plugin, recorder)
    return total


def install(source: str, name: str | None = None, force: bool = False) -> dict[str, Any]:
    """安装插件并（可选）登记其命令。"""
    marker = install_plugin(source, name=name, force=force)
    auto = True
    try:
        from package.core_utils.config_loader import config_loader

        auto = bool(config_loader.get("dsh.auto_register_commands", True))
    except Exception:
        pass
    if auto:
        register_commands(marker)
    return marker


def set_enabled(name: str, enabled: bool) -> bool:
    """启用/禁用插件（禁用后技能发现会跳过，重启或重载后生效）。"""
    marker_path = _plugin_dir(name) / MARKER_FILE
    marker = _read_json(marker_path)
    if not marker:
        return False
    marker["enabled"] = enabled
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def inspect(source: str) -> dict[str, Any]:
    """预览一个插件来源的声明式资产（不安装）。"""
    path = Path(source).expanduser()
    if path.exists():
        return detect_bundle(path)
    raise FileNotFoundError(f"本地路径不存在: {source}（远程来源请直接 install）")
