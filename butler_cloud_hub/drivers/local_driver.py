"""
本地文件系统驱动
"""

import os
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from .base import StorageDriver, StorageConfig, FileItem, StorageType


class LocalDriver(StorageDriver):
    """本地文件系统"""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.root = Path(config.config.get("root", "/"))

    async def connect(self) -> bool:
        if self.root.exists() and self.root.is_dir():
            self._connected = True
            return True
        return False

    async def disconnect(self) -> None:
        self._connected = False

    async def list(self, path: str = "/") -> list[FileItem]:
        target = self._resolve(path)
        items = []
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            try:
                stat = entry.stat()
                items.append(FileItem(
                    name=entry.name,
                    path=self._relative(entry),
                    is_dir=entry.is_dir(),
                    size=stat.st_size if entry.is_file() else 0,
                    modified=datetime.fromtimestamp(stat.st_mtime),
                    mime_type=self._guess_mime(entry),
                ))
            except (PermissionError, OSError):
                continue
        return items

    async def stat(self, path: str) -> FileItem:
        target = self._resolve(path)
        stat = target.stat()
        return FileItem(
            name=target.name,
            path=path,
            is_dir=target.is_dir(),
            size=stat.st_size if target.is_file() else 0,
            modified=datetime.fromtimestamp(stat.st_mtime),
        )

    async def get(self, path: str) -> bytes:
        target = self._resolve(path)
        return target.read_bytes()

    async def put(self, path: str, data: bytes, overwrite: bool = True) -> FileItem:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not overwrite:
            raise FileExistsError(f"File already exists: {path}")
        target.write_bytes(data)
        return await self.stat(path)

    async def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    async def mkdir(self, path: str) -> None:
        self._resolve(path).mkdir(parents=True, exist_ok=True)

    async def move(self, src: str, dst: str) -> None:
        shutil.move(str(self._resolve(src)), str(self._resolve(dst)))

    async def copy(self, src: str, dst: str) -> None:
        s, d = self._resolve(src), self._resolve(dst)
        if s.is_dir():
            shutil.copytree(s, d)
        else:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)

    async def search(self, keyword: str, path: str = "/") -> list[FileItem]:
        target = self._resolve(path)
        results = []
        keyword_lower = keyword.lower()
        for root, dirs, files in os.walk(target):
            for name in files + dirs:
                if keyword_lower in name.lower():
                    full = Path(root) / name
                    try:
                        stat = full.stat()
                        results.append(FileItem(
                            name=name,
                            path=self._relative(full),
                            is_dir=full.is_dir(),
                            size=stat.st_size if full.is_file() else 0,
                            modified=datetime.fromtimestamp(stat.st_mtime),
                        ))
                    except (PermissionError, OSError):
                        continue
        return results[:100]

    # === 内部方法 ===

    def _resolve(self, path: str) -> Path:
        """将虚拟路径转为实际路径"""
        clean = path.lstrip("/")
        target = (self.root / clean).resolve()
        # 安全检查: 不允许跳出 root
        if not str(target).startswith(str(self.root.resolve())):
            raise ValueError(f"Path traversal blocked: {path}")
        return target

    def _relative(self, full_path: Path) -> str:
        """将实际路径转为虚拟路径"""
        rel = full_path.relative_to(self.root)
        return "/" + str(rel).replace("\\", "/")

    @staticmethod
    def _guess_mime(path: Path) -> Optional[str]:
        ext = path.suffix.lower()
        mimes = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
            ".mp4": "video/mp4", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
            ".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac",
            ".pdf": "application/pdf", ".zip": "application/zip",
            ".txt": "text/plain", ".md": "text/markdown", ".json": "application/json",
            ".py": "text/x-python", ".js": "text/javascript", ".ts": "text/typescript",
        }
        return mimes.get(ext)
