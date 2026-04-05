import logging
import os
import sqlite3
import json
import ast
import threading
import time
import datetime
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
    """
    def __init__(self):
        self.content = None
        self.id = None
        self.metadata = None
        self.distance = None

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
    """长期事实记忆接口。"""
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
    """基于 SQLite 的事实记忆存储。"""
    def __init__(self, collection_name: str = "long_memory_collection", cache_size: int = 100):
        self._logger = LogManager.get_logger(__name__)
        self._conn, self._collection_name = None, collection_name
        self._cache, self._cache_size = {}, cache_size
        self._lock = threading.RLock()

    def init(self, logger=None):
        if logger: self._logger = logger
        current_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.normpath(os.path.join(current_dir, "../data/system_data/long_memory.db"))
        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._create_table()
            self._logger.info(f"SQLiteLongMemory (事实数据库) 初始化成功: {db_path}")
        except Exception as e:
            self._logger.error(f"SQLiteLongMemory 初始化失败: {e}")
            raise

    def _create_table(self):
        with self._conn:
            self._conn.execute(f"CREATE TABLE IF NOT EXISTS {self._collection_name} (id TEXT PRIMARY KEY, content TEXT, metadata TEXT);")
            try:
                self._conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {self._collection_name}_fts USING fts5(content, id UNINDEXED, content='{self._collection_name}', content_rowid='id');")
                self._conn.execute(f"CREATE TRIGGER IF NOT EXISTS {self._collection_name}_ai AFTER INSERT ON {self._collection_name} BEGIN INSERT INTO {self._collection_name}_fts(rowid, content, id) VALUES (new.rowid, new.content, new.id); END;")
                self._conn.execute(f"CREATE TRIGGER IF NOT EXISTS {self._collection_name}_ad AFTER DELETE ON {self._collection_name} BEGIN INSERT INTO {self._collection_name}_fts({self._collection_name}_fts, rowid, content, id) VALUES('delete', old.rowid, old.content, old.id); END;")
                self._conn.execute(f"CREATE TRIGGER IF NOT EXISTS {self._collection_name}_au AFTER UPDATE ON {self._collection_name} BEGIN INSERT INTO {self._collection_name}_fts({self._collection_name}_fts, rowid, content, id) VALUES('delete', old.rowid, old.content, old.id); INSERT INTO {self._collection_name}_fts(rowid, content, id) VALUES (new.rowid, new.content, new.id); END;")
            except sqlite3.OperationalError: pass

    def save(self, items: List[LongMemoryItem]):
        if not items or not self._conn: return
        with self._lock:
            try:
                with self._conn:
                    for item in items:
                        self._conn.execute(f"INSERT OR REPLACE INTO {self._collection_name} (id, content, metadata) VALUES (?, ?, ?)", (item.id, item.content, json.dumps(item.metadata)))
            except Exception as e: self._logger.error(f"SQLite 保存失败: {e}")

    def search(self, text, n, filter=None):
        if not self._conn: return []
        cursor = self._conn.cursor()
        try:
            query = f"SELECT id, content, metadata, bm25({self._collection_name}_fts) FROM {self._collection_name}_fts JOIN {self._collection_name} ON {self._collection_name}.rowid = {self._collection_name}_fts.rowid WHERE {self._collection_name}_fts MATCH ? LIMIT ?"
            cursor.execute(query, (text, n))
            rows = cursor.fetchall()
            return [LongMemoryItem.new(id=r[0], content=r[1], metadata=json.loads(r[2]), distance=float(r[3])) for r in rows]
        except:
            cursor.execute(f"SELECT id, content, metadata FROM {self._collection_name} WHERE content LIKE ? LIMIT ?", (f"%{text}%", n))
            return [LongMemoryItem.new(id=r[0], content=r[1], metadata=json.loads(r[2]), distance=0.0) for r in cursor.fetchall()]

    def delete(self, ids):
        with self._conn: self._conn.executemany(f"DELETE FROM {self._collection_name} WHERE id = ?", [(i,) for i in ids])
    def get_recent_history(self, n):
        cursor = self._conn.cursor(); cursor.execute(f"SELECT id, content, metadata FROM {self._collection_name} ORDER BY rowid DESC LIMIT ?", (n,))
        return [LongMemoryItem.new(id=r[0], content=r[1], metadata=json.loads(r[2]), distance=0.0) for r in cursor.fetchall()]
    def export_data(self): return []
    def import_data(self, data): pass

class RedisLongMemory(AbstractLongMemory):
    """基于 Redis 的向量存储。"""
    def __init__(self, api_key, col="long_memory_collection"):
        self._api_key, self._col = api_key, col; self.client = redis_client
        if not self.client: raise ConnectionError("Redis unavailable")
        self.index = SearchIndex.from_dict({"index":{"name":col,"prefix":f"{col}:"},"fields":[{"name":"content","type":"text"},{"name":"metadata","type":"text"},{"name":"embedding","type":"vector","attrs":{"dims":1024,"distance_metric":"cosine","algorithm":"flat"}}]}); self.index.set_client(self.client)
        if not self.client.exists(f"idx:{col}"): self.index.create(overwrite=True)
    def init(self, logger=None): pass
    def save(self, items):
        recs = []
        for it in items:
            emb = get_embedding(it.content, self._api_key)
            if emb is not None: recs.append({"id":it.id, "content":it.content, "metadata":json.dumps(it.metadata), "embedding":emb.tobytes()})
        if recs: self.index.load(recs)
    def search(self, text, n, filter=None):
        emb = get_embedding(text, self._api_key)
        if emb is None: return []
        results = self.index.query(VectorQuery(vector=emb.tobytes(), vector_field_name="embedding", return_fields=["id","content","metadata","vector_distance"], num_results=n))
        return [LongMemoryItem.new(id=d["id"], content=d["content"], metadata=json.loads(d["metadata"]), distance=float(d["vector_distance"])) for d in results]
    def delete(self, ids): pass
    def get_recent_history(self, n): return []
    def export_data(self): return []
    def import_data(self, data): pass

class ZvecLongMemory(AbstractLongMemory):
    def __init__(self, key=None, col="long_memory_zvec"): self._key, self._col, self._off = key, col, key is None; self.collection = None
    def init(self, logger=None):
        p = os.path.normpath(os.path.join(os.path.dirname(__file__), "../data/system_data/zvec_memory", self._col))
        if not os.path.exists(p): os.makedirs(p, exist_ok=True)
        self.collection = zvec.create_and_open(path=p, schema=zvec.CollectionSchema(name=self._col, vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, 1024), fields=[zvec.FieldSchema("content", zvec.DataType.STRING), zvec.FieldSchema("metadata", zvec.DataType.STRING), zvec.FieldSchema("timestamp", zvec.DataType.DOUBLE)]))
    def save(self, items): pass
    def search(self, text, n, filter=None): return []
    def delete(self, ids): pass
    def get_recent_history(self, n): return []
    def export_data(self): return []
    def import_data(self, data): pass

class DeepSeekLongMemory(AbstractLongMemory):
    def __init__(self, key): self._key, self._mem, self._embs = key, {}, {}
    def init(self, logger=None): pass
    def save(self, items): pass
    def search(self, text, n, filter=None): return []
    def delete(self, ids): pass
    def get_recent_history(self, n): return []
    def export_data(self): return []
    def import_data(self, data): pass

class HybridMemoryManager:
    """
    混合日志记忆系统（对话日志记录与查询）。
    """
    def __init__(self, root=None):
        self._logger = LogManager.get_logger(__name__)
        p_root = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
        self.root = root or os.path.join(p_root, "data", "butler_memory")
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
        full = os.path.join(self.root, path)
        if not os.path.exists(full): return ""
        with open(full, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return "".join(lines[max(0, start-1): (start-1+num if num>0 else None)])

# 全局单例 (保持日志系统独立实例)
hybrid_memory_manager = HybridMemoryManager()

class UnifiedMemoryEngine:
    """
    统一记忆引擎：整合两套独立运行的记忆系统。
    实现“事实数据库”与“原始对话日志”之间的相互独立运行与数据共享。
    """
    def __init__(self, fact_db: AbstractLongMemory, log_sys: HybridMemoryManager):
        self.fact_db = fact_db # 独立的事实数据库系统
        self.logs = log_sys     # 独立的原始对话日志系统
        self._logger = LogManager.get_logger(__name__)

    def init(self, logger=None):
        if logger: self._logger = logger
        self.fact_db.init(self._logger)

    def record_interaction(self, user_cmd: str, assistant_resp: str):
        """记录交互：数据共享。"""
        # 1. 存入日志系统（记录原始上下文）
        self.logs.add_daily_log(f"User: {user_cmd}\nAssistant: {assistant_resp}")

        # 2. 存入事实数据库（结构化存储助手回复）
        item = LongMemoryItem.new(content=assistant_resp, id=f"resp_{int(time.time()*1000)}", metadata={"role": "assistant", "cmd": user_cmd, "ts": time.time()})
        self.fact_db.save([item])

    def save_fact(self, content: str, metadata: dict = None):
        """数据共享：将新发现的事实同时存入数据库和日志。"""
        metadata = metadata or {}
        item = LongMemoryItem.new(content=content, id=f"fact_{int(time.time()*1000)}", metadata=metadata)
        self.fact_db.save([item])
        self.logs.add_daily_log(f"[Fact Added] {content}")

    def unified_search(self, query: str, n: int = 5) -> List[Dict[str, Any]]:
        """强力搜索：跨系统数据共享搜索。"""
        f_results = self.fact_db.search(query, n)
        l_results = self.logs.search(query, n)

        combined = []
        for r in f_results: combined.append({"src": "fact_db", "content": r.content, "score": r.distance})
        for r in l_results:
            c = r.get("content", "") if isinstance(r, dict) else str(r)
            combined.append({"src": "logs", "content": c, "score": 0.5})
        return sorted(combined, key=lambda x: x["score"])

    # 代理事实数据库的方法
    def search(self, text, n, filter=None): return self.fact_db.search(text, n, filter)
    def save(self, items): self.fact_db.save(items)
    def delete(self, ids): self.fact_db.delete(ids)
    def get_recent_history(self, n): return self.fact_db.get_recent_history(n)
