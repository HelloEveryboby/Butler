import json
import numpy as np
import redis
from typing import List, Dict, Optional

from butler.redis_client import redis_client
from ..long_memory.long_memory_interface import AbstractLongMemory, LongMemoryItem
from package.core_utils.log_manager import LogManager
from redisvl.index import SearchIndex
from redisvl.query import VectorQuery
from package.core_utils.embedding_utils import get_embedding

class RedisLongMemory(AbstractLongMemory):
    def __init__(self, api_key: str, collection_name: str = "long_memory_collection"):
        self._logger = LogManager.get_logger(__name__)
        if not api_key:
            raise ValueError("DeepSeek API key is required.")
        self._api_key = api_key
        self._collection_name = collection_name
        self.redis_client = redis_client
        if not self.redis_client:
            raise ConnectionError("Failed to connect to Redis.")

        # Define the schema for the search index
        schema = {
            "index": {
                "name": self._collection_name,
                "prefix": f"{self._collection_name}:",
            },
            "fields": [
                {"name": "content", "type": "text"},
                {"name": "metadata", "type": "text"},
                {
                    "name": "embedding",
                    "type": "vector",
                    "attrs": {
                        "dims": 1024,
                        "distance_metric": "cosine",
                        "algorithm": "flat",
                    }
                }
            ]
        }
        self.index = SearchIndex.from_dict(schema)
        self.index.set_client(self.redis_client)
        if not self.redis_client.exists(f"idx:{self._collection_name}"):
            self.index.create(overwrite=True)

        self._logger.info("RedisLongMemory initialized.")

    def init(self, logger: LogManager):
        self._logger = logger
        # Health check moved to simple embedding test
        emb = get_embedding("test", self._api_key)
        if emb is not None:
            self._logger.info("DeepSeek API health check successful.")
        else:
            self._logger.error("DeepSeek API health check failed.")

    def save(self, items: List[LongMemoryItem]):
        """Saves items to Redis after generating embeddings for their content."""
        records = []
        for item in items:
            embedding = get_embedding(item.content, self._api_key)
            if embedding is not None:
                record = {
                    "id": item.id,
                    "content": item.content,
                    "metadata": json.dumps(item.metadata),
                    "embedding": embedding.tobytes()
                }
                records.append(record)
            else:
                self._logger.warning(f"Failed to save item {item.id} due to embedding failure.")

        if records:
            self.index.load(records)
            for record in records:
                timestamp = json.loads(record['metadata']).get('timestamp', 0)
                self.redis_client.zadd(f"{self._collection_name}:history", {record['id']: timestamp})
            self._logger.info(f"Saved {len(records)} items to RedisLongMemory.")


    def search(self, text: str, n_results: int, metadata_filter: Optional[Dict[str, str]] = None) -> List[LongMemoryItem]:
        """Searches for items in Redis based on semantic similarity."""
        query_embedding = get_embedding(text, self._api_key)
        if query_embedding is None:
            return []

        query = VectorQuery(
            vector=query_embedding.tobytes(),
            vector_field_name="embedding",
            return_fields=["id", "content", "metadata", "vector_distance"],
            num_results=n_results,
        )

        results = self.index.query(query)

        long_memory_items = []
        for doc in results:
            item = LongMemoryItem.new(
                id=doc["id"],
                content=doc["content"],
                metadata=json.loads(doc["metadata"]),
                distance=float(doc["vector_distance"])
            )
            long_memory_items.append(item)

        return long_memory_items

    def get_recent_history(self, n_results: int) -> List[LongMemoryItem]:
        """Retrieves the most recent items from memory."""
        recent_ids = self.redis_client.zrevrange(f"{self._collection_name}:history", 0, n_results - 1)

        long_memory_items = []
        for item_id in recent_ids:
            item_key = f"{self._collection_name}:{item_id}"
            item_data = self.redis_client.hgetall(item_key)
            if item_data:
                item = LongMemoryItem.new(
                    id=item_id,
                    content=item_data["content"],
                    metadata=json.loads(item_data["metadata"]),
                    distance=0
                )
                long_memory_items.append(item)

        return long_memory_items
