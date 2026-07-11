"""Local filesystem storage driver."""

import os
import shutil
from typing import Any, Dict, List, Optional
from pathlib import Path
from .abstract_driver import AbstractDriver


class LocalDriver(AbstractDriver):
    """Driver for local filesystem storage."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize local driver.

        Args:
            config: Configuration dict with 'base_path' key
        """
        super().__init__(config)
        self.base_path = Path(config.get('base_path', './storage'))
        self.connected = False

    def connect(self) -> bool:
        """Establish connection (create base directory if needed)."""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            self.connected = True
            return True
        except Exception as e:
            print(f"Local driver connection error: {e}")
            return False

    def disconnect(self) -> bool:
        """Close connection."""
        self.connected = False
        return True

    def _get_full_path(self, path: str) -> Path:
        """Get full file path, preventing directory traversal."""
        # Remove leading slashes
        clean_path = path.lstrip('/')
        full_path = (self.base_path / clean_path).resolve()

        # Security check: ensure path is within base_path
        if not str(full_path).startswith(str(self.base_path.resolve())):
            raise ValueError(f"Path traversal detected: {path}")

        return full_path

    def put(self, path: str, data: bytes) -> bool:
        """Upload file content."""
        try:
            full_path = self._get_full_path(path)
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(data)
            return True
        except Exception as e:
            print(f"Local put error: {e}")
            return False

    def put_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file from local filesystem."""
        try:
            with open(local_path, 'rb') as f:
                data = f.read()
            return self.put(remote_path, data)
        except Exception as e:
            print(f"Local put_file error: {e}")
            return False

    def get(self, path: str) -> Optional[bytes]:
        """Download file content."""
        try:
            full_path = self._get_full_path(path)
            if full_path.exists():
                return full_path.read_bytes()
            return None
        except Exception as e:
            print(f"Local get error: {e}")
            return None

    def get_file(self, remote_path: str, local_path: str) -> bool:
        """Download file to local filesystem."""
        try:
            data = self.get(remote_path)
            if data is None:
                return False
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            Path(local_path).write_bytes(data)
            return True
        except Exception as e:
            print(f"Local get_file error: {e}")
            return False

    def list_objects(self, prefix: str = "", recursive: bool = False) -> List[Dict[str, Any]]:
        """List objects in storage."""
        try:
            search_path = self.base_path / prefix.lstrip('/')

            if not search_path.exists():
                return []

            objects = []

            if recursive:
                pattern = "**/*"
            else:
                pattern = "*"

            for item in search_path.glob(pattern):
                if item.is_file():
                    rel_path = item.relative_to(self.base_path)
                    stat = item.stat()
                    objects.append({
                        'name': str(rel_path),
                        'size': stat.st_size,
                        'modified_time': stat.st_mtime,
                        'is_file': True,
                    })
                elif item.is_dir() and not recursive:
                    rel_path = item.relative_to(self.base_path)
                    objects.append({
                        'name': str(rel_path) + '/',
                        'size': 0,
                        'modified_time': item.stat().st_mtime,
                        'is_file': False,
                    })

            return objects
        except Exception as e:
            print(f"Local list_objects error: {e}")
            return []

    def exists(self, path: str) -> bool:
        """Check if object exists."""
        try:
            full_path = self._get_full_path(path)
            return full_path.exists()
        except Exception as e:
            print(f"Local exists error: {e}")
            return False

    def delete(self, path: str) -> bool:
        """Delete object."""
        try:
            full_path = self._get_full_path(path)
            if full_path.is_file():
                full_path.unlink()
                return True
            elif full_path.is_dir():
                shutil.rmtree(full_path)
                return True
            return False
        except Exception as e:
            print(f"Local delete error: {e}")
            return False

    def copy(self, src_path: str, dst_path: str) -> bool:
        """Copy object within storage."""
        try:
            src_full = self._get_full_path(src_path)
            dst_full = self._get_full_path(dst_path)

            if not src_full.exists():
                return False

            dst_full.parent.mkdir(parents=True, exist_ok=True)

            if src_full.is_file():
                shutil.copy2(src_full, dst_full)
            else:
                shutil.copytree(src_full, dst_full, dirs_exist_ok=True)

            return True
        except Exception as e:
            print(f"Local copy error: {e}")
            return False

    def get_url(self, path: str, expires_in: int = 3600) -> Optional[str]:
        """Local filesystem doesn't support URLs."""
        try:
            full_path = self._get_full_path(path)
            return f"file://{full_path.resolve()}"
        except Exception:
            return None

    def get_metadata(self, path: str) -> Optional[Dict[str, Any]]:
        """Get object metadata."""
        try:
            full_path = self._get_full_path(path)
            if not full_path.exists():
                return None

            stat = full_path.stat()
            return {
                'name': path,
                'size': stat.st_size,
                'modified_time': stat.st_mtime,
                'is_file': full_path.is_file(),
                'is_dir': full_path.is_dir(),
            }
        except Exception as e:
            print(f"Local get_metadata error: {e}")
            return None
