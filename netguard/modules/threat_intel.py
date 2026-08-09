import json
import random
import re
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import ThreatRecord


KNOWN_MALICIOUS_PATTERNS = {
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


def _detect_target_type(target: str) -> str:
    ip_pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    if ip_pattern.match(target):
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


def _compute_reputation_score(target: str, target_type: str, known_result: dict) -> dict:
    score = known_result["score"]
    if not known_result["is_malicious"]:
        hash_val = hash(target) % 100
        if hash_val < 5:
            score = random.uniform(0.1, 0.3)
        elif hash_val < 15:
            score = random.uniform(0.01, 0.1)

    return {
        "is_malicious": known_result["is_malicious"] or score > 0.7,
        "score": round(score, 3),
        "categories": known_result["categories"],
        "confidence": round(max(0.5, 1.0 - score * 0.5), 2),
    }


async def query_threat(target: str, user_id: int, db: AsyncSession) -> dict:
    target_type = _detect_target_type(target)
    known_result = _check_known_threats(target, target_type)
    reputation = _compute_reputation_score(target, target_type, known_result)

    record = ThreatRecord(
        user_id=user_id,
        target=target,
        target_type=target_type,
        is_malicious=reputation["is_malicious"],
        score=reputation["score"],
        categories=json.dumps(reputation["categories"]),
        details=json.dumps({
            "target_type": target_type,
            "known_threat": known_result["is_malicious"],
            "confidence": reputation["confidence"],
            "checked_at": datetime.utcnow().isoformat(),
        }),
    )
    db.add(record)
    await db.commit()

    return {
        "target": target,
        "target_type": target_type,
        "analysis": {
            "is_malicious": reputation["is_malicious"],
            "score": reputation["score"],
            "categories": reputation["categories"],
            "confidence": reputation["confidence"],
        },
        "recommendations": _generate_recommendations(reputation),
    }


def _generate_recommendations(reputation: dict) -> list:
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
    return recs


async def get_threat_history(user_id: int, db: AsyncSession, limit: int = 50) -> list:
    result = await db.execute(
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
            "categories": json.loads(r.categories),
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
