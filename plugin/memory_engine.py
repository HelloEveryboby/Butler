import logging
import os
import sqlite3
import json
import ast
import threading
import time
import datetime
import re
from abc import ABCMeta, abstractmethod
from typing import List, Dict, Optional, Tuple, Any

from package.core_utils.log_manager import LogManager
from package.core_utils.embedding_utils import get_embedding

# 可选依赖项处理
try:
    import numpy as np
except ImportError:
    np = None

try:
    import redis
    from redisvl.index import SearchIndex
    from redisvl.query import VectorQuery
    from butler.redis_client import redis_client
except ImportError:
    redis = None
    SearchIndex = None
    VectorQuery = None
    redis_client = None

try:
    import zvec
except ImportError:
    zvec = None

# BHL 协议客户端，用于混合记忆查询
try:
    from butler.core.hybrid_link import HybridLinkClient
except ImportError:
    HybridLinkClient = None

class LongMemoryItem:
    """
    表示一条长期记忆的数据项（事实数据）。
    包含内容、ID、元数据以及搜索得分。
    """
    def __init__(self):
        self.content: Optional[str] = None
        self.id: Optional[str] = None
        self.metadata: Optional[dict] = None
        self.distance: Optional[float] = None

    @staticmethod
    def new(content: str, id: str, metadata: dict, distance: float = None):
        item = LongMemoryItem()
        item.content = content
        item.id = id
        item.metadata = metadata
        item.distance = distance
        return item

    def to_dict(self) -> dict:
        return {"id": self.id, "content": self.content, "metadata": self.metadata, "distance": self.distance}

class AbstractLongMemory(metaclass=ABCMeta):
    """长期事实记忆存储接口。"""
    @abstractmethod
    def init(self, logger: logging.Logger = None): pass
    @abstractmethod
    def save(self, items: List[LongMemoryItem]): pass
    @abstractmethod
    def search(self, text: str, n_results: int, metadata_filter: Optional[dict] = None) -> List[LongMemoryItem]: pass
    @abstractmethod
    def delete(self, ids: List[str]): pass
    @abstractmethod
    def get_recent_history(self, n_results: int) -> List[LongMemoryItem]: pass
    @abstractmethod
    def export_data(self) -> List[dict]: pass
    @abstractmethod
    def import_data(self, data: List[dict]): pass

class SQLiteLongMemory(AbstractLongMemory):
    """
    基于 SQLite 的事实记忆存储。
    内置 FTS5 强力搜索支持，具备自动同步触发器和 RLock 线程安全。
    """
    def __init__(self, collection_name: str = "long_memory_collection", cache_size: int = 100):
        self._logger = LogManager.get_logger(__name__)
        self._conn, self._collection_name = None, collection_name
        self._cache, self._cache_size = {}, cache_size
        self._lock = threading.RLock()

        # 安全性：严格限制集合名称格式
        if not collection_name.replace('_', '').isalnum():
            raise ValueError(f"Security Error: Invalid collection name '{collection_name}'.")

    def init(self, logger=None):
        if logger: self._logger = logger
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.normpath(os.path.join(current_dir, "../data/system_data/long_memory.db"))
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._create_table()
            self._logger.info(f"SQLiteLongMemory 初始化成功: {db_path}")
        except Exception as e:
            self._logger.error(f"SQLiteLongMemory 初始化失败: {e}")
            raise

    def _create_table(self):
        t = f'"{self._collection_name}"'
        ft = f'"{self._collection_name}_fts"'
        with self._conn:
            self._conn.execute(f"CREATE TABLE IF NOT EXISTS {t} (id TEXT PRIMARY KEY, content TEXT, metadata TEXT);")
            try:
                # 使用外部内容表模式实现 FTS5
                self._conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {ft} USING fts5(content, id UNINDEXED, content={t});")
                # 建立同步触发器
                self._conn.execute(f"CREATE TRIGGER IF NOT EXISTS {self._collection_name}_ai AFTER INSERT ON {t} BEGIN INSERT INTO {ft}(rowid, content, id) VALUES (new.rowid, new.content, new.id); END;")
                self._conn.execute(f"CREATE TRIGGER IF NOT EXISTS {self._collection_name}_ad AFTER DELETE ON {t} BEGIN INSERT INTO {ft}({ft}, rowid, content, id) VALUES('delete', old.rowid, old.content, old.id); END;")
                self._conn.execute(f"CREATE TRIGGER IF NOT EXISTS {self._collection_name}_au AFTER UPDATE ON {t} BEGIN INSERT INTO {ft}({ft}, rowid, content, id) VALUES('delete', old.rowid, old.content, old.id); INSERT INTO {ft}(rowid, content, id) VALUES (new.rowid, new.content, new.id); END;")
            except sqlite3.OperationalError:
                self._logger.warning("FTS5 extension is not available.")

    def save(self, items: List[LongMemoryItem]):
        if not items or not self._conn: return
        t = f'"{self._collection_name}"'
        with self._lock:
            # 简单的排重逻辑
            to_delete_ids = []
            for item in items:
                cursor = self._conn.cursor()
                cursor.execute(f"SELECT id FROM {t} WHERE content = ?", (item.content,))
                to_delete_ids.extend([r[0] for r in cursor.fetchall() if r[0] != item.id])

            if to_delete_ids:
                self.delete(to_delete_ids)

            try:
                with self._conn:
                    for it in items:
                        self._conn.execute(f"INSERT OR REPLACE INTO {t} (id, content, metadata) VALUES (?, ?, ?)",
                                         (it.id, it.content, json.dumps(it.metadata)))
                self._update_cache(items)
            except Exception as e: self._logger.error(f"SQLite 保存失败: {e}")

    def _sanitize_query(self, text: str) -> str:
        """清理查询字符串，防止 FTS5 语法错误。"""
        return re.sub(r'[^\w\s]', ' ', text).strip()

    def search(self, text, n, metadata_filter=None) -> List[LongMemoryItem]:
        cache_key = (text, n, frozenset(metadata_filter.items()) if metadata_filter else None)
        with self._lock:
            if cache_key in self._cache: return self._cache[cache_key]
        if not self._conn: return []

        t, ft = f'"{self._collection_name}"', f'"{self._collection_name}_fts"'
        cursor = self._conn.cursor()
        clean_text = self._sanitize_query(text)

        items = []
        try:
            # 优先尝试 FTS5 全文搜索
            if clean_text:
                query = f"SELECT {t}.id, {t}.content, {t}.metadata, bm25({ft}) FROM {ft} JOIN {t} ON {t}.rowid = {ft}.rowid WHERE {ft} MATCH ? LIMIT ?"
                cursor.execute(query, (clean_text, n))
                rows = cursor.fetchall()
                # bm25 越小越好，此处映射为相似度得分（取负值以便降序排列）
                items = [LongMemoryItem.new(id=r[0], content=r[1], metadata=json.loads(r[2]), distance=-float(r[3])) for r in rows]
        except: pass

        if not items:
            # 降级到 LIKE 搜索
            cursor.execute(f"SELECT id, content, metadata FROM {t} WHERE content LIKE ? LIMIT ?", (f"%{text}%", n))
            items = [LongMemoryItem.new(id=r[0], content=r[1], metadata=json.loads(r[2]), distance=0.0) for r in cursor.fetchall()]

        with self._lock:
            if len(self._cache) >= self._cache_size: self._cache.pop(next(iter(self._cache)))
            self._cache[cache_key] = items
        return items

    def delete(self, ids):
        t = f'"{self._collection_name}"'
        with self._conn: self._conn.executemany(f"DELETE FROM {t} WHERE id = ?", [(i,) for i in ids])
        self._invalidate_cache(ids)

    def get_recent_history(self, n):
        t = f'"{self._collection_name}"'
        if not self._conn: return []
        cursor = self._conn.cursor()
        cursor.execute(f"SELECT id, content, metadata FROM {t} ORDER BY rowid DESC LIMIT ?", (n,))
        return [LongMemoryItem.new(id=r[0], content=r[1], metadata=json.loads(r[2]), distance=0.0) for r in cursor.fetchall()]

    def export_data(self) -> List[dict]:
        t = f'"{self._collection_name}"'
        if not self._conn: return []
        cursor = self._conn.cursor(); cursor.execute(f"SELECT id, content, metadata FROM {t}")
        return [{"id": r[0], "content": r[1], "metadata": json.loads(r[2])} for r in cursor.fetchall()]

    def import_data(self, data: List[dict]):
        items = [LongMemoryItem.new(id=d["id"], content=d["content"], metadata=d["metadata"]) for d in data]
        if items: self.save(items)

    def _update_cache(self, items):
        for item in items: self._cache[(item.content, 1, frozenset(item.metadata.items()))] = [item]
    def _invalidate_cache(self, ids):
        keys = [k for k, v in self._cache.items() if any(i.id in ids for i in v)]
        for k in keys: self._cache.pop(k, None)

class RedisLongMemory(AbstractLongMemory):
    """基于 Redis 的向量存储实现。"""
    def __init__(self, api_key, col="long_memory_collection"):
        self._api_key, self._col = api_key, col; self.client = redis_client
        if not self.client: raise ConnectionError("Redis client not initialized.")
        schema = {"index":{"name":col,"prefix":f"{col}:"},"fields":[{"name":"content","type":"text"},{"name":"metadata","type":"text"},{"name":"embedding","type":"vector","attrs":{"dims":1024,"distance_metric":"cosine","algorithm":"flat"}}]}
        self.index = SearchIndex.from_dict(schema); self.index.set_client(self.client)
        if not self.client.exists(f"idx:{col}"): self.index.create(overwrite=True)

    def init(self, logger=None): pass
    def save(self, items):
        recs = []
        for it in items:
            emb = get_embedding(it.content, self._api_key)
            if emb is not None: recs.append({"id":it.id, "content":it.content, "metadata":json.dumps(it.metadata), "embedding":emb.tobytes()})
        if recs:
            self.index.load(recs)
            for r in recs: self.client.zadd(f"{self._col}:history", {r['id']: json.loads(r['metadata']).get('timestamp', time.time())})

    def search(self, text, n, filter=None):
        emb = get_embedding(text, self._api_key)
        if emb is None: return []
        results = self.index.query(VectorQuery(vector=emb.tobytes(), vector_field_name="embedding", return_fields=["id","content","metadata","vector_distance"], num_results=n))
        return [LongMemoryItem.new(id=d["id"], content=d["content"], metadata=json.loads(d["metadata"]), distance=1.0 - float(d["vector_distance"])) for d in results]

    def delete(self, ids):
        for i in ids: self.client.delete(f"{self._col}:{i}"); self.client.zrem(f"{self._col}:history", i)
    def get_recent_history(self, n):
        ids = self.client.zrevrange(f"{self._col}:history", 0, n-1)
        items = []
        for i in ids:
            sid = i.decode() if isinstance(i, bytes) else i
            d = self.client.hgetall(f"{self._col}:{sid}")
            if d: items.append(LongMemoryItem.new(id=sid, content=d.get(b"content", b"").decode(), metadata=json.loads(d.get(b"metadata", b"{}").decode()), distance=0))
        return items
    def export_data(self): return []
    def import_data(self, data):
        items = [LongMemoryItem.new(id=d["id"], content=d["content"], metadata=d["metadata"]) for d in data]
        if items: self.save(items)

class ZvecLongMemory(AbstractLongMemory):
    """基于 zvec 的本地向量存储。"""
    def __init__(self, api_key=None, collection_name="long_memory_zvec"):
        self._api_key, self._collection_name, self._offline = api_key, collection_name, (api_key is None)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._data_path = os.path.normpath(os.path.join(base_dir, "../data/system_data/zvec_memory", collection_name))
        self.collection = None

    def init(self, logger=None):
        if not zvec: raise ImportError("zvec is not installed.")
        if not os.path.exists(self._data_path): os.makedirs(self._data_path, exist_ok=True)
        schema = zvec.CollectionSchema(name=self._collection_name, vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, 1024), fields=[zvec.FieldSchema("content", zvec.DataType.STRING), zvec.FieldSchema("metadata", zvec.DataType.STRING), zvec.FieldSchema("timestamp", zvec.DataType.DOUBLE)])
        self.collection = zvec.create_and_open(path=self._data_path, schema=schema)

    def save(self, items):
        if not self.collection: return
        docs = []
        for it in items:
            emb = get_embedding(it.content, self._api_key, offline=self._offline)
            if emb is not None:
                docs.append(zvec.Doc(id=it.id or f"mem_{int(time.time()*1000)}", vectors={"embedding": emb.tolist()}, fields={"content": it.content, "metadata": json.dumps(it.metadata), "timestamp": it.metadata.get("timestamp", time.time())}))
        if docs: self.collection.insert(docs)

    def search(self, text, n, filter=None):
        if not self.collection: return []
        emb = get_embedding(text, self._api_key, offline=self._offline)
        if emb is None: return []
        query = zvec.VectorQuery(field_name="embedding", vector=emb.tolist())
        results = self.collection.query(vectors=query, topk=n)
        return [LongMemoryItem.new(id=d.id, content=d.field("content"), metadata=json.loads(d.field("metadata")), distance=d.score) for d in results]

    def delete(self, ids): pass
    def get_recent_history(self, n): return []
    def export_data(self): return []
    def import_data(self, data):
        items = [LongMemoryItem.new(id=d["id"], content=d["content"], metadata=d["metadata"]) for d in data]
        if items: self.save(items)

class DeepSeekLongMemory(AbstractLongMemory):
    """基于内存的语义存储。"""
    def __init__(self, api_key):
        self._api_key = api_key
        self._memory: Dict[str, LongMemoryItem] = {}
        self._embeddings: Dict[str, Any] = {}

    def init(self, logger=None): pass

    def save(self, items: List[LongMemoryItem]):
        for item in items:
            emb = get_embedding(item.content, self._api_key)
            if emb is not None:
                self._memory[item.id] = item
                self._embeddings[item.id] = emb

    def search(self, text, n, filter=None) -> List[LongMemoryItem]:
        query_emb = get_embedding(text, self._api_key)
        if query_emb is None or not self._embeddings: return []
        candidate_ids = list(self._memory.keys())
        c_embs = np.array([self._embeddings[cid] for cid in candidate_ids])
        sims = np.dot(c_embs, query_emb) / (np.linalg.norm(c_embs, axis=1) * np.linalg.norm(query_emb))
        top_indices = np.argsort(sims)[-n:][::-1]
        results = []
        for i in top_indices:
            cid = candidate_ids[i]
            item = self._memory[cid]
            item.distance = float(sims[i])
            results.append(item)
        return results

    def delete(self, ids: List[str]):
        for cid in ids:
            self._memory.pop(cid, None); self._embeddings.pop(cid, None)

    def get_recent_history(self, n): return list(self._memory.values())[-n:]
    def export_data(self): return [item.to_dict() for item in self._memory.values()]
    def import_data(self, data):
        items = [LongMemoryItem.new(id=d["id"], content=d["content"], metadata=d["metadata"]) for d in data]
        if items: self.save(items)

class HybridMemoryManager:
    """混合日志记忆系统管理。"""
    def __init__(self, root=None):
        self._logger = LogManager.get_logger(__name__)
        p_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
        self.root = os.path.abspath(root or os.path.join(p_root, "data", "butler_memory"))
        self.log_dir = os.path.join(self.root, "memory")
        self.long_term_file = os.path.join(self.root, "MEMORY.md")
        os.makedirs(self.log_dir, exist_ok=True)
        if HybridLinkClient:
            self._client = HybridLinkClient(executable_path=os.path.join(p_root, "programs/hybrid_memory/memory_service"), fallback_enabled=True)
            self._client.start()
        else: self._client = None

    def add_daily_log(self, content):
        p = os.path.join(self.log_dir, f"{datetime.datetime.now().strftime('%Y-%m-%d')}.md")
        fmt = f"\n### {datetime.datetime.now().strftime('%H:%M:%S')}\n{content}\n"
        with open(p, "a", encoding="utf-8") as f: f.write(fmt)

    def add_long_term_memory(self, content):
        with open(self.long_term_file, "a", encoding="utf-8") as f: f.write(f"\n- {content}\n")

    def search(self, query, n=5):
        if not self._client: return []
        return self._client.call("search", {"root": self.root, "query": query, "max_results": n}) or []

    def get_file_content(self, path, start=1, num=-1):
        full_path = os.path.abspath(os.path.join(self.root, path))
        if not full_path.startswith(self.root): return "Security Violation: Access Denied."
        if not os.path.exists(full_path): return ""
        with open(full_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[max(0, start-1): (start-1+num if num>0 else None)])

# 全局单例
hybrid_memory_manager = HybridMemoryManager()

class UnifiedMemoryEngine:
    """
    统一记忆引擎：整合“事实数据库”与“原始对话日志”。
    """
    def __init__(self, fact_db: AbstractLongMemory, log_sys: HybridMemoryManager):
        self.fact_db, self.logs = fact_db, log_sys
        self._logger = LogManager.get_logger(__name__)

    def init(self, logger=None):
        if logger: self._logger = logger
        self.fact_db.init(self._logger)

    def record_interaction(self, user_cmd: str, assistant_resp: str):
        """记录交互：实现双轨同步。"""
        self.logs.add_daily_log(f"User: {user_cmd}\nAssistant: {assistant_resp}")

        # 彩蛋逻辑：识别怀旧词汇并标记
        is_nos = any(k in user_cmd for k in ["一中", "早读", "中考", "操场"])
        meta = {"role": "assistant", "type": "nostalgia" if is_nos else "chat", "ts": time.time()}

        item = LongMemoryItem.new(content=assistant_resp, id=f"resp_{int(time.time()*1000)}", metadata=meta)
        self.fact_db.save([item])

    def save_fact(self, content: str, metadata: dict = None):
        """保存事实：数据共享。"""
        metadata = metadata or {}
        item = LongMemoryItem.new(content=content, id=f"fact_{int(time.time()*1000)}", metadata=metadata)
        self.fact_db.save([item])
        self.logs.add_daily_log(f"[Fact Synchronized] {content}")

    def unified_search(self, query: str, n: int = 5) -> List[Dict[str, Any]]:
        """跨系统搜索：合并事实与语境。"""
        f_res = self.fact_db.search(query, n)
        l_res = self.logs.search(query, n)

        combined = []
        for r in f_res:
            combined.append({"src": "fact_db", "content": r.content, "score": r.distance, "meta": r.metadata})

        for r in l_res:
            c = r.get("content", "") if isinstance(r, dict) else str(r)
            combined.append({"src": "logs", "content": c, "score": 0.5, "meta": r if isinstance(r, dict) else {}})

        # 降序排序，得分越高越靠前
        return sorted(combined, key=lambda x: x["score"], reverse=True)

    def search(self, text, n, filter=None): return self.fact_db.search(text, n, filter)
    def save(self, items): self.fact_db.save(items)
    def delete(self, ids): self.fact_db.delete(ids)
    def get_recent_history(self, n): return self.fact_db.get_recent_history(n)
    def export_data(self): return self.fact_db.export_data()
    def import_data(self, data): self.fact_db.import_data(data)
