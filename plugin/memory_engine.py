import logging
import os
import sqlite3
import json
import ast
import threading
import time
from abc import ABCMeta, abstractmethod
from typing import List, Dict, Optional, Tuple, Any

from package.core_utils.log_manager import LogManager
from package.core_utils.embedding_utils import get_embedding

# Optional dependencies
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

class LongMemoryItem:
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
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "distance": self.distance
        }

class AbstractLongMemory(metaclass=ABCMeta):
    @abstractmethod
    def init(self, logger: logging.Logger = None):
        pass

    @abstractmethod
    def save(self, items: List[LongMemoryItem]):
        pass

    @abstractmethod
    def search(self, text: str, n_results: int, metadata_filter: Optional[dict] = None) -> List[LongMemoryItem]:
        pass

    @abstractmethod
    def delete(self, ids: List[str]):
        pass

    @abstractmethod
    def get_recent_history(self, n_results: int) -> List[LongMemoryItem]:
        pass

    @abstractmethod
    def export_data(self) -> List[dict]:
        """Export all data as a list of dictionaries for migration."""
        pass

    @abstractmethod
    def import_data(self, data: List[dict]):
        """Import data from a list of dictionaries."""
        pass

class SQLiteLongMemory(AbstractLongMemory):
    def __init__(self, collection_name: str = "long_memory_collection", cache_size: int = 100):
        self._logger = LogManager.get_logger(__name__)
        self._conn: Optional[sqlite3.Connection] = None

        if not collection_name.replace('_', '').isalnum():
            raise ValueError(f"Invalid collection name: {collection_name}. Must be alphanumeric.")
        self._collection_name = collection_name

        self._cache: Dict[Tuple[str, int, Optional[frozenset]], List[LongMemoryItem]] = {}
        self._cache_size = cache_size
        self._lock = threading.Lock()

    def init(self, logger: logging.Logger = None):
        if logger: self._logger = logger

        # Consistent path resolution
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, "../data/system_data/long_memory.db")

        try:
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._create_table()
            self._create_index()
            self._logger.info("SQLiteLongMemory initialized.")
        except Exception as e:
            self._logger.error(f"Failed to initialize SQLiteLongMemory: {e}")
            raise

    def _create_table(self):
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self._collection_name} (
            id TEXT PRIMARY KEY,
            content TEXT,
            metadata TEXT
        );
        """
        if self._conn:
            with self._conn:
                self._conn.execute(create_table_sql)

    def _create_index(self):
        create_index_sql = f"""
        CREATE INDEX IF NOT EXISTS idx_content ON {self._collection_name} (content);
        """
        if self._conn:
            with self._conn:
                self._conn.execute(create_index_sql)

    def save(self, items: List[LongMemoryItem]):
        if not items or not self._conn:
            return

        with self._lock:
            # deduplication logic: if similar content exists, delete it first
            to_delete_ids = []
            for item in items:
                old_memories = self.search(text=item.content, n_results=5)
                # Note: distance is not really calculated in simple SQLite search,
                # but we keep the logic structure if distance is available.
                to_delete_ids.extend([old_memory.id for old_memory in old_memories if old_memory.distance is not None and old_memory.distance < 0.2])

            if to_delete_ids:
                self.delete(to_delete_ids)

            try:
                with self._conn:
                    for item in items:
                        self._conn.execute(f"""
                        INSERT OR REPLACE INTO {self._collection_name} (id, content, metadata) VALUES (?, ?, ?)
                        """, (item.id, item.content, json.dumps(item.metadata)))
                self._update_cache(items)
            except Exception as e:
                self._logger.error(f"Failed to save items to SQLite: {e}")

    def search(self, text: str, n_results: int, metadata_filter: Optional[Dict[str, str]] = None) -> List[LongMemoryItem]:
        cache_key = (text, n_results, frozenset(metadata_filter.items()) if metadata_filter else None)

        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        if not self._conn:
            return []

        try:
            cursor = self._conn.cursor()
            if metadata_filter:
                filter_conditions = []
                filter_values = []
                for key, value in metadata_filter.items():
                    filter_conditions.append("json_extract(metadata, ?) = ?")
                    filter_values.extend([f"$.{key}", value])

                filter_sql = " AND ".join(filter_conditions)
                query = f"SELECT id, content, metadata FROM {self._collection_name} WHERE content LIKE ? AND {filter_sql} LIMIT ?"
                cursor.execute(query, (f"%{text}%", *filter_values, n_results))
            else:
                query = f"SELECT id, content, metadata FROM {self._collection_name} WHERE content LIKE ? LIMIT ?"
                cursor.execute(query, (f"%{text}%", n_results))

            rows = cursor.fetchall()
            items = []
            for row in rows:
                metadata = self._parse_metadata(row[2])
                items.append(LongMemoryItem.new(content=row[1], metadata=metadata, id=row[0]))

            with self._lock:
                if len(self._cache) >= self._cache_size:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[cache_key] = items

            return items
        except Exception as e:
            self._logger.error(f"SQLiteLongMemory search failed: {e}")
            return []

    def get_recent_history(self, n_results: int) -> List[LongMemoryItem]:
        if not self._conn: return []
        try:
            cursor = self._conn.cursor()
            query = f"SELECT id, content, metadata FROM {self._collection_name} ORDER BY rowid DESC LIMIT ?"
            cursor.execute(query, (n_results,))
            rows = cursor.fetchall()
            return [LongMemoryItem.new(content=row[1], metadata=self._parse_metadata(row[2]), id=row[0]) for row in rows]
        except Exception as e:
            self._logger.error(f"Failed to get recent history from SQLite: {e}")
            return []

    def delete(self, ids: List[str]):
        if not ids or not self._conn: return
        try:
            with self._conn:
                self._conn.executemany(f"DELETE FROM {self._collection_name} WHERE id = ?", [(i,) for i in ids])
            self._invalidate_cache(ids)
        except Exception as e:
            self._logger.error(f"Failed to delete from SQLite: {e}")

    def export_data(self) -> List[dict]:
        if not self._conn: return []
        try:
            cursor = self._conn.cursor()
            cursor.execute(f"SELECT id, content, metadata FROM {self._collection_name}")
            return [{"id": r[0], "content": r[1], "metadata": self._parse_metadata(r[2])} for r in cursor.fetchall()]
        except Exception as e:
            self._logger.error(f"Failed to export SQLite data: {e}")
            return []

    def import_data(self, data: List[dict]):
        items = [LongMemoryItem.new(content=d["content"], id=d["id"], metadata=d["metadata"]) for d in data]
        if items: self.save(items)

    def _parse_metadata(self, metadata_str: str) -> dict:
        try:
            return json.loads(metadata_str)
        except Exception:
            try: return ast.literal_eval(metadata_str)
            except Exception: return {}

    def _update_cache(self, items: List[LongMemoryItem]):
        for item in items:
            cache_key = (item.content, 1, frozenset(item.metadata.items()))
            self._cache[cache_key] = [item]

    def _invalidate_cache(self, ids: List[str]):
        keys_to_remove = [k for k, v in self._cache.items() if any(item.id in ids for item in v)]
        for key in keys_to_remove:
            del self._cache[key]

class RedisLongMemory(AbstractLongMemory):
    def __init__(self, api_key: str, collection_name: str = "long_memory_collection"):
        self._logger = LogManager.get_logger(__name__)
        if not redis:
            raise ImportError("Redis dependencies not installed. Please install 'redis' and 'redisvl'.")
        if not api_key:
            raise ValueError("DeepSeek API key is required.")
        self._api_key = api_key
        self._collection_name = collection_name
        self.redis_client = redis_client
        if not self.redis_client:
            raise ConnectionError("Failed to connect to Redis.")

        schema = {
            "index": {"name": self._collection_name, "prefix": f"{self._collection_name}:"},
            "fields": [
                {"name": "content", "type": "text"},
                {"name": "metadata", "type": "text"},
                {
                    "name": "embedding",
                    "type": "vector",
                    "attrs": {"dims": 1024, "distance_metric": "cosine", "algorithm": "flat"}
                }
            ]
        }
        self.index = SearchIndex.from_dict(schema)
        self.index.set_client(self.redis_client)
        if not self.redis_client.exists(f"idx:{self._collection_name}"):
            self.index.create(overwrite=True)

        self._logger.info("RedisLongMemory initialized.")

    def init(self, logger: logging.Logger = None):
        if logger: self._logger = logger
        # Basic health check via embedding utility
        if get_embedding("test", self._api_key) is not None:
            self._logger.info("RedisLongMemory health check successful.")

    def save(self, items: List[LongMemoryItem]):
        records = []
        for item in items:
            emb = get_embedding(item.content, self._api_key)
            if emb is not None:
                record = {
                    "id": item.id,
                    "content": item.content,
                    "metadata": json.dumps(item.metadata),
                    "embedding": emb.tobytes()
                }
                records.append(record)
            else:
                self._logger.warning(f"Embedding failure for item {item.id}")

        if records:
            self.index.load(records)
            for record in records:
                ts = json.loads(record['metadata']).get('timestamp', time.time())
                self.redis_client.zadd(f"{self._collection_name}:history", {record['id']: ts})
            self._logger.info(f"Saved {len(records)} items to Redis.")

    def search(self, text: str, n_results: int, metadata_filter: Optional[Dict[str, str]] = None) -> List[LongMemoryItem]:
        emb = get_embedding(text, self._api_key)
        if emb is None: return []

        query = VectorQuery(
            vector=emb.tobytes(),
            vector_field_name="embedding",
            return_fields=["id", "content", "metadata", "vector_distance"],
            num_results=n_results,
        )
        # RedisVL filter support could be added here if needed via query.set_filter()
        results = self.index.query(query)
        return [LongMemoryItem.new(id=doc["id"], content=doc["content"],
                                   metadata=json.loads(doc["metadata"]),
                                   distance=float(doc["vector_distance"])) for doc in results]

    def delete(self, ids: List[str]):
        for item_id in ids:
            key = f"{self._collection_name}:{item_id}"
            self.redis_client.delete(key)
            self.redis_client.zrem(f"{self._collection_name}:history", item_id)

    def get_recent_history(self, n_results: int) -> List[LongMemoryItem]:
        recent_ids = self.redis_client.zrevrange(f"{self._collection_name}:history", 0, n_results - 1)
        items = []
        for item_id in recent_ids:
            item_data = self.redis_client.hgetall(f"{self._collection_name}:{item_id.decode() if isinstance(item_id, bytes) else item_id}")
            if item_data:
                items.append(LongMemoryItem.new(
                    id=item_id.decode() if isinstance(item_id, bytes) else item_id,
                    content=item_data.get(b"content", b"").decode(),
                    metadata=json.loads(item_data.get(b"metadata", b"{}").decode()),
                    distance=0
                ))
        return items

    def export_data(self) -> List[dict]:
        data = []
        try:
            cursor = 0
            prefix = f"{self._collection_name}:"
            while True:
                cursor, keys = self.redis_client.scan(cursor=cursor, match=f"{prefix}*", count=100)
                for key in keys:
                    if self.redis_client.type(key) == b'hash':
                        hdata = self.redis_client.hgetall(key)
                        data.append({
                            "id": key.decode().replace(prefix, ""),
                            "content": hdata.get(b"content", b"").decode(),
                            "metadata": json.loads(hdata.get(b"metadata", b"{}").decode())
                        })
                if cursor == 0: break
        except Exception as e:
            self._logger.error(f"Redis export failed: {e}")
        return data

    def import_data(self, data: List[dict]):
        items = [LongMemoryItem.new(content=d["content"], id=d["id"], metadata=d["metadata"]) for d in data]
        if items: self.save(items)

class ZvecLongMemory(AbstractLongMemory):
    def __init__(self, api_key: str = None, collection_name: str = "long_memory_zvec"):
        self._logger = LogManager.get_logger(__name__)
        if not zvec:
            raise ImportError("zvec library not installed or incompatible.")
        self._api_key = api_key
        self._collection_name = collection_name
        self._offline = (api_key is None)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._data_path = os.path.join(base_dir, "../data/system_data/zvec_memory", collection_name)
        self.collection = None

    def init(self, logger: logging.Logger = None):
        if logger: self._logger = logger
        if not os.path.exists(self._data_path):
            os.makedirs(self._data_path, exist_ok=True)

        try:
            schema = zvec.CollectionSchema(
                name=self._collection_name,
                vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, 1024),
                fields=[
                    zvec.FieldSchema("content", zvec.DataType.STRING),
                    zvec.FieldSchema("metadata", zvec.DataType.STRING),
                    zvec.FieldSchema("timestamp", zvec.DataType.DOUBLE)
                ]
            )
            self.collection = zvec.create_and_open(path=self._data_path, schema=schema)
            self._logger.info(f"ZvecLongMemory initialized at {self._data_path}")
        except Exception as e:
            self._logger.error(f"ZvecLongMemory initialization failed: {e}")
            raise

    def save(self, items: List[LongMemoryItem]):
        if not self.collection: return
        docs = []
        for item in items:
            emb = get_embedding(item.content, self._api_key, offline=self._offline)
            if emb is not None:
                doc = zvec.Doc(
                    id=item.id if item.id else f"mem_{int(time.time() * 1000)}",
                    vectors={"embedding": emb.tolist()},
                    fields={
                        "content": item.content,
                        "metadata": json.dumps(item.metadata),
                        "timestamp": item.metadata.get("timestamp", time.time())
                    }
                )
                docs.append(doc)
        if docs:
            self.collection.insert(docs)
            self._logger.info(f"Saved {len(docs)} items to Zvec.")

    def search(self, text: str, n_results: int, metadata_filter: Optional[Dict[str, str]] = None) -> List[LongMemoryItem]:
        if not self.collection: return []
        emb = get_embedding(text, self._api_key, offline=self._offline)
        if emb is None: return []

        query = zvec.VectorQuery(field_name="embedding", vector=emb.tolist())
        try:
            results = self.collection.query(vectors=query, topk=n_results)
            return [LongMemoryItem.new(id=doc.id, content=doc.field("content"),
                                       metadata=json.loads(doc.field("metadata")),
                                       distance=doc.score) for doc in results]
        except Exception as e:
            self._logger.error(f"Zvec search failed: {e}")
            return []

    def delete(self, ids: List[str]):
        # Zvec may have limited support for direct deletion by ID depending on version
        # Placeholder for version that supports it
        pass

    def get_recent_history(self, n_results: int) -> List[LongMemoryItem]:
        return [] # Placeholder

    def export_data(self) -> List[dict]:
        self._logger.warning("Zvec export not fully implemented.")
        return []

    def import_data(self, data: List[dict]):
        items = [LongMemoryItem.new(content=d["content"], id=d["id"], metadata=d["metadata"]) for d in data]
        if items: self.save(items)

class DeepSeekLongMemory(AbstractLongMemory):
    """In-memory vector store using DeepSeek embeddings and Cosine Similarity."""
    def __init__(self, api_key: str):
        self._logger = LogManager.get_logger(__name__)
        if np is None:
            raise ImportError("numpy is required for DeepSeekLongMemory.")
        self._api_key = api_key
        self._memory: Dict[str, LongMemoryItem] = {}
        self._embeddings: Dict[str, Any] = {}

    def init(self, logger: logging.Logger = None):
        if logger: self._logger = logger
        if get_embedding("test", self._api_key) is not None:
            self._logger.info("DeepSeekLongMemory health check successful.")

    def save(self, items: List[LongMemoryItem]):
        for item in items:
            emb = get_embedding(item.content, self._api_key)
            if emb is not None:
                self._memory[item.id] = item
                self._embeddings[item.id] = emb
            else:
                self._logger.warning(f"Embedding failure for {item.id}")

    def search(self, text: str, n_results: int, metadata_filter: Optional[Dict[str, str]] = None) -> List[LongMemoryItem]:
        query_emb = get_embedding(text, self._api_key)
        if query_emb is None or not self._embeddings: return []

        candidate_ids = list(self._memory.keys())
        if metadata_filter:
            candidate_ids = [cid for cid in candidate_ids if all(self._memory[cid].metadata.get(k) == v for k, v in metadata_filter.items())]

        if not candidate_ids: return []

        # Cosine Similarity
        c_embs = np.array([self._embeddings[cid] for cid in candidate_ids])
        sims = np.dot(c_embs, query_emb) / (np.linalg.norm(c_embs, axis=1) * np.linalg.norm(query_emb))
        top_indices = np.argsort(sims)[-n_results:][::-1]

        results = []
        for i in top_indices:
            cid = candidate_ids[i]
            item = self._memory[cid]
            item.distance = float(1 - sims[i])
            results.append(item)
        return results

    def delete(self, ids: List[str]):
        for cid in ids:
            self._memory.pop(cid, None)
            self._embeddings.pop(cid, None)

    def get_recent_history(self, n_results: int) -> List[LongMemoryItem]:
        return list(self._memory.values())[-n_results:]

    def export_data(self) -> List[dict]:
        return [item.to_dict() for item in self._memory.values()]

    def import_data(self, data: List[dict]):
        items = [LongMemoryItem.new(content=d["content"], id=d["id"], metadata=d["metadata"]) for d in data]
        if items: self.save(items)
