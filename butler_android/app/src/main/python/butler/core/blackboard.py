import time
import threading
import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger("Blackboard")

class BlackboardData:
    """带有生命周期的黑板数据项"""
    def __init__(self, value: Any, ttl: float):
        self.value = value
        self.expires_at = time.time() + ttl

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

class EphemeralBlackboard:
    """
    临时态“沙盒黑板”状态交换中心 (ESB)。
    用于在技能间安全、高效地共享临时状态和传递数据。
    """
    _instance = None

    def __init__(self):
        self.store: Dict[str, BlackboardData] = {}
        self.lock = threading.RLock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = EphemeralBlackboard()
        return cls._instance

    def write(self, key: str, value: Any, ttl: float = 60.0):
        """
        向黑板写入数据。
        :param key: 数据的键
        :param value: 数据的值 (应为 JSON 可序列化)
        :param ttl: 生存时间 (秒)
        """
        with self.lock:
            self.store[key] = BlackboardData(value, ttl)
            logger.debug(f"Blackboard write: {key} (TTL: {ttl}s)")

    def read_snapshot(self, key: str) -> Optional[Any]:
        """
        读取数据的快照（只读）。
        """
        with self.lock:
            data = self.store.get(key)
            if not data:
                return None
            if data.is_expired():
                del self.store[key]
                return None
            return data.value

    def get_snapshot_payload(self, keys: List[str]) -> Dict[str, Any]:
        """
        获取指定键集合的快照载荷。
        """
        payload = {}
        with self.lock:
            for key in keys:
                val = self.read_snapshot(key)
                if val is not None:
                    payload[key] = val
        return payload

    def cleanup(self):
        """清理过期数据"""
        with self.lock:
            now = time.time()
            expired_keys = [k for k, v in self.store.items() if v.is_expired()]
            for k in expired_keys:
                del self.store[k]
            if expired_keys:
                logger.debug(f"Blackboard cleaned up {len(expired_keys)} expired items.")

blackboard = EphemeralBlackboard.get_instance()
