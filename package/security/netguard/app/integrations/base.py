"""外部 API 客户端基类"""

import asyncio
import time
from abc import ABC, abstractmethod

import httpx


class ExternalAPIClient(ABC):
    """带重试 + 缓存的外部 API 客户端基类"""

    def __init__(self, api_key: str | None = None, timeout: float = 10.0):
        self.api_key = api_key
        self._http = httpx.AsyncClient(timeout=timeout)
        self._cache: dict[str, tuple[float, dict]] = {}
        self._cache_ttl = 3600  # 1 小时

    def _cache_get(self, key: str) -> dict | None:
        if key in self._cache:
            ts, data = self._cache[key]
            if time.time() - ts < self._cache_ttl:
                return data
            del self._cache[key]
        return None

    def _cache_set(self, key: str, data: dict):
        self._cache[key] = (time.time(), data)

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    async def lookup(self, target: str) -> dict: ...

    async def close(self):
        await self._http.aclose()
