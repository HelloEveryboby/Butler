"""IP 黑名单聚合服务"""

import asyncio
import time
from datetime import datetime, timezone

import httpx

from app.store.base import StateStore

# ── 公开黑名单源 ──
BLACKLIST_SOURCES = {
    "spamhaus_drop": {
        "url": "https://www.spamhaus.org/drop/drop.txt",
        "description": "Spamhaus DROP List (hijacked IP space)",
    },
    "spamhaus_edrop": {
        "url": "https://www.spamhaus.org/drop/edrop.txt",
        "description": "Spamhaus EDROP List (extended DROP)",
    },
    "abuse_ch_feodo": {
        "url": "https://feodotracker.abuse.ch/downloads/ipblocklist_recommended.txt",
        "description": "Feodo Tracker (botnet C2 servers)",
    },
    "ci_army": {
        "url": "https://cinsscore.com/list/ci-badguys.txt",
        "description": "CINS Score (known attackers)",
    },
    "blocklist_de": {
        "url": "https://lists.blocklist.de/lists/all.txt",
        "description": "Blocklist.de (reported attackers)",
    },
}


class BlacklistService:
    """IP 黑名单聚合服务"""

    def __init__(self, store: StateStore):
        self.store = store

    async def fetch_all(self) -> dict:
        """从所有源拉取黑名单"""
        results = {}
        async with httpx.AsyncClient(timeout=30.0) as client:
            tasks = [
                self._fetch_source(client, name, source)
                for name, source in BLACKLIST_SOURCES.items()
            ]
            done = await asyncio.gather(*tasks, return_exceptions=True)
            for i, (name, _) in enumerate(BLACKLIST_SOURCES.items()):
                if isinstance(done[i], Exception):
                    results[name] = {"error": str(done[i]), "count": 0}
                else:
                    results[name] = done[i]

        return {
            "sources": results,
            "total_ips": len(await self.store.get_blacklist()),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _fetch_source(self, client: httpx.AsyncClient, name: str, source: dict) -> dict:
        """拉取单个源"""
        try:
            resp = await client.get(source["url"])
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}", "count": 0}

            ips = []
            for line in resp.text.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith(";"):
                    # 处理 CIDR 格式（取第一个 IP）
                    ip = line.split("/")[0].split(";")[0].strip()
                    if ip and self._is_valid_ip(ip):
                        ips.append(ip)

            await self.store.add_to_blacklist(name, ips)

            return {
                "description": source["description"],
                "count": len(ips),
                "status": "ok",
            }
        except Exception as e:
            return {"error": str(e), "count": 0}

    async def check_ip(self, ip: str) -> dict:
        """检查 IP 是否在黑名单中"""
        is_listed = await self.store.is_blacklisted(ip)
        sources_found = []

        if is_listed:
            for name in BLACKLIST_SOURCES:
                blacklist = await self.store.get_blacklist(name)
                if ip in blacklist:
                    sources_found.append(name)

        return {
            "ip": ip,
            "is_blacklisted": is_listed,
            "sources": sources_found,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _is_valid_ip(ip: str) -> bool:
        import re
        return bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip))
