"""状态存储抽象基类"""

from abc import ABC, abstractmethod


class StateStore(ABC):
    """统一的状态存储接口，支持 Redis 和内存两种实现"""

    # ── IP 阻断 ──
    @abstractmethod
    async def is_ip_blocked(self, ip: str) -> bool: ...

    @abstractmethod
    async def block_ip(self, ip: str, ttl_seconds: int = 3600): ...

    @abstractmethod
    async def unblock_ip(self, ip: str): ...

    @abstractmethod
    async def get_blocked_ips(self) -> list[str]: ...

    # ── 请求计数（限流） ──
    @abstractmethod
    async def increment_counter(self, key: str, window_seconds: int) -> int: ...

    @abstractmethod
    async def get_counter(self, key: str) -> int: ...

    # ── 规则 ──
    @abstractmethod
    async def set_rule(self, key: str, value: int): ...

    @abstractmethod
    async def get_rules(self) -> dict: ...

    # ── 黑名单 ──
    @abstractmethod
    async def add_to_blacklist(self, source: str, ips: list[str]): ...

    @abstractmethod
    async def get_blacklist(self, source: str | None = None) -> list[str]: ...

    @abstractmethod
    async def is_blacklisted(self, ip: str) -> bool: ...

    # ── 任务队列 ──
    @abstractmethod
    async def create_task(self, task_id: str, task_type: str, params: dict): ...

    @abstractmethod
    async def update_task(self, task_id: str, status: str, result: dict | None = None): ...

    @abstractmethod
    async def get_task(self, task_id: str) -> dict | None: ...

    @abstractmethod
    async def list_tasks(self, user_id: int, task_type: str | None = None) -> list[dict]: ...
