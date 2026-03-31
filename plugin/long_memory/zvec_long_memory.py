import os
import json
import time
from typing import List, Dict, Optional
from .long_memory_interface import AbstractLongMemory, LongMemoryItem
from package.core_utils.log_manager import LogManager
from package.core_utils.embedding_utils import get_embedding


class ZvecLongMemory(AbstractLongMemory):
    """
    使用 zvec 实现的高性能本地向量存储。
    支持联网 (DeepSeek) 和完全离线模式。
    """

    def __init__(self, api_key: str = None, collection_name: str = "long_memory_zvec"):
        self._logger = LogManager.get_logger(__name__)
        self._api_key = api_key
        self._collection_name = collection_name
        self._offline = api_key is None

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self._data_path = os.path.join(
            base_dir, "../../data/system_data/zvec_memory", collection_name
        )
        self.collection = None

    def init(self, logger=None):
        if logger:
            self._logger = logger

        try:
            import zvec
        except (ImportError, RuntimeError, Exception) as e:
            self._logger.error(f"zvec 库加载失败 (可能由于硬件不兼容或未安装): {e}")
            raise RuntimeError(f"zvec is not available: {e}")

        if not os.path.exists(self._data_path):
            os.makedirs(self._data_path, exist_ok=True)

        try:
            schema = zvec.CollectionSchema(
                name=self._collection_name,
                vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, 1024),
                fields=[
                    zvec.FieldSchema("content", zvec.DataType.STRING),
                    zvec.FieldSchema("metadata", zvec.DataType.STRING),
                    zvec.FieldSchema("timestamp", zvec.DataType.DOUBLE),
                ],
            )
            self.collection = zvec.create_and_open(path=self._data_path, schema=schema)
            mode_str = "离线" if self._offline else "在线"
            self._logger.info(
                f"ZvecLongMemory ({mode_str}模式) 初始化成功: {self._data_path}"
            )
        except Exception as e:
            self._logger.error(f"ZvecLongMemory 初始化失败: {e}")
            raise

    def save(self, items: List[LongMemoryItem]):
        if not self.collection:
            return
        import zvec

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
                        "timestamp": item.metadata.get("timestamp", time.time()),
                    },
                )
                docs.append(doc)

        if docs:
            self.collection.insert(docs)
            self._logger.info(f"已保存 {len(docs)} 条记忆到 ZvecLongMemory。")

    def search(
        self,
        text: str,
        n_results: int,
        metadata_filter: Optional[Dict[str, str]] = None,
    ) -> List[LongMemoryItem]:
        if not self.collection:
            return []
        import zvec

        emb = get_embedding(text, self._api_key, offline=self._offline)
        if emb is None:
            return []

        query = zvec.VectorQuery(field_name="embedding", vector=emb.tolist())
        try:
            results = self.collection.query(vectors=query, topk=n_results)

            long_memory_items = []
            for doc in results:
                item = LongMemoryItem.new(
                    id=doc.id,
                    content=doc.field("content"),
                    metadata=json.loads(doc.field("metadata")),
                    distance=doc.score,
                )
                long_memory_items.append(item)

            return long_memory_items
        except Exception as e:
            self._logger.error(f"Zvec 搜索出错: {e}")
            return []

    def export_data(self) -> List[dict]:
        """Export all data from Zvec collection."""
        if not self.collection:
            return []
        data = []
        try:
            # Zvec also doesn't have a direct export, so we query with a broad scope if possible
            # or use internal iterator if available. Assuming we can't easily,
            # this is a placeholder for actual zvec export logic.
            self._logger.warning("Zvec export not fully implemented.")
        except Exception as e:
            self._logger.error(f"Failed to export data from Zvec: {e}")
        return data

    def import_data(self, data: List[dict]):
        """Import data into Zvec."""
        items = []
        for d in data:
            item = LongMemoryItem.new(
                content=d["content"], id=d["id"], metadata=d["metadata"]
            )
            items.append(item)
        if items:
            self.save(items)

    def get_recent_history(self, n_results: int) -> List[LongMemoryItem]:
        # Implementation for Zvec history if needed
        return []
