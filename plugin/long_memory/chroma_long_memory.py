import sqlite3
import os
import threading
from typing import List, Dict, Optional, Tuple
from .long_memory_interface import AbstractLongMemory, LongMemoryItem
from package.log_manager import LogManager

# 系统数据路径
SYSTEM_DATA_PATH = "./data/system_data"
# 默认集合名称
DEFAULT_COLLECTION_NAME = "long_memory_collection"
# 数据库文件名称
DATABASE_FILE_NAME = "long_memory.db"

class SQLiteLongMemory(AbstractLongMemory):
    def __init__(self, collection_name: str = DEFAULT_COLLECTION_NAME, cache_size: int = 100):
        # 初始化日志记录器
        self._logger = LogManager.get_logger(__name__)
        # 初始化集合为 None
        self._conn: Optional[sqlite3.Connection] = None
        # 使用提供的集合名称（或默认值）
        self._collection_name = collection_name
        # 初始化缓存字典
        self._cache: Dict[Tuple[str, int, Optional[frozenset]], List[LongMemoryItem]] = {}
        # 缓存大小限制
        self._cache_size = cache_size
        # 初始化线程锁以确保线程安全
        self._lock = threading.Lock()

    def init(self):
        # 持久化数据目录
        db_path = os.path.join(os.path.split(os.path.abspath(__file__))[0], "../../", SYSTEM_DATA_PATH, DATABASE_FILE_NAME)

        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self._conn = sqlite3.connect(db_path)
            self._create_table()
            # 创建索引以优化查询性能
            self._create_index()
            # 进行一次搜索以确保初始化正常
            self._logger.info("初始化 SQLiteLongMemory...")
            self.search(text="init message", n_results=1)
            self._logger.info("SQLiteLongMemory 初始化成功")
        except Exception as e:
            # 记录初始化失败信息
            self._logger.error(f"初始化 SQLiteLongMemory 失败: {e}")
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
            to_delete_ids = []

            for item in items:
                old_memories = self.search(text=item.content, n_results=5)
                to_delete_ids.extend([old_memory.id for old_memory in old_memories if old_memory.distance < 0.2])

            if to_delete_ids:
                self.delete(to_delete_ids)
            try:
                with self._conn:
                    for item in items:
                        self._conn.execute(f"""
                        INSERT INTO {self._collection_name} (id, content, metadata) VALUES (?, ?, ?)
                        """, (item.id, item.content, str(item.metadata)))
                self._update_cache(items)
            except Exception as e:
                self._logger.error(f"保存项到 SQLiteLongMemory 失败: {e}")

    def search(self, text: str, n_results: int, metadata_filter: Optional[Dict[str, str]] = None) -> List[LongMemoryItem]:
        cache_key = (text, n_results, frozenset(metadata_filter.items()) if metadata_filter else None)

        with self._lock:
            if cache_key in self._cache:
                self._logger.info(f"缓存命中键: {cache_key}")
                return self._cache[cache_key]

        if not self._conn:
            return []

        try:
            cursor = self._conn.cursor()
            if metadata_filter:
                # 使用元数据过滤
                filter_conditions = " AND ".join([f"json_extract(metadata, '$.{key}') = ?" for key in metadata_filter.keys()])
                filter_values = list(metadata_filter.values())
                query = f"""
                SELECT id, content, metadata FROM {self._collection_name}
                WHERE content LIKE ? AND {filter_conditions}
                LIMIT ?
                """
                cursor.execute(query, (f"%{text}%", *filter_values, n_results))
            else:
                query = f"""
                SELECT id, content, metadata FROM {self._collection_name}
                WHERE content LIKE ?
                LIMIT ?
                """
                cursor.execute(query, (f"%{text}%", n_results))

            rows = cursor.fetchall()
            # 初始化结果项
            items = [LongMemoryItem.new(content=row[1], metadata=eval(row[2]), id=row[0]) for row in rows]

            with self._lock:
                # 更新缓存，如果缓存满了，删除最旧的项
                if len(self._cache) >= self._cache_size:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[cache_key] = items

            return items
        except Exception as e:
            self._logger.error(f"SQLiteLongMemory 搜索失败: {e}")
            return []

    def delete(self, ids: List[str]):
        if not ids or not self._conn:
            return
        try:
            with self._conn:
                self._conn.executemany(f"""
                DELETE FROM {self._collection_name} WHERE id = ?
                """, [(id,) for id in ids])
            # 从集合中删除指定的项    
            self._invalidate_cache(ids)
        except Exception as e:
            # 记录删除失败信息
            self._logger.error(f"从 SQLiteLongMemory 删除项失败: {e}")

    def _update_cache(self, items: List[LongMemoryItem]):
        # 更新缓存
        for item in items:
            cache_key = (item.content, 1, frozenset(item.metadata.items()))
            self._cache[cache_key] = [item]

    def _invalidate_cache(self, ids: List[str]):
        # 使缓存中的项失效
        keys_to_remove = [k for k, v in self._cache.items() if any(item.id in ids for item in v)]
        for key in keys_to_remove:
            if any(item.id in ids for item in self._cache.get(key, [])):
                del self._cache[key]
        if keys_to_remove:
            self._logger.info(f"缓存中的项已失效: {keys_to_remove}")