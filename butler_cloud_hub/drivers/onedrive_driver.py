"""
OneDrive 驱动

基于 Microsoft Graph API:
https://learn.microsoft.com/en-us/graph/api/resources/onedrive
"""

import time
import httpx
from datetime import datetime
from .base import StorageDriver, StorageConfig, FileItem, StorageType


class OneDriveDriver(StorageDriver):
    """OneDrive / OneDrive for Business"""

    API_BASE = "https://graph.microsoft.com/v1.0"
    AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.client_id = config.config.get("client_id", "")
        self.client_secret = config.config.get("client_secret", "")
        self.refresh_token = config.config.get("refresh_token", "")
        self.access_token = ""
        self.token_expire = 0
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
        api_path = f"/me/drive/root/children" if path in ("/", "") else f"/me/drive/root:{path}:/children"
        items = []
        url = f"{self.API_BASE}{api_path}"

        while url:
            resp = await self._get_raw(url)
            data = resp.json()
            for f in data.get("value", []):
                items.append(FileItem(
                    name=f["name"],
                    path=f"{path.rstrip('/')}/{f['name']}".replace("//", "/"),
                    is_dir="folder" in f,
                    size=f.get("size", 0),
                    modified=datetime.fromisoformat(f["lastModifiedDateTime"]),
                    hash_md5=f.get("file", {}).get("hashes", {}).get("quickXorHash"),
                    extra={"id": f["id"]},
                ))
            url = data.get("@odata.nextLink")

        return items

    async def stat(self, path: str) -> FileItem:
        api_path = "/me/drive/root" if path in ("/", "") else f"/me/drive/root:{path}"
        resp = await self._get(api_path)
        return FileItem(
            name=resp["name"],
            path=path,
            is_dir="folder" in resp,
            size=resp.get("size", 0),
            modified=datetime.fromisoformat(resp["lastModifiedDateTime"]),
            extra={"id": resp["id"]},
        )

    async def get(self, path: str) -> bytes:
        url = await self.get_download_url(path)
        resp = await self.client.get(url, follow_redirects=True)
        return resp.content

    async def put(self, path: str, data: bytes, overwrite: bool = True) -> FileItem:
        # 小文件 (<4MB) 直接上传
        if len(data) <= 4 * 1024 * 1024:
            api_path = f"/me/drive/root:{path}:/content" if overwrite else f"/me/drive/root:{path}:/content"
            resp = await self.client.put(
                f"{self.API_BASE}{api_path}",
                content=data,
                headers={
                    **self._headers(),
                    "Content-Type": "application/octet-stream",
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return FileItem(
                name=result["name"],
                path=path,
                is_dir=False,
                size=result.get("size", len(data)),
                extra={"id": result["id"]},
            )
        else:
            # 大文件: 创建上传会话
            api_path = f"/me/drive/root:{path}:/createUploadSession"
            session = await self._post(api_path, {})
            upload_url = session["uploadUrl"]
            await self.client.put(
                upload_url,
                content=data,
                headers={
                    "Content-Range": f"bytes 0-{len(data)-1}/{len(data)}",
                    "Content-Length": str(len(data)),
                },
            )
            return FileItem(name=path.split("/")[-1], path=path, is_dir=False, size=len(data))

    async def delete(self, path: str) -> None:
        api_path = f"/me/drive/root:{path}"
        await self._delete(api_path)

    async def mkdir(self, path: str) -> None:
        parent = str(path).rsplit("/", 1)[0] or "/"
        name = str(path).rsplit("/", 1)[-1]
        api_path = "/me/drive/root/children" if parent in ("/", "") else f"/me/drive/root:{parent}:/children"
        await self._post(api_path, {"name": name, "folder": {}})

    async def move(self, src: str, dst: str) -> None:
        item_id = (await self.stat(src)).extra["id"]
        dst_parent = str(dst).rsplit("/", 1)[0] or "/"
        dst_name = str(dst).rsplit("/", 1)[-1]
        parent_id = "root" if dst_parent in ("/", "") else (await self.stat(dst_parent)).extra["id"]
        await self._patch(f"/me/drive/items/{item_id}", {
            "name": dst_name,
            "parentReference": {"id": parent_id},
        })

    async def copy(self, src: str, dst: str) -> None:
        item_id = (await self.stat(src)).extra["id"]
        dst_parent = str(dst).rsplit("/", 1)[0] or "/"
        dst_name = str(dst).rsplit("/", 1)[-1]
        parent_id = "root" if dst_parent in ("/", "") else (await self.stat(dst_parent)).extra["id"]
        await self._post(f"/me/drive/items/{item_id}/copy", {
            "name": dst_name,
            "parentReference": {"id": parent_id},
        })

    async def get_download_url(self, path: str) -> str:
        api_path = "/me/drive/root/content" if path in ("/", "") else f"/me/drive/root:{path}:/content"
        # 返回重定向 URL
        return f"{self.API_BASE}{api_path}"

    async def search(self, keyword: str, path: str = "/") -> list[FileItem]:
        resp = await self._get(f"/me/drive/root/search(q='{keyword}')")
        return [
            FileItem(
                name=f["name"],
                path=f.get("parentReference", {}).get("path", "") + "/" + f["name"],
                is_dir="folder" in f,
                size=f.get("size", 0),
                extra={"id": f["id"]},
            )
            for f in resp.get("value", [])
        ]

    # === 内部方法 ===

    async def _refresh_access_token(self) -> bool:
        resp = await self.client.post(self.AUTH_URL, data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        })
        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        self.token_expire = time.time() + data.get("expires_in", 3600)
        self._connected = True
        return True

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str) -> dict:
        if time.time() > self.token_expire - 300:
            await self._refresh_access_token()
        resp = await self.client.get(f"{self.API_BASE}{path}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def _get_raw(self, url: str) -> httpx.Response:
        if time.time() > self.token_expire - 300:
            await self._refresh_access_token()
        return await self.client.get(url, headers=self._headers())

    async def _post(self, path: str, body: dict) -> dict:
        if time.time() > self.token_expire - 300:
            await self._refresh_access_token()
        resp = await self.client.post(f"{self.API_BASE}{path}", json=body, headers=self._headers())
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    async def _patch(self, path: str, body: dict) -> dict:
        if time.time() > self.token_expire - 300:
            await self._refresh_access_token()
        resp = await self.client.patch(f"{self.API_BASE}{path}", json=body, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def _delete(self, path: str) -> None:
        if time.time() > self.token_expire - 300:
            await self._refresh_access_token()
        resp = await self.client.delete(f"{self.API_BASE}{path}", headers=self._headers())
        resp.raise_for_status()
