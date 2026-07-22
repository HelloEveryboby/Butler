"""
百度网盘驱动

基于百度网盘开放平台 API:
https://pan.baidu.com/union/doc/
"""

import time
import hashlib
import httpx
from datetime import datetime
from .base import StorageDriver, StorageConfig, FileItem, StorageType


class BaiduDriver(StorageDriver):
    """百度网盘"""

    API_BASE = "https://pan.baidu.com/rest/2.0"
    AUTH_URL = "https://openapi.baidu.com/oauth/2.0/token"

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.access_token = config.config.get("access_token", "")
        self.refresh_token = config.config.get("refresh_token", "")
        self.token_expire = 0
        self.client = httpx.AsyncClient(timeout=30)

    async def connect(self) -> bool:
        if not self.access_token:
            return False
        self._connected = True
        return True

    async def disconnect(self) -> None:
        await self.client.aclose()
        self._connected = False

    async def list(self, path: str = "/") -> list[FileItem]:
        resp = await self._get("/xpan/file", {
            "dir": path,
            "order": "name",
            "showempty": 0,
            "web": 1,
        })
        items = []
        for f in resp.get("list", []):
            items.append(FileItem(
                name=f["server_filename"],
                path=f["path"],
                is_dir=f["isdir"] == 1,
                size=f.get("size", 0),
                modified=datetime.fromtimestamp(f.get("local_mtime", 0)),
                hash_md5=f.get("md5"),
                extra={"fs_id": f["fs_id"]},
            ))
        return items

    async def stat(self, path: str) -> FileItem:
        resp = await self._get("/xpan/multimedia", {
            "dlink": 1,
            "fsids": f'[{await self._path_to_fs_id(path)}]',
        })
        f = resp.get("list", [{}])[0]
        return FileItem(
            name=f.get("server_filename", path.split("/")[-1]),
            path=path,
            is_dir=f.get("isdir", 0) == 1,
            size=f.get("size", 0),
            extra={"fs_id": f.get("fs_id")},
        )

    async def get(self, path: str) -> bytes:
        url = await self.get_download_url(path)
        resp = await self.client.get(url, follow_redirects=True)
        return resp.content

    async def put(self, path: str, data: bytes, overwrite: bool = True) -> FileItem:
        # 百度网盘使用分片上传
        block_size = 4 * 1024 * 1024  # 4MB
        blocks = []
        for i in range(0, len(data), block_size):
            blocks.append(hashlib.md5(data[i:i+block_size]).hexdigest())

        file_list = [{"path": path, "isdir": 0, "size": len(data)}]

        # 创建上传任务
        resp = await self._post("/xpan/file", {
            "method": "create",
            "ondup": "overwrite" if overwrite else "newcopy",
            "access_token": self.access_token,
        }, json_body={
            "block_list": blocks,
            "path": path,
            "size": len(data),
            "isdir": 0,
            "rtype": 1 if overwrite else 2,
        })

        upload_url = resp.get("uploadurl", "")
        # 上传数据块
        if upload_url:
            await self.client.post(
                upload_url,
                content=data,
                headers={"Content-Type": "application/octet-stream"},
            )

        return FileItem(name=path.split("/")[-1], path=path, is_dir=False, size=len(data))

    async def delete(self, path: str) -> None:
        fs_id = await self._path_to_fs_id(path)
        await self._post("/xpan/file", {
            "method": "delete",
            "access_token": self.access_token,
        }, json_body={"filelist": [path]})

    async def mkdir(self, path: str) -> None:
        await self._post("/xpan/file", {
            "method": "create",
            "access_token": self.access_token,
        }, json_body={"path": path, "isdir": 1, "rtype": 0})

    async def move(self, src: str, dst: str) -> None:
        await self._post("/xpan/file", {
            "method": "move",
            "access_token": self.access_token,
        }, json_body={
            "filelist": [{"path": src, "dest": str(dst).rsplit("/", 1)[0], "newname": str(dst).rsplit("/", 1)[-1]}],
        })

    async def copy(self, src: str, dst: str) -> None:
        await self._post("/xpan/file", {
            "method": "copy",
            "access_token": self.access_token,
        }, json_body={
            "filelist": [{"path": src, "dest": str(dst).rsplit("/", 1)[0], "newname": str(dst).rsplit("/", 1)[-1]}],
        })

    async def get_download_url(self, path: str) -> str:
        fs_id = await self._path_to_fs_id(path)
        resp = await self._get("/xpan/multimedia", {
            "dlink": 1,
            "fsids": f"[{fs_id}]",
        })
        dlink = resp.get("list", [{}])[0].get("dlink", "")
        return f"{dlink}&access_token={self.access_token}"

    async def search(self, keyword: str, path: str = "/") -> list[FileItem]:
        resp = await self._get("/xpan/file", {
            "dir": path,
            "key": keyword,
            "web": 1,
        })
        return [
            FileItem(
                name=f["server_filename"],
                path=f["path"],
                is_dir=f["isdir"] == 1,
                size=f.get("size", 0),
                extra={"fs_id": f["fs_id"]},
            )
            for f in resp.get("list", [])
        ]

    # === 内部方法 ===

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def _get(self, path: str, params: dict) -> dict:
        params["access_token"] = self.access_token
        resp = await self.client.get(f"{self.API_BASE}{path}", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def _post(self, path: str, params: dict, json_body: dict = None) -> dict:
        params["access_token"] = self.access_token
        resp = await self.client.post(
            f"{self.API_BASE}{path}",
            params=params,
            json=json_body,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def _path_to_fs_id(self, path: str) -> int:
        resp = await self._get("/xpan/multimedia", {
            "dlink": 1,
            "path": path,
        })
        items = resp.get("list", [])
        if not items:
            raise FileNotFoundError(f"Path not found: {path}")
        return items[0]["fs_id"]
