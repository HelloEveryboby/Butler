# -*- coding: utf-8 -*-
"""
AI Memory Service Core Engine
提供 Markdown 存储、SQLite FTS5 索引、Zvec 向量检索以及 RRF (倒数排名融合) 混合搜索服务。
"""

import os
import sqlite3
import json
import time
import datetime
import logging
from typing import List, Dict, Any, Optional, Tuple

from skills.ai_memory.data_model import (
    MemoryDocument,
    CREATE_MEMORIES_TABLE,
    CREATE_MEMORIES_FTS_TABLE,
    CREATE_FTS_TRIGGERS
)
from package.core_utils.embedding_utils import get_embedding

try:
    import zvec
except ImportError:
    zvec = None

logger = logging.getLogger("ai_memory_service")


class MemoryService:
    """
    AI 记忆服务核心引擎：支持项目级隔离与全局备用存储。
    """
    def __init__(self, project_root: Optional[str] = None, api_key: Optional[str] = None):
        self.project_root = project_root or os.getcwd()
        self.api_key = api_key
        self.memory_dir = self._resolve_memory_dir()
        self.db_path = os.path.join(self.memory_dir, "memory.db")
        self.zvec_dir = os.path.join(self.memory_dir, "zvec_data")

        os.makedirs(self.memory_dir, exist_ok=True)
        self._init_sqlite()
        self._init_zvec()

    def _resolve_memory_dir(self) -> str:
        """解析存储路径：优先项目内 .butler-memory，无项目根目录降级至全局 ~/butler-memory"""
        if self.project_root and os.path.exists(self.project_root):
            p = os.path.join(self.project_root, ".butler-memory")
            return p
        user_home = os.path.expanduser("~")
        return os.path.join(user_home, "butler-memory")

    def _init_sqlite(self):
        """初始化 SQLite 数据库与 FTS5 全文索引"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        with self.conn:
            self.conn.execute(CREATE_MEMORIES_TABLE)
            try:
                self.conn.execute(CREATE_MEMORIES_FTS_TABLE)
                for trigger_sql in CREATE_FTS_TRIGGERS.strip().split(";\n\n"):
                    if trigger_sql.strip():
                        self.conn.execute(trigger_sql)
            except sqlite3.OperationalError as e:
                logger.warning(f"SQLite FTS5 虚拟表建立警告 (可能已存在或未启用 FTS5 扩展): {e}")

    def _init_zvec(self):
        """初始化 Zvec 嵌入式向量数据库"""
        self.zvec_collection = None
        self.zvec_enabled = False
        if not zvec:
            logger.info("未安装 zvec，系统将降级为纯 SQLite FTS5 混合全文检索。")
            return

        try:
            os.makedirs(self.zvec_dir, exist_ok=True)
            schema = zvec.CollectionSchema(
                name="ai_memory_zvec",
                vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, 1024),
                fields=[
                    zvec.FieldSchema("doc_id", zvec.DataType.STRING),
                    zvec.FieldSchema("title", zvec.DataType.STRING),
                    zvec.FieldSchema("project", zvec.DataType.STRING),
                    zvec.FieldSchema("file_path", zvec.DataType.STRING),
                    zvec.FieldSchema("content", zvec.DataType.STRING),
                    zvec.FieldSchema("timestamp", zvec.DataType.DOUBLE)
                ]
            )
            self.zvec_collection = zvec.create_and_open(path=self.zvec_dir, schema=schema)
            self.zvec_enabled = True
            logger.info("Zvec 向量数据库初始化成功。")
        except Exception as e:
            logger.warning(f"Zvec 向量库初始化失败 ({e})，降级为 SQLite FTS5。")
            self.zvec_enabled = False

    def save_memory(self, doc: MemoryDocument) -> str:
        """
        保存记忆文档：
        1. 写入 Markdown 源文件
        2. 索引至 SQLite & FTS5
        3. 嵌入生成并存入 Zvec (若可用)
        """
        now_str = datetime.datetime.now().strftime("%Y-%m-%d")
        safe_title = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in doc.title)[:40]
        filename = f"{now_str}-{safe_title}.md"
        file_path = os.path.join(self.memory_dir, filename)

        doc.file_path = file_path
        markdown_text = doc.to_frontmatter_markdown()

        # 1. 保存 Markdown 文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        # 2. 索引至 SQLite
        self._save_doc_to_sqlite(doc)

        # 3. 保存至 Zvec
        self._save_doc_to_zvec(doc)

        return file_path

    def index_file(self, file_path: str) -> Optional[MemoryDocument]:
        """读取外部 Markdown 文件并建立索引"""
        if not os.path.exists(file_path):
            return None

        with open(file_path, "r", encoding="utf-8") as f:
            raw_content = f.read()

        doc = MemoryDocument.from_markdown(raw_content, file_path=file_path)
        self._save_doc_to_sqlite(doc)
        self._save_doc_to_zvec(doc)
        return doc

    def index_all_files(self) -> int:
        """索引记忆目录下的所有 .md 文件"""
        count = 0
        for root, _, files in os.walk(self.memory_dir):
            for file in files:
                if file.endswith(".md"):
                    fp = os.path.join(root, file)
                    self.index_file(fp)
                    count += 1
        return count

    def _save_doc_to_sqlite(self, doc: MemoryDocument):
        """保存/更新 SQLite 记录"""
        decisions_json = json.dumps(doc.decisions, ensure_ascii=False)
        questions_json = json.dumps(doc.open_questions, ensure_ascii=False)
        tags_json = json.dumps(doc.tags, ensure_ascii=False)

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO memories (
                id, title, project, file_path, content, session_summary, decisions, open_questions, tags, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            doc.doc_id, doc.title, doc.project, doc.file_path, doc.content,
            doc.session_summary, decisions_json, questions_json, tags_json
        ))
        self.conn.commit()

    def _save_doc_to_zvec(self, doc: MemoryDocument):
        """生成 embedding 并写入 Zvec"""
        if not self.zvec_enabled or not self.zvec_collection:
            return

        try:
            full_text = f"{doc.title}\n{doc.session_summary}\n{' '.join(doc.decisions)}\n{doc.content}"
            emb = get_embedding(full_text, self.api_key, offline=(self.api_key is None))
            if emb is not None:
                zdoc = zvec.Doc(
                    id=doc.doc_id,
                    vectors={"embedding": emb.tolist()},
                    fields={
                        "doc_id": doc.doc_id,
                        "title": doc.title,
                        "project": doc.project,
                        "file_path": doc.file_path or "",
                        "content": doc.content,
                        "timestamp": time.time()
                    }
                )
                self.zvec_collection.insert([zdoc])
        except Exception as e:
            logger.warning(f"写入 Zvec 索引失败: {e}")

    def fts_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """SQLite FTS5 全文搜索"""
        cursor = self.conn.cursor()
        clean_query = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
        results = []

        if clean_query:
            try:
                sql = """
                    SELECT m.id, m.title, m.project, m.file_path, m.content, m.session_summary,
                           m.decisions, m.open_questions, m.tags, m.created_at, bm25(memories_fts) as score
                    FROM memories_fts
                    JOIN memories m ON m.rowid = memories_fts.rowid
                    WHERE memories_fts MATCH ?
                    ORDER BY score ASC
                    LIMIT ?
                """
                cursor.execute(sql, (clean_query, limit))
                rows = cursor.fetchall()
                for r in rows:
                    results.append({
                        "id": r[0], "title": r[1], "project": r[2], "file_path": r[3],
                        "content": r[4], "session_summary": r[5],
                        "decisions": json.loads(r[6] or "[]"),
                        "open_questions": json.loads(r[7] or "[]"),
                        "tags": json.loads(r[8] or "[]"),
                        "created_at": r[9],
                        "score": -float(r[10]) # bm25 lower is better
                    })
            except Exception as e:
                logger.warning(f"FTS5 检索异常，退回 LIKE 模糊搜素: {e}")

        if not results:
            sql = """
                SELECT id, title, project, file_path, content, session_summary,
                       decisions, open_questions, tags, created_at
                FROM memories
                WHERE title LIKE ? OR content LIKE ? OR session_summary LIKE ?
                LIMIT ?
            """
            pat = f"%{query}%"
            cursor.execute(sql, (pat, pat, pat, limit))
            rows = cursor.fetchall()
            for r in rows:
                results.append({
                    "id": r[0], "title": r[1], "project": r[2], "file_path": r[3],
                    "content": r[4], "session_summary": r[5],
                    "decisions": json.loads(r[6] or "[]"),
                    "open_questions": json.loads(r[7] or "[]"),
                    "tags": json.loads(r[8] or "[]"),
                    "created_at": r[9],
                    "score": 1.0
                })

        return results

    def vector_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Zvec 向量语义搜索"""
        if not self.zvec_enabled or not self.zvec_collection:
            return []

        try:
            emb = get_embedding(query, self.api_key, offline=(self.api_key is None))
            if emb is None:
                return []
            vq = zvec.VectorQuery(field_name="embedding", vector=emb.tolist())
            zres = self.zvec_collection.query(vectors=vq, topk=limit)
            doc_ids = [d.id for d in zres]

            if not doc_ids:
                return []

            placeholders = ",".join(["?"] * len(doc_ids))
            sql = f"""
                SELECT id, title, project, file_path, content, session_summary,
                       decisions, open_questions, tags, created_at
                FROM memories WHERE id IN ({placeholders})
            """
            cursor = self.conn.cursor()
            cursor.execute(sql, doc_ids)
            doc_map = {r[0]: r for r in cursor.fetchall()}

            results = []
            for d in zres:
                r = doc_map.get(d.id)
                if r:
                    results.append({
                        "id": r[0], "title": r[1], "project": r[2], "file_path": r[3],
                        "content": r[4], "session_summary": r[5],
                        "decisions": json.loads(r[6] or "[]"),
                        "open_questions": json.loads(r[7] or "[]"),
                        "tags": json.loads(r[8] or "[]"),
                        "created_at": r[9],
                        "score": float(d.score)
                    })
            return results
        except Exception as e:
            logger.warning(f"Zvec 向量搜索失败: {e}")
            return []

    def hybrid_search(self, query: str, limit: int = 5, k: float = 60.0) -> List[Dict[str, Any]]:
        """
        RRF (Reciprocal Rank Fusion) 倒数排名融合混合搜索：
        RRF_score(d) = sum( 1 / (k + rank(d)) )
        自动兼容纯 FTS5 降级模式。
        """
        fts_items = self.fts_search(query, limit=limit * 2)
        vec_items = self.vector_search(query, limit=limit * 2)

        rrf_scores: Dict[str, float] = {}
        item_data: Dict[str, Dict[str, Any]] = {}

        # 累计 FTS5 排名得分
        for rank, item in enumerate(fts_items):
            doc_id = item["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))
            item_data[doc_id] = item

        # 累计 Vector 排名得分
        for rank, item in enumerate(vec_items):
            doc_id = item["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))
            if doc_id not in item_data:
                item_data[doc_id] = item

        # 重新按 RRF 分数从高到低排序
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        final_results = []
        for doc_id in sorted_ids[:limit]:
            res = item_data[doc_id]
            res["rrf_score"] = rrf_scores[doc_id]
            final_results.append(res)

        return final_results

    def create_handoff(
        self,
        project_name: str,
        session_summary: str,
        decisions: List[str],
        open_questions: List[str],
        tags: Optional[List[str]] = None,
        title: str = "Session Handoff"
    ) -> MemoryDocument:
        """生成交接文件并持久化"""
        doc = MemoryDocument(
            title=title,
            project=project_name,
            session_summary=session_summary,
            decisions=decisions,
            open_questions=open_questions,
            tags=tags or ["handoff", "ai-session"],
            content=f"# 交接记录: {title}\n\n## 会话摘要\n{session_summary}\n\n## 决议事项\n" +
                    "\n".join(f"- {d}" for d in decisions) +
                    "\n\n## 待决问题\n" +
                    "\n".join(f"- {q}" for q in open_questions)
        )
        self.save_memory(doc)
        return doc

    def get_latest_handoff(self, project_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取最近一次交接文档"""
        cursor = self.conn.cursor()
        if project_name:
            sql = """
                SELECT id, title, project, file_path, content, session_summary,
                       decisions, open_questions, tags, created_at
                FROM memories
                WHERE project = ? AND (tags LIKE '%handoff%' OR title LIKE '%Handoff%')
                ORDER BY created_at DESC LIMIT 1
            """
            cursor.execute(sql, (project_name,))
        else:
            sql = """
                SELECT id, title, project, file_path, content, session_summary,
                       decisions, open_questions, tags, created_at
                FROM memories
                WHERE tags LIKE '%handoff%' OR title LIKE '%Handoff%'
                ORDER BY created_at DESC LIMIT 1
            """
            cursor.execute(sql)

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "id": row[0], "title": row[1], "project": row[2], "file_path": row[3],
            "content": row[4], "session_summary": row[5],
            "decisions": json.loads(row[6] or "[]"),
            "open_questions": json.loads(row[7] or "[]"),
            "tags": json.loads(row[8] or "[]"),
            "created_at": row[9]
        }
