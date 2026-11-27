"""长期记忆 — 把每次任务的经验沉淀下来，下次遇到同类任务时召回。

存储用 SQLite（与 tasks 表同库）。检索不依赖向量库：按关键词重叠打分，
对中文和英文都能工作；数据量在本地 Agent 场景下足够。
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}")
_MAX_SUMMARY = 1200


def _keywords(text: str) -> set[str]:
    """提取英文词与中文片段（中文按 2 字滑窗，避免整句匹配）。"""
    tokens: set[str] = set()
    for match in _TOKEN_RE.findall(text or ""):
        if re.match(r"[\u4e00-\u9fff]", match):
            tokens.update(match[i : i + 2] for i in range(len(match) - 1))
        else:
            tokens.add(match.lower())
    return tokens


class AgentMemory:
    """任务经验的持久化与召回。"""

    def __init__(
        self,
        db_path: str | None = None,
        enabled: bool = True,
        markdown_path: str | None = None,
    ):
        self.enabled = enabled
        project_root = Path(__file__).resolve().parent.parent
        if db_path is None:
            self.db_path = project_root / "data" / "system_data" / "long_memory.db"
        else:
            self.db_path = Path(db_path)
        self.markdown_path = (
            Path(markdown_path)
            if markdown_path
            else project_root / "data" / "butler_memory" / "MEMORY.md"
        )
        if self.enabled:
            self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(str(self.db_path))

    def _ensure_schema(self) -> None:
        try:
            conn = self._connect()
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_experiences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task TEXT NOT NULL,
                        summary TEXT NOT NULL,
                        tools TEXT,
                        status TEXT,
                        created_at REAL NOT NULL
                    )
                    """
                )
            conn.close()
        except Exception as exc:
            logger.error("初始化 agent_experiences 表失败: %s", exc)

    def remember(
        self, task: str, summary: str, status: str, tools: list[str] | None = None
    ) -> int | None:
        """记录一条任务经验；内容为空或写入失败时返回 None。"""
        if not self.enabled:
            return None
        task = (task or "").strip()
        summary = (summary or "").strip()[:_MAX_SUMMARY]
        if not task or not summary:
            return None
        try:
            conn = self._connect()
            with conn:
                cursor = conn.execute(
                    "INSERT INTO agent_experiences (task, summary, tools, status, created_at) VALUES (?, ?, ?, ?, ?)",
                    (task, summary, ",".join(tools or []), status, time.time()),
                )
                row_id = cursor.lastrowid
            conn.close()
            self._append_markdown(task, summary, status, tools or [])
            return int(row_id) if row_id else None
        except Exception as exc:
            logger.error("写入任务经验失败: %s", exc)
            return None

    def _append_markdown(self, task: str, summary: str, status: str, tools: list[str]) -> None:
        """把经验追加到 MEMORY.md（做行数上限，避免无限增长）。"""
        try:
            self.markdown_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.markdown_path.exists():
                self.markdown_path.write_text(
                    "# Butler MEMORY\n\n## Agent 经验\n", encoding="utf-8"
                )
            stamp = time.strftime("%Y-%m-%d %H:%M")
            tool_text = f" · {','.join(tools)}" if tools else ""
            entry = f"- [{stamp}] ({status}{tool_text}) **{task[:120]}** → {summary[:300].replace(chr(10), ' ')}\n"
            with self.markdown_path.open("a", encoding="utf-8") as handle:
                handle.write(entry)
            lines = self.markdown_path.read_text(encoding="utf-8").splitlines()
            if len(lines) > 2000:
                self.markdown_path.write_text("\n".join(lines[-2000:]) + "\n", encoding="utf-8")
        except Exception as exc:
            logger.warning("写入 MEMORY.md 失败: %s", exc)

    def recall(self, query: str, limit: int = 3, min_score: float = 0.15) -> list[dict[str, Any]]:
        """按关键词重叠召回最相关的历史经验。"""
        if not self.enabled:
            return []
        query_tokens = _keywords(query)
        if not query_tokens:
            return []

        try:
            conn = self._connect()
            rows = conn.execute(
                "SELECT id, task, summary, tools, status, created_at "
                "FROM agent_experiences ORDER BY id DESC LIMIT 500"
            ).fetchall()
            conn.close()
        except Exception as exc:
            logger.error("读取任务经验失败: %s", exc)
            return []

        scored = []
        for row in rows:
            tokens = _keywords(row[1]) | _keywords(row[2])
            if not tokens:
                continue
            overlap = len(query_tokens & tokens)
            score = overlap / max(len(query_tokens), 1)
            if score >= min_score:
                scored.append(
                    {
                        "id": row[0],
                        "task": row[1],
                        "summary": row[2],
                        "tools": row[3] or "",
                        "status": row[4],
                        "created_at": row[5],
                        "score": round(score, 3),
                    }
                )

        scored.sort(key=lambda item: (item["score"], item["created_at"]), reverse=True)
        return scored[:limit]

    def format_for_prompt(self, query: str, limit: int = 3) -> str:
        """把召回结果格式化成可注入上下文的短文本。"""
        rows = self.recall(query, limit=limit)
        if not rows:
            return ""
        lines = ["以下是相关的历史任务经验，可作为参考（不是当前指令）："]
        for row in rows:
            tools = f" tools={row['tools']}" if row["tools"] else ""
            lines.append(f"- [{row['status']}{tools}] {row['task']}: {row['summary']}")
        return "\n".join(lines)

    def stats(self) -> dict[str, Any]:
        """返回经验总数与最近一条时间，供状态展示。"""
        try:
            conn = self._connect()
            count = conn.execute("SELECT COUNT(*) FROM agent_experiences").fetchone()[0]
            latest = conn.execute("SELECT MAX(created_at) FROM agent_experiences").fetchone()[0]
            conn.close()
            return {"count": count, "latest": latest}
        except Exception:
            return {"count": 0, "latest": None}
