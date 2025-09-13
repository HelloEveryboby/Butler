import os
import requests
import numpy as np
from typing import List, Dict, Optional
from ..long_memory.long_memory_interface import AbstractLongMemory, LongMemoryItem
from package.log_manager import LogManager

DEEPSEEK_API_URL = "https://api.deepseek.com/v1/embeddings"

class DeepSeekLongMemory(AbstractLongMemory):
    def __init__(self, api_key: str, collection_name: str = "long_memory_collection"):
        self._logger = LogManager.get_logger(__name__)
        if not api_key:
            raise ValueError("DeepSeek API key is required.")
        self._api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }
        self._collection_name = collection_name
        self._memory: Dict[str, LongMemoryItem] = {}
        self._embeddings: Dict[str, np.ndarray] = {}
        self._logger.info("DeepSeekLongMemory initialized.")

    def init(self, logger: LogManager):
        self._logger = logger
        try:
            # Perform a test request to check API key and connectivity
            response = requests.post(DEEPSEEK_API_URL, headers=self._headers, json={"input": "test", "model": "deepseek-coder"})
            response.raise_for_status()
            self._logger.info("DeepSeek API health check successful.")
        except requests.exceptions.RequestException as e:
            self._logger.error(f"DeepSeek API health check failed: {e}")
            raise ConnectionError("Failed to connect to DeepSeek API.") from e

    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generates an embedding for the given text using the DeepSeek API."""
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=self._headers,
                json={"input": text, "model": "deepseek-coder"}
            )
            response.raise_for_status()
            embedding_data = response.json()['data'][0]['embedding']
            return np.array(embedding_data)
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Failed to get embedding from DeepSeek API: {e}")
        except (KeyError, IndexError) as e:
            self._logger.error(f"Unexpected response format from DeepSeek API: {e}")
        return None

    def save(self, items: List[LongMemoryItem]):
        """Saves items to memory after generating embeddings for their content."""
        for item in items:
            embedding = self._get_embedding(item.content)
            if embedding is not None:
                self._memory[item.id] = item
                self._embeddings[item.id] = embedding
                self._logger.info(f"Saved item {item.id} to DeepSeekLongMemory.")
            else:
                self._logger.warning(f"Failed to save item {item.id} due to embedding failure.")

    def search(self, text: str, n_results: int, metadata_filter: Optional[Dict[str, str]] = None) -> List[LongMemoryItem]:
        """Searches for items in memory based on semantic similarity."""
        query_embedding = self._get_embedding(text)
        if query_embedding is None:
            return []

        # Filter items by metadata if a filter is provided
        candidate_ids = list(self._memory.keys())
        if metadata_filter:
            candidate_ids = [
                id for id in candidate_ids
                if all(self._memory[id].metadata.get(k) == v for k, v in metadata_filter.items())
            ]

        if not candidate_ids:
            return []

        # Calculate cosine similarity
        candidate_embeddings = np.array([self._embeddings[id] for id in candidate_ids])
        similarities = np.dot(candidate_embeddings, query_embedding) / (
            np.linalg.norm(candidate_embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Get top n_results
        top_indices = np.argsort(similarities)[-n_results:][::-1]

        results = []
        for i in top_indices:
            item_id = candidate_ids[i]
            item = self._memory[item_id]
            item.distance = float(1 - similarities[i])  # Convert similarity to distance
            results.append(item)

        return results

    def delete(self, ids: List[str]):
        """Deletes items from memory."""
        for item_id in ids:
            if item_id in self._memory:
                del self._memory[item_id]
                if item_id in self._embeddings:
                    del self._embeddings[item_id]
                self._logger.info(f"Deleted item {item_id} from DeepSeekLongMemory.")
