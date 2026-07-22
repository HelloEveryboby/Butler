"""
WebDAV 通用驱动
"""

import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from .base import StorageDriver, StorageConfig, FileItem, StorageType


class WebDAVDriver(StorageDriver):
    """WebDAV 通用协议"""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.base_url = config.config.get("url", "").rstrip("/")
        self.username = config.config.get("username", "")
        self.password = config.config.get("password", "")
        self.client = httpx.AsyncClient(
            timeout=30,
            auth=httpx.BasicAuth(self.username, self.password) if self.username else None,
        )

    async def connect(self) -> bool:
        try:
            resp = await self.client.request("PROPFIND", self.base_url, headers={"Depth": "0"})
            self._connected = resp.status_code in (200, 207)
            return self._connected
        except Exception:
            return False

    async def disconnect(self) -> None:
        await self.client.aclose()
        self._connected = False

    async def list(self, path: str = "/") -> list[FileItem]:
        url = f"{self.base_url}{path}"
        resp = await self.client.request(
            "PROPFIND", url,
            headers={"Depth": "1", "Content-Type": "application/xml"},
        )
        return self._parse_multistatus(resp.text, path)

    async def stat(self, path: str) -> FileItem:
        url = f"{self.base_url}{path}"
        resp = await self.client.request(
            "PROPFIND", url,
            headers={"Depth": "0", "Content-Type": "application/xml"},
        )
        items = self._parse_multistatus(resp.text, str(path).rsplit("/", 1)[0] or "/")
        if not items:
            raise FileNotFoundError(f"Not found: {path}")
        return items[0]

    async def get(self, path: str) -> bytes:
        resp = await self.client.get(f"{self.base_url}{path}")
        resp.raise_for_status()
        return resp.content

    async def put(self, path: str, data: bytes, overwrite: bool = True) -> FileItem:
        headers = {}
        if not overwrite:
            headers["If-None-Match"] = "*"
        resp = await self.client.put(
            f"{self.base_url}{path}",
            content=data,
            headers=headers,
        )
        resp.raise_for_status()
        return FileItem(name=str(path).split("/")[-1], path=path, is_dir=False, size=len(data))

    async def delete(self, path: str) -> None:
        resp = await self.client.delete(f"{self.base_url}{path}")
        resp.raise_for_status()

    async def mkdir(self, path: str) -> None:
        resp = await self.client.request("MKCOL", f"{self.base_url}{path}")
        resp.raise_for_status()

    async def move(self, src: str, dst: str) -> None:
        resp = await self.client.request(
            "MOVE", f"{self.base_url}{src}",
            headers={"Destination": f"{self.base_url}{dst}", "Overwrite": "T"},
        )
        resp.raise_for_status()

    async def copy(self, src: str, dst: str) -> None:
        resp = await self.client.request(
            "COPY", f"{self.base_url}{src}",
            headers={"Destination": f"{self.base_url}{dst}", "Overwrite": "T"},
        )
        resp.raise_for_status()

    # === XML 解析 ===

    def _parse_multistatus(self, xml_text: str, parent_path: str) -> list[FileItem]:
        items = []
        ns = {"d": "DAV:"}
        root = ET.fromstring(xml_text)

        for resp in root.findall(".//d:response", ns):
            href = resp.findtext("d:href", "", ns)
            if not href:
                continue

            name = href.rstrip("/").split("/")[-1]
            is_dir = resp.find(".//d:resourcetype/d:collection", ns) is not None

            # 跳过目录自身
            if href.rstrip("/") == f"{self.base_url}{parent_path}".rstrip("/"):
                continue

            size_text = resp.findtext(".//d:getcontentlength", "0", ns)
            modified_text = resp.findtext(".//d:getlastmodified", "", ns)

            items.append(FileItem(
                name=name,
                path=href.replace(self.base_url, ""),
                is_dir=is_dir,
                size=int(size_text) if size_text else 0,
                modified=self._parse_http_date(modified_text) if modified_text else None,
            ))

        return items

    @staticmethod
    def _parse_http_date(date_str: str) -> datetime:
        from email.utils import parsedate_to_datetime
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return datetime.now()
