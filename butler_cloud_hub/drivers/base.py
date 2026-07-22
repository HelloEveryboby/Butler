"""
Butler Cloud Hub — 统一存储抽象层

每个云盘驱动实现 StorageDriver 接口，
CloudHub 管理所有驱动实例并提供统一 API。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, AsyncIterator
import asyncio


class StorageType(str, Enum):
    LOCAL = "local"
    ALIYUN = "aliyun"
    BAIDU = "baidu"
    ONEDRIVE = "onedrive"
    WEBDAV = "webdaV"
    GOOGLE = "google"
    S3 = "s3"
    PAN123 = "123pan"
    QUARK = "quark"


@dataclass
class FileItem:
    """统一文件模型"""
    name: str
    path: str
    is_dir: bool
    size: int = 0
    modified: Optional[datetime] = None
    hash_md5: Optional[str] = None
    hash_sha1: Optional[str] = None
    thumbnail: Optional[str] = None
    mime_type: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "is_dir": self.is_dir,
            "size": self.size,
            "modified": self.modified.isoformat() if self.modified else None,
            "hash_md5": self.hash_md5,
            "thumbnail": self.thumbnail,
            "mime_type": self.mime_type,
        }


@dataclass
class StorageConfig:
    """存储配置"""
    name: str           # 用户自定义名称, 如 "我的阿里云盘"
    type: StorageType
    config: dict        # 驱动特定配置 (token, url, etc.)
    enabled: bool = True
    read_only: bool = False


class StorageDriver(ABC):
    """
    存储驱动抽象接口

    每个云盘/协议实现这个接口即可接入 CloudHub。
    所有方法都是异步的，支持并发操作。
    """

    def __init__(self, config: StorageConfig):
        self.config = config
        self.name = config.name
        self.type = config.type
        self._connected = False

    @abstractmethod
    async def connect(self) -> bool:
        """初始化连接/认证"""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接，释放资源"""
        ...

    @abstractmethod
    async def list(self, path: str = "/") -> list[FileItem]:
        """列出目录内容"""
        ...

    @abstractmethod
    async def stat(self, path: str) -> FileItem:
        """获取文件/目录信息"""
        ...

    @abstractmethod
    async def get(self, path: str) -> bytes:
        """下载文件内容"""
        ...

    @abstractmethod
    async def put(self, path: str, data: bytes, overwrite: bool = True) -> FileItem:
        """上传文件"""
        ...

    @abstractmethod
    async def delete(self, path: str) -> None:
        """删除文件/目录"""
        ...

    @abstractmethod
    async def mkdir(self, path: str) -> None:
        """创建目录"""
        ...

    @abstractmethod
    async def move(self, src: str, dst: str) -> None:
        """移动/重命名"""
        ...

    @abstractmethod
    async def copy(self, src: str, dst: str) -> None:
        """复制"""
        ...

    async def get_download_url(self, path: str) -> Optional[str]:
        """获取直链下载地址 (如果支持)"""
        return None

    async def search(self, keyword: str, path: str = "/") -> list[FileItem]:
        """搜索文件 (如果支持)"""
        return []

    @property
    def is_connected(self) -> bool:
        return self._connected

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' type={self.type}>"
