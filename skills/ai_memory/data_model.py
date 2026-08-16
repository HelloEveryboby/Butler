# -*- coding: utf-8 -*-
"""
AI Memory Data Model and Schema Specifications
支持 Markdown 文件 (YAML FrontMatter + Body)、SQLite FTS5 索引与 Zvec 向量 Schema 定义。
"""

import os
import re
import json
import time
import datetime
from typing import List, Dict, Any, Optional

try:
    import yaml
except ImportError:
    yaml = None

class MemoryDocument:
    """
    表示一篇 AI 记忆文档 (包含 FrontMatter 元数据与 Markdown 正文)
    """
    def __init__(
        self,
        title: str,
        project: str = "default",
        session_summary: str = "",
        decisions: Optional[List[str]] = None,
        open_questions: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        content: str = "",
        file_path: Optional[str] = None,
        date: Optional[str] = None,
        doc_id: Optional[str] = None
    ):
        self.doc_id = doc_id or f"mem_{int(time.time() * 1000)}"
        self.title = title
        self.project = project
        self.session_summary = session_summary
        self.decisions = decisions or []
        self.open_questions = open_questions or []
        self.tags = tags or []
        self.content = content
        self.file_path = file_path
        self.date = date or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_frontmatter_markdown(self) -> str:
        """格式化为带 FrontMatter 的 Markdown 内容"""
        meta = {
            "id": self.doc_id,
            "title": self.title,
            "date": self.date,
            "project": self.project,
            "tags": self.tags,
            "session_summary": self.session_summary,
            "decisions": self.decisions,
            "open_questions": self.open_questions,
        }

        if yaml:
            yaml_str = yaml.dump(meta, allow_unicode=True, sort_keys=False).strip()
        else:
            # Fallback simple YAML generator
            yaml_lines = [
                f"id: {self.doc_id}",
                f"title: \"{self.title}\"",
                f"date: \"{self.date}\"",
                f"project: \"{self.project}\"",
                f"tags: {json.dumps(self.tags, ensure_ascii=False)}",
                f"session_summary: \"{self.session_summary}\"",
                "decisions:",
            ]
            for d in self.decisions:
                yaml_lines.append(f"  - \"{d}\"")
            yaml_lines.append("open_questions:")
            for q in self.open_questions:
                yaml_lines.append(f"  - \"{q}\"")
            yaml_str = "\n".join(yaml_lines)

        return f"---\n{yaml_str}\n---\n\n{self.content.strip()}\n"

    @classmethod
    def from_markdown(cls, raw_text: str, file_path: Optional[str] = None) -> "MemoryDocument":
        """从原生 Markdown 文本解析 FrontMatter 和 Body"""
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw_text, re.DOTALL)
        meta = {}
        content = raw_text

        if fm_match:
            yaml_text, content = fm_match.group(1), fm_match.group(2)
            if yaml:
                try:
                    meta = yaml.safe_load(yaml_text) or {}
                except Exception:
                    meta = {}
            else:
                # Basic line regex fallback parser
                meta = {}
                for line in yaml_text.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        meta[k.strip()] = v.strip().strip('"').strip("'")

        # Extract values
        doc_id = meta.get("id")
        title = meta.get("title", "Untitled Memory")
        project = meta.get("project", "default")
        session_summary = meta.get("session_summary", "")
        decisions = meta.get("decisions", [])
        if isinstance(decisions, str):
            try: decisions = json.loads(decisions)
            except Exception: decisions = [decisions]
        open_questions = meta.get("open_questions", [])
        if isinstance(open_questions, str):
            try: open_questions = json.loads(open_questions)
            except Exception: open_questions = [open_questions]
        tags = meta.get("tags", [])
        if isinstance(tags, str):
            try: tags = json.loads(tags)
            except Exception: tags = [tags]
        date = meta.get("date", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        return cls(
            doc_id=doc_id,
            title=title,
            project=project,
            session_summary=session_summary,
            decisions=decisions,
            open_questions=open_questions,
            tags=tags,
            content=content,
            file_path=file_path,
            date=date
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.doc_id,
            "title": self.title,
            "project": self.project,
            "session_summary": self.session_summary,
            "decisions": self.decisions,
            "open_questions": self.open_questions,
            "tags": self.tags,
            "content": self.content,
            "file_path": self.file_path,
            "date": self.date
        }


# SQLite 表结构与 FTS5 规范
CREATE_MEMORIES_TABLE = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    title TEXT,
    project TEXT,
    file_path TEXT UNIQUE,
    content TEXT,
    session_summary TEXT,
    decisions TEXT,
    open_questions TEXT,
    tags TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_MEMORIES_FTS_TABLE = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    title,
    content,
    session_summary,
    decisions,
    open_questions,
    tags,
    content='memories',
    content_rowid='rowid'
);
"""

CREATE_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, title, content, session_summary, decisions, open_questions, tags)
  VALUES (new.rowid, new.title, new.content, new.session_summary, new.decisions, new.open_questions, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, title, content, session_summary, decisions, open_questions, tags)
  VALUES('delete', old.rowid, old.title, old.content, old.session_summary, old.decisions, old.open_questions, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, title, content, session_summary, decisions, open_questions, tags)
  VALUES('delete', old.rowid, old.title, old.content, old.session_summary, old.decisions, old.open_questions, old.tags);
  INSERT INTO memories_fts(rowid, title, content, session_summary, decisions, open_questions, tags)
  VALUES (new.rowid, new.title, new.content, new.session_summary, new.decisions, new.open_questions, new.tags);
END;
"""
