"""威胁情报服务 — 本地知识库 + 外部 API 聚合"""

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.threat import ThreatRecord
from app.store.base import StateStore

# ── 已知恶意目标（本地知识库） ──
KNOWN_MALICIOUS_PATTERNS: dict = {
    "ips": {
        "192.168.1.100": {"categories": ["botnet", "c2"], "score": 0.95},
        "10.0.0.66": {"categories": ["spam", "phishing"], "score": 0.8},
        "45.33.32.156": {"categories": ["scanner", "brute-force"], "score": 0.7},
    },
    "domains": {
        "malware-c2.example.com": {"categories": ["c2", "malware"], "score": 0.98},
        "phishing-site.example.net": {"categories": ["phishing", "fraud"], "score": 0.9},
        "spam-relay.example.org": {"categories": ["spam"], "score": 0.6},
    },
}

_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")


def _detect_target_type(target: str) -> str:
    if _IP_RE.match(target):
        return "ip"
    if "." in target and not target.startswith(("http://", "https://")):
        return "domain"
    if target.startswith(("http://", "https://")):
        return "url"
    return "unknown"


def _check_known_threats(target: str, target_type: str) -> dict:
    db = KNOWN_MALICIOUS_PATTERNS
    if target_type == "ip" and target in db["ips"]:
        info = db["ips"][target]
        return {"is_malicious": True, "score": info["score"], "categories": info["categories"]}
    if target_type == "domain":
        if target in db["domains"]:
            info = db["domains"][target]
            return {"is_malicious": True, "score": info["score"], "categories": info["categories"]}
        for known_domain, info in db["domains"].items():
            if known_domain in target:
                return {"is_malicious": True, "score": info["score"] * 0.9, "categories": info["categories"]}
    return {"is_malicious": False, "score": 0.0, "categories": []}


def _compute_reputation(target: str, target_type: str, known: dict) -> dict:
    score = known["score"]
    if not known["is_malicious"]:
        hash_val = hash(target) % 100
        if hash_val < 5:
            score = 0.15
        elif hash_val < 15:
            score = 0.05
        else:
            score = 0.0

    is_malicious = known["is_malicious"] or score > 0.7
    return {
        "is_malicious": is_malicious,
        "score": round(score, 3),
        "categories": known["categories"],
        "confidence": round(max(0.5, 1.0 - score * 0.5), 2),
    }


def _generate_recommendations(reputation: dict, external: list[dict] | None = None) -> list[str]:
    recs = []
    if reputation["is_malicious"]:
        recs.append("立即阻断该目标的所有网络连接")
        recs.append("将该目标添加到防火墙黑名单")
        if "c2" in reputation["categories"]:
            recs.append("检查主机是否已被植入后门程序")
        if "phishing" in reputation["categories"]:
            recs.append("通知相关用户检查凭证安全性")
    elif reputation["score"] > 0.3:
        recs.append("持续监控该目标的活动")
        recs.append("考虑限制与该目标的通信频率")
    else:
        recs.append("当前目标信誉良好，建议定期复查")

    # 外部 API 建议
    if external:
        for src in external:
            if src.get("is_malicious"):
                recs.append(f"外部情报源 {src['source']} 标记为恶意 (score: {src.get('score', 'N/A')})")

    return recs


class ThreatIntelService:
    def __init__(self, db: AsyncSession, store: StateStore | None = None):
        self.db = db
        self.store = store
        self._external_clients = []
        self._init_external_clients()

    def _init_external_clients(self):
        settings = get_settings()
        if settings.VIRUSTOTAL_API_KEY:
            from app.integrations.virustotal import VirusTotalClient
            self._external_clients.append(VirusTotalClient(settings.VIRUSTOTAL_API_KEY))
        if settings.ABUSEIPDB_API_KEY:
            from app.integrations.abuseipdb import AbuseIPDBClient
            self._external_clients.append(AbuseIPDBClient(settings.ABUSEIPDB_API_KEY))

    async def query(self, target: str, user_id: int) -> dict:
        target_type = _detect_target_type(target)
        known = _check_known_threats(target, target_type)
        reputation = _compute_reputation(target, target_type, known)

        # 外部 API 查询
        external_results = []
        for client in self._external_clients:
            if client.is_available() and target_type == "ip":
                try:
                    result = await client.lookup(target)
                    external_results.append(result)
                except Exception as e:
                    external_results.append({"source": client.__class__.__name__, "error": str(e)})

        # 黑名单检查
        blacklist_info = None
        if self.store:
            is_blacklisted = await self.store.is_blacklisted(target)
            if is_blacklisted:
                blacklist_info = {"is_blacklisted": True, "sources": []}
                reputation["is_malicious"] = True
                reputation["score"] = max(reputation["score"], 0.8)

        # 持久化
        record = ThreatRecord(
            user_id=user_id,
            target=target,
            target_type=target_type,
            is_malicious=reputation["is_malicious"],
            score=reputation["score"],
            categories=reputation["categories"],
            details={
                "target_type": target_type,
                "known_threat": known["is_malicious"],
                "confidence": reputation["confidence"],
                "external_sources": external_results,
                "blacklist": blacklist_info,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.db.add(record)
        await self.db.commit()

        return {
            "target": target,
            "target_type": target_type,
            "analysis": {
                "is_malicious": reputation["is_malicious"],
                "score": reputation["score"],
                "categories": reputation["categories"],
                "confidence": reputation["confidence"],
            },
            "external_sources": external_results if external_results else None,
            "blacklist": blacklist_info,
            "recommendations": _generate_recommendations(reputation, external_results),
        }

    async def get_history(self, user_id: int, limit: int = 50) -> list[dict]:
        result = await self.db.execute(
            select(ThreatRecord)
            .where(ThreatRecord.user_id == user_id)
            .order_by(ThreatRecord.created_at.desc())
            .limit(limit)
        )
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "target": r.target,
                "target_type": r.target_type,
                "is_malicious": r.is_malicious,
                "score": r.score,
                "categories": r.categories,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]
