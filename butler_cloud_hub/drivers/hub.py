"""
CloudHub Manager — 多云存储统一管理器

注册所有驱动，提供统一 API，支持跨盘传输。
"""

import asyncio
import logging
from typing import Optional
from .base import StorageDriver, StorageConfig, FileItem, StorageType

logger = logging.getLogger("CloudHub")


# 驱动注册表
DRIVER_REGISTRY: dict[StorageType, type[StorageDriver]] = {}


def register_driver(storage_type: StorageType):
    """装饰器: 注册存储驱动"""
    def decorator(cls):
        DRIVER_REGISTRY[storage_type] = cls
        return cls
    return decorator


# 延迟导入并注册驱动
def _load_drivers():
    from .local_driver import LocalDriver
    from .aliyun_driver import AliyunDriver
    from ..baidu_driver import BaiduDriver
    from .onedrive_driver import OneDriveDriver
    from .webdav_driver import WebDAVDriver

    DRIVER_REGISTRY[StorageType.LOCAL] = LocalDriver
    DRIVER_REGISTRY[StorageType.ALIYUN] = AliyunDriver
    DRIVER_REGISTRY[StorageType.BAIDU] = BaiduDriver
    DRIVER_REGISTRY[StorageType.ONEDRIVE] = OneDriveDriver
    DRIVER_REGISTRY[StorageType.WEBDAV] = WebDAVDriver


class CloudHub:
    """多云存储统一管理器"""

    def __init__(self):
        self.drivers: dict[str, StorageDriver] = {}
        _load_drivers()

    async def add_storage(self, config: StorageConfig) -> str:
        """添加存储"""
        driver_cls = DRIVER_REGISTRY.get(config.type)
        if not driver_cls:
            raise ValueError(f"Unsupported storage type: {config.type}")

        driver = driver_cls(config)
        ok = await driver.connect()
        if not ok:
            raise ConnectionError(f"Failed to connect: {config.name}")

        self.drivers[config.name] = driver
        logger.info(f"Storage added: {config.name} ({config.type})")
        return config.name

    async def remove_storage(self, name: str) -> None:
        """移除存储"""
        driver = self.drivers.pop(name, None)
        if driver:
            await driver.disconnect()
            logger.info(f"Storage removed: {name}")

    def get_driver(self, name: str) -> Optional[StorageDriver]:
        """获取驱动实例"""
        return self.drivers.get(name)

    def list_storages(self) -> list[dict]:
        """列出所有已注册存储"""
        return [
            {
                "name": d.name,
                "type": d.type.value,
                "connected": d.is_connected,
                "read_only": d.config.read_only,
            }
            for d in self.drivers.values()
        ]

    async def list_files(self, storage_name: str, path: str = "/") -> list[dict]:
        """列出文件"""
        driver = self._get_driver(storage_name)
        items = await driver.list(path)
        return [item.to_dict() for item in items]

    async def get_file(self, storage_name: str, path: str) -> bytes:
        """下载文件"""
        driver = self._get_driver(storage_name)
        return await driver.get(path)

    async def put_file(self, storage_name: str, path: str, data: bytes) -> dict:
        """上传文件"""
        driver = self._get_driver(storage_name)
        if driver.config.read_only:
            raise PermissionError(f"Storage is read-only: {storage_name}")
        item = await driver.put(path, data)
        return item.to_dict()

    async def delete_file(self, storage_name: str, path: str) -> None:
        """删除文件"""
        driver = self._get_driver(storage_name)
        if driver.config.read_only:
            raise PermissionError(f"Storage is read-only: {storage_name}")
        await driver.delete(path)

    async def mkdir(self, storage_name: str, path: str) -> None:
        """创建目录"""
        driver = self._get_driver(storage_name)
        if driver.config.read_only:
            raise PermissionError(f"Storage is read-only: {storage_name}")
        await driver.mkdir(path)

    async def search(self, storage_name: str, keyword: str, path: str = "/") -> list[dict]:
        """搜索文件"""
        driver = self._get_driver(storage_name)
        items = await driver.search(keyword, path)
        return [item.to_dict() for item in items]

    async def transfer(self, src_storage: str, src_path: str, dst_storage: str, dst_path: str) -> dict:
        """
        跨盘传输

        从源存储下载 → 上传到目标存储。
        未来可优化为流式传输，不落盘。
        """
        src_driver = self._get_driver(src_storage)
        dst_driver = self._get_driver(dst_storage)

        if dst_driver.config.read_only:
            raise PermissionError(f"Destination is read-only: {dst_storage}")

        # 下载
        logger.info(f"Transferring: {src_storage}:{src_path} → {dst_storage}:{dst_path}")
        data = await src_driver.get(src_path)

        # 上传
        result = await dst_driver.put(dst_path, data)
        logger.info(f"Transfer complete: {len(data)} bytes")
        return result.to_dict()

    async def global_search(self, keyword: str) -> list[dict]:
        """全局搜索所有存储"""
        results = []
        tasks = []
        for name, driver in self.drivers.items():
            if driver.is_connected:
                tasks.append(self._search_one(name, driver, keyword))

        for coro in asyncio.as_completed(tasks):
            try:
                storage_name, items = await coro
                for item in items:
                    item_dict = item.to_dict()
                    item_dict["storage"] = storage_name
                    results.append(item_dict)
            except Exception as e:
                logger.warning(f"Search error: {e}")

        return results

    async def _search_one(self, name: str, driver: StorageDriver, keyword: str):
        items = await driver.search(keyword)
        return name, items

    def _get_driver(self, name: str) -> StorageDriver:
        driver = self.drivers.get(name)
        if not driver:
            raise KeyError(f"Storage not found: {name}")
        if not driver.is_connected:
            raise ConnectionError(f"Storage not connected: {name}")
        return driver
