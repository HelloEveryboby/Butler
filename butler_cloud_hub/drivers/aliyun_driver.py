"""
阿里云盘驱动

基于阿里云盘开放平台 API v2:
https://www.aliyundrive.com/drive/api
"""

import time
import httpx
from datetime import datetime
from .base import StorageDriver, StorageConfig, FileItem, StorageType


class AliyunDriver(StorageDriver):
    """阿里云盘"""

    API_BASE = "https://api.aliyundrive.com"
    AUTH_URL = "https://auth.aliyundrive.com/v2/account/token"

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.refresh_token = config.config.get("refresh_token", "")
        self.access_token = ""
        self.token_expire = 0
        self.drive_id = ""
        self.client = httpx.AsyncClient(timeout=30)

    async def connect(self) -> bool:
        if not self.refresh_token:
            return False
        try:
            return await self._refresh_access_token()
        except Exception:
            return False

    async def disconnect(self) -> None:
        await self.client.aclose()
        self._connected = False

    async def list(self, path: str = "/") -> list[FileItem]:
        file_id = await self._path_to_id(path)
        items = []
        marker = None

        while True:
            body = {
                "drive_id": self.drive_id,
                "parent_file_id": file_id,
                "limit": 200,
            }
            if marker:
                body["marker"] = marker

            resp = await self._post("/v2/file/list", body)
            for f in resp.get("items", []):
                items.append(FileItem(
                    name=f["name"],
                    path=f"{path.rstrip('/')}/{f['name']}".replace("//", "/"),
                    is_dir=f["type"] == "folder",
                    size=f.get("size", 0),
                    modified=datetime.fromisoformat(f["updated_at"].replace("Z", "+00:00")) if f.get("updated_at") else None,
                    hash_md5=f.get("content_hash"),
                    thumbnail=f.get("thumbnail"),
                    extra={"file_id": f["file_id"]},
                ))

            marker = resp.get("next_marker")
            if not marker:
                break

        return items

    async def stat(self, path: str) -> FileItem:
        file_id = await self._path_to_id(path)
        resp = await self._post("/v2/file/get", {
            "drive_id": self.drive_id,
            "file_id": file_id,
        })
        return FileItem(
            name=resp["name"],
            path=path,
            is_dir=resp["type"] == "folder",
            size=resp.get("size", 0),
            modified=datetime.fromisoformat(resp["updated_at"].replace("Z", "+00:00")) if resp.get("updated_at") else None,
            extra={"file_id": resp["file_id"]},
        )

    async def get(self, path: str) -> bytes:
        url = await self.get_download_url(path)
        resp = await self.client.get(url)
        return resp.content

    async def put(self, path: str, data: bytes, overwrite: bool = True) -> FileItem:
        parent = str(path).rsplit("/", 1)[0] or "/"
        name = str(path).rsplit("/", 1)[-1]
        parent_id = await self._path_to_id(parent)

        # 1. 创建上传任务
        resp = await self._post("/v2/file/create", {
            "drive_id": self.drive_id,
            "parent_file_id": parent_id,
            "name": name,
            "type": "file",
            "size": len(data),
            "check_name_mode": "overwrite" if overwrite else "auto_rename",
        })

        upload_url = resp["upload_url"]
        file_id = resp["file_id"]

        # 2. 上传数据
        await self.client.put(
            upload_url,
            content=data,
            headers={"Content-Type": "application/octet-stream"},
        )

        return FileItem(name=name, path=path, is_dir=False, size=len(data), extra={"file_id": file_id})

    async def delete(self, path: str) -> None:
        file_id = await self._path_to_id(path)
        await self._post("/v2/file/delete", {
            "drive_id": self.drive_id,
            "file_id": file_id,
        })

    async def mkdir(self, path: str) -> None:
        parent = str(path).rsplit("/", 1)[0] or "/"
        name = str(path).rsplit("/", 1)[-1]
        parent_id = await self._path_to_id(parent)
        await self._post("/v2/file/create", {
            "drive_id": self.drive_id,
            "parent_file_id": parent_id,
            "name": name,
            "type": "folder",
        })

    async def move(self, src: str, dst: str) -> None:
        file_id = await self._path_to_id(src)
        dst_parent = str(dst).rsplit("/", 1)[0] or "/"
        dst_name = str(dst).rsplit("/", 1)[-1]
        to_parent = await self._path_to_id(dst_parent)
        await self._post("/v2/file/update", {
            "drive_id": self.drive_id,
            "file_id": file_id,
            "name": dst_name,
            "to_drive_id": self.drive_id,
            "to_parent_file_id": to_parent,
        })

    async def copy(self, src: str, dst: str) -> None:
        file_id = await self._path_to_id(src)
        dst_parent = str(dst).rsplit("/", 1)[0] or "/"
        to_parent = await self._path_to_id(dst_parent)
        await self._post("/v2/file/copy", {
            "drive_id": self.drive_id,
            "file_id": file_id,
            "to_drive_id": self.drive_id,
            "to_parent_file_id": to_parent,
        })

    async def get_download_url(self, path: str) -> str:
        file_id = await self._path_to_id(path)
        resp = await self._post("/v2/file/get_download_url", {
            "drive_id": self.drive_id,
            "file_id": file_id,
        })
        return resp["url"]

    async def search(self, keyword: str, path: str = "/") -> list[FileItem]:
        resp = await self._post("/v2/file/search", {
            "drive_id": self.drive_id,
            "query": f"name match '{keyword}'",
            "limit": 50,
        })
        return [
            FileItem(
                name=f["name"],
                path=f.get("path", f["name"]),
                is_dir=f["type"] == "folder",
                size=f.get("size", 0),
                extra={"file_id": f["file_id"]},
            )
            for f in resp.get("items", [])
        ]

    # === 内部方法 ===

    async def _refresh_access_token(self) -> bool:
        resp = await self.client.post(self.AUTH_URL, json={
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        })
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        self.token_expire = time.time() + data.get("expires_in", 7200)
        self.drive_id = data.get("default_drive_id", "")

        # 获取 user_id
        user_resp = await self.client.get(
            f"{self.API_BASE}/v2/user/get",
            headers=self._headers(),
        )
        self.drive_id = user_resp.json().get("default_drive_id", self.drive_id)
        self._connected = True
        return True

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, body: dict) -> dict:
        if time.time() > self.token_expire - 300:
            await self._refresh_access_token()
        resp = await self.client.post(
            f"{self.API_BASE}{path}",
            json=body,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def _path_to_id(self, path: str) -> str:
        """将路径转为阿里云盘 file_id"""
        if path in ("/", ""):
            return "root"

        parts = [p for p in path.split("/") if p]
        current_id = "root"

        for part in parts:
            resp = await self._post("/v2/file/list", {
                "drive_id": self.drive_id,
                "parent_file_id": current_id,
                "limit": 200,
            })
            found = False
            for f in resp.get("items", []):
                if f["name"] == part:
                    current_id = f["file_id"]
                    found = True
                    break
            if not found:
                raise FileNotFoundError(f"Path not found: {path}")

        return current_id
