"""命令记录器 — 统一登记 Butler 的命令，并记录使用情况供 AI 查询。

三张表（data/system_data/command_registry.db）：
  commands  正式命令目录（分类 / 作用 / 用法 / 示例 / 来源）
  usage     实际使用记录（按 命令+参数 聚合计数）
  combos    常用命令组合

设计目标：AI 动手前先查标准命令，避免臆造参数；未登记或高频命令自动补录。
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from butler.core.constants import DATA_DIR

logger = logging.getLogger("CommandRecorder")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS commands (
    name TEXT PRIMARY KEY,
    category TEXT,
    purpose TEXT,
    usage TEXT,
    example TEXT,
    aliases TEXT,
    risk TEXT,
    source TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    argv TEXT,
    argv_hash TEXT,
    source TEXT,
    success INTEGER,
    count INTEGER DEFAULT 1,
    last_used_at TEXT,
    UNIQUE(name, argv_hash)
);
CREATE TABLE IF NOT EXISTS combos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    intent TEXT,
    steps_json TEXT,
    count INTEGER DEFAULT 1,
    updated_at TEXT
);
"""


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class CommandSpec:
    """一条命令的登记信息。"""

    name: str
    category: str = "未分类"
    purpose: str = ""
    usage: str = ""
    example: str = ""
    aliases: list[str] = field(default_factory=list)
    risk: str = "safe"
    source: str = "manual"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "purpose": self.purpose,
            "usage": self.usage,
            "example": self.example,
            "aliases": list(self.aliases),
            "risk": self.risk,
            "source": self.source,
        }


def _load_catalog_entries() -> list:
    """读取 TUI 命令目录；textual 未安装时直接按文件加载，避开 UI 依赖。"""
    try:
        from butler.tui.command_catalog import COMMANDS

        return list(COMMANDS)
    except Exception:
        pass

    import importlib.util
    import sys

    path = Path(__file__).resolve().parent.parent / "tui" / "command_catalog.py"
    if not path.is_file():
        return []
    spec = importlib.util.spec_from_file_location("_butler_command_catalog", path)
    if not spec or not spec.loader:
        return []
    module = importlib.util.module_from_spec(spec)
    # dataclass 需要模块已注册到 sys.modules，否则找不到 __dict__
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return list(getattr(module, "COMMANDS", []))


class CommandRecorder:
    """命令目录与使用记录的唯一读写入口。"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = (
            Path(db_path) if db_path else DATA_DIR / "system_data" / "command_registry.db"
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        try:
            data["aliases"] = json.loads(data.get("aliases") or "[]")
        except (TypeError, json.JSONDecodeError):
            data["aliases"] = []
        return data

    # ── 目录 ────────────────────────────────────────────────

    def upsert(self, spec: CommandSpec) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO commands
                    (name, category, purpose, usage, example, aliases, risk, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    category=excluded.category,
                    purpose=excluded.purpose,
                    usage=excluded.usage,
                    example=excluded.example,
                    aliases=excluded.aliases,
                    risk=excluded.risk,
                    source=excluded.source,
                    updated_at=excluded.updated_at
                """,
                (
                    spec.name,
                    spec.category,
                    spec.purpose,
                    spec.usage,
                    spec.example,
                    json.dumps(spec.aliases, ensure_ascii=False),
                    spec.risk,
                    spec.source,
                    _now(),
                ),
            )

    def get(self, name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM commands WHERE name = ?", (name,)).fetchone()
        return self._row_to_dict(row) if row else None

    def list_by_category(self, category: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM commands WHERE category = ? ORDER BY name", (category,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM commands ORDER BY category, name"
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def categories(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT category, COUNT(*) AS total FROM commands GROUP BY category"
                " ORDER BY total DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """子串匹配 + 相似度打分；中文可直接用命令名/作用里的词。"""
        query_l = (query or "").strip().lower()
        if not query_l:
            return []
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM commands").fetchall()

        scored: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            data = self._row_to_dict(row)
            haystack = " ".join(
                str(data.get(k) or "")
                for k in ("name", "category", "purpose", "usage", "example", "aliases")
            ).lower()
            score = 0.0
            if query_l in data["name"].lower():
                score += 100
            if query_l in haystack:
                score += 40
            score += SequenceMatcher(None, query_l, data["name"].lower()).ratio() * 30
            if score >= 20:
                scored.append((score, data))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:limit]]

    # ── 使用记录 ────────────────────────────────────────────

    def track(
        self,
        name: str,
        argv: Iterable[str] | None = None,
        source: str = "cli",
        success: bool = True,
    ) -> None:
        """记录一次执行。source: cli | ai | tui | api。"""
        if not name:
            return
        argv_list = [str(a) for a in (argv or [])]
        argv_text = " ".join(argv_list)
        argv_hash = hashlib.sha1(argv_text.encode("utf-8")).hexdigest()[:16]
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id FROM usage WHERE name = ? AND argv_hash = ?",
                    (name, argv_hash),
                ).fetchone()
                if row:
                    conn.execute(
                        """
                        UPDATE usage SET count = count + 1, success = ?, source = ?,
                            last_used_at = ? WHERE id = ?
                        """,
                        (int(success), source, _now(), row["id"]),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO usage
                            (name, argv, argv_hash, source, success, count, last_used_at)
                        VALUES (?, ?, ?, ?, ?, 1, ?)
                        """,
                        (name, argv_text, argv_hash, source, int(success), _now()),
                    )
        except sqlite3.Error as exc:
            logger.warning("记录命令使用失败: %s", exc)

    def usage_stats(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name, SUM(count) AS total, MAX(last_used_at) AS last_used_at
                FROM usage GROUP BY name ORDER BY total DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── 同步与补录 ──────────────────────────────────────────

    def sync_from_catalog(self) -> int:
        """把 TUI 命令目录与已安装插件的命令收口进记录器。"""
        count = 0
        try:
            for entry in _load_catalog_entries():
                self.upsert(
                    CommandSpec(
                        name=entry.name,
                        category=entry.category,
                        purpose=entry.description,
                        usage=entry.usage,
                        example=entry.example,
                        aliases=list(entry.aliases) + list(entry.tags),
                        source="builtin",
                    )
                )
                count += 1
        except Exception as exc:  # 目录不可用时不应阻断
            logger.warning("同步命令目录失败: %s", exc)

        try:
            from butler.core import dsh_adapter

            count += dsh_adapter.register_all_plugin_commands(self)
        except Exception as exc:
            logger.debug("同步插件命令跳过: %s", exc)
        return count

    def promote(self, min_count: int | None = None) -> int:
        """把高频但未登记的命令补录为正式命令。"""
        if min_count is None:
            try:
                from package.core_utils.config_loader import config_loader

                min_count = int(config_loader.get("commands.promote_min_count", 5))
            except Exception:
                min_count = 5

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name, SUM(count) AS total FROM usage
                WHERE name NOT IN (SELECT name FROM commands)
                GROUP BY name HAVING total >= ?
                """,
                (min_count,),
            ).fetchall()

        promoted = 0
        for row in rows:
            self.upsert(
                CommandSpec(
                    name=row["name"],
                    category="自动记录",
                    purpose=f"高频使用自动登记（{row['total']} 次）",
                    source="learned",
                )
            )
            promoted += 1
        return promoted

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            total_cmd = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
            total_usage = conn.execute("SELECT COALESCE(SUM(count), 0) FROM usage").fetchone()[0]
            unregistered = conn.execute(
                """
                SELECT COUNT(DISTINCT name) FROM usage
                WHERE name NOT IN (SELECT name FROM commands)
                """
            ).fetchone()[0]
        return {
            "commands": total_cmd,
            "usage_total": total_usage,
            "unregistered": unregistered,
            "categories": self.categories(),
            "top_used": self.usage_stats(),
        }

    # ── 组合 ────────────────────────────────────────────────

    def add_combo(self, name: str, intent: str, steps: list[str]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO combos (name, intent, steps_json, count, updated_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (name, intent, json.dumps(steps, ensure_ascii=False), _now()),
            )

    def list_combos(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM combos ORDER BY id DESC").fetchall()
        result = []
        for row in rows:
            data = dict(row)
            try:
                data["steps"] = json.loads(data.pop("steps_json") or "[]")
            except json.JSONDecodeError:
                data["steps"] = []
            result.append(data)
        return result

    def suggest_combo(self, intent: str, limit: int = 3) -> list[dict[str, Any]]:
        intent_l = (intent or "").lower()
        matched = []
        for combo in self.list_combos():
            haystack = f"{combo.get('name', '')} {combo.get('intent', '')}".lower()
            ratio = SequenceMatcher(None, intent_l, haystack).ratio()
            if intent_l and (intent_l in haystack or ratio >= 0.4):
                matched.append((ratio, combo))
        matched.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in matched[:limit]]


command_recorder = CommandRecorder()
