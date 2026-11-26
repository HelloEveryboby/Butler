"""内容寻址存储 — 图片/视频等二进制产物的版本快照底座。

按内容 SHA-256 存放文件，天然去重；只负责字节存取，不解释业务语义。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from butler.core.constants import DATA_DIR

_CHUNK_SIZE = 1024 * 1024


@dataclass
class ArtifactMeta:
    """一个已存对象的元信息。"""

    sha: str
    size: int
    path: Path

    def to_dict(self) -> dict:
        return {"sha": self.sha, "size": self.size, "path": str(self.path)}


class ArtifactStore:
    """内容寻址对象库。目录结构：<root>/<sha 前两位>/<sha>。"""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else DATA_DIR / "system_data" / "artifacts"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def hash_file(path: str | Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def path_for(self, sha: str) -> Path:
        return self.root / sha[:2] / sha

    def exists(self, sha: str) -> bool:
        return self.path_for(sha).is_file()

    def put_bytes(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        target = self.path_for(sha)
        if target.exists():
            return sha
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp_name, target)
        finally:
            Path(tmp_name).unlink(missing_ok=True)
        return sha

    def put_file(self, path: str | Path, max_mb: int | None = None) -> str:
        src = Path(path)
        if not src.is_file():
            raise FileNotFoundError(f"文件不存在: {src}")
        size = src.stat().st_size
        if max_mb and size > max_mb * 1024 * 1024:
            raise ValueError(
                f"文件超过快照上限 {max_mb}MB: {src} ({size / 1024 / 1024:.1f}MB)"
            )
        sha = self.hash_file(src)
        target = self.path_for(sha)
        if target.exists():
            return sha
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent)
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            shutil.copyfile(src, tmp_path)
            os.replace(tmp_path, target)
        finally:
            tmp_path.unlink(missing_ok=True)
        return sha

    def get_path(self, sha: str) -> Path:
        path = self.path_for(sha)
        if not path.is_file():
            raise FileNotFoundError(f"对象不存在: {sha}")
        return path

    def read_bytes(self, sha: str) -> bytes:
        return self.get_path(sha).read_bytes()

    def stat(self, sha: str) -> ArtifactMeta | None:
        path = self.path_for(sha)
        if not path.is_file():
            return None
        return ArtifactMeta(sha=sha, size=path.stat().st_size, path=path)

    def total_size(self) -> int:
        return sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())

    def prune(self, referenced: set[str]) -> int:
        """删除未被引用的对象，返回释放的字节数。"""
        freed = 0
        for path in list(self.root.rglob("*")):
            if not path.is_file() or path.name in referenced:
                continue
            freed += path.stat().st_size
            path.unlink(missing_ok=True)
        return freed


artifact_store = ArtifactStore()
