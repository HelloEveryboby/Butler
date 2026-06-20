import os
import requests
import numpy as np
import hashlib
from typing import Optional, List
from package.core_utils.log_manager import LogManager
from package.core_utils.config_loader import config_loader

logger = LogManager.get_logger(__name__)

DEEPSEEK_API_URL = config_loader.get("api.deepseek.endpoint", "https://api.deepseek.com/v1") + "/embeddings"
EMBEDDING_MODEL = "deepseek-coder"

def get_embedding(text: str, api_key: str = None, offline: bool = False) -> Optional[np.ndarray]:
    """
    获取向量嵌入。支持在线 (DeepSeek) 和离线 (简单哈希 fallback) 模式。
    """
    if not offline and api_key:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json={"input": text, "model": EMBEDDING_MODEL},
                timeout=10
            )
            response.raise_for_status()
            embedding_data = response.json()['data'][0]['embedding']
            return np.array(embedding_data, dtype=np.float32)
        except Exception as e:
            logger.warning(f"在线 Embedding 失败，尝试切换到离线模式: {e}")

    # 离线模式或在线失败后的 Fallback: 简单哈希向量化 (1024维)
    return _get_simple_local_embedding(text)

def _get_simple_local_embedding(text: str, dimension: int = 1024) -> np.ndarray:
    """
    一个简单的离线向量化方案：基于字符 N-gram 的哈希投影。
    虽然语义性能不如神经网络，但完全不需要联网，速度极快。
    """
    vec = np.zeros(dimension, dtype=np.float32)
    # 使用滑动窗口获取字符 N-gram
    n = 3
    for i in range(len(text) - n + 1):
        ngram = text[i:i+n]
        # 使用 hash 将 ngram 映射到维度空间
        h = int(hashlib.md5(ngram.encode('utf-8')).hexdigest(), 16)
        vec[h % dimension] += 1.0

    # 归一化
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm

    return vec
