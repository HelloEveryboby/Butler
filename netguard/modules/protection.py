import json
import re
import time
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import ProtectionEvent


ip_request_log = defaultdict(list)
blocked_ips = set()
rate_limit_rules = {}

DEFAULT_RULES = {
    "ddos_threshold": 100,
    "ddos_window_seconds": 10,
    "port_scan_threshold": 20,
    "brute_force_threshold": 5,
    "brute_force_window_seconds": 60,
}


def _check_ddos(source_ip: str, rules: dict) -> dict:
    now = time.time()
    window = rules.get("ddos_window_seconds", DEFAULT_RULES["ddos_window_seconds"])
    threshold = rules.get("ddos_threshold", DEFAULT_RULES["ddos_threshold"])

    if source_ip not in ip_request_log:
        ip_request_log[source_ip] = []

    ip_request_log[source_ip] = [t for t in ip_request_log[source_ip] if now - t < window]
    ip_request_log[source_ip].append(now)

    count = len(ip_request_log[source_ip])
    if count >= threshold:
        return {
            "detected": True,
            "attack_type": "DDoS",
            "request_count": count,
            "threshold": threshold,
            "action": "block",
        }
    return {"detected": False}


def _check_port_scan(source_ip: str, target_port: int, rules: dict) -> dict:
    threshold = rules.get("port_scan_threshold", DEFAULT_RULES["port_scan_threshold"])
    scan_key = f"scan_{source_ip}"
    if scan_key not in ip_request_log:
        ip_request_log[scan_key] = []

    ports_attempted = set(ip_request_log[scan_key])
    ports_attempted.add(target_port)
    ip_request_log[scan_key] = list(ports_attempted)

    if len(ports_attempted) >= threshold:
        return {
            "detected": True,
            "attack_type": "Port Scan",
            "ports_attempted": len(ports_attempted),
            "threshold": threshold,
            "action": "block",
        }
    return {"detected": False}


def _check_brute_force(source_ip: str, rules: dict) -> dict:
    now = time.time()
    window = rules.get("brute_force_window_seconds", DEFAULT_RULES["brute_force_window_seconds"])
    threshold = rules.get("brute_force_threshold", DEFAULT_RULES["brute_force_threshold"])
    bf_key = f"bf_{source_ip}"

    if bf_key not in ip_request_log:
        ip_request_log[bf_key] = []

    ip_request_log[bf_key] = [t for t in ip_request_log[bf_key] if now - t < window]
    ip_request_log[bf_key].append(now)

    count = len(ip_request_log[bf_key])
    if count >= threshold:
        return {
            "detected": True,
            "attack_type": "Brute Force",
            "attempt_count": count,
            "threshold": threshold,
            "action": "block",
        }
    return {"detected": False}


def _check_sql_injection(payload: str) -> dict:
    sqli_patterns = [
        r"(?i)(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b.*\b(FROM|INTO|TABLE)\b)",
        r"(?i)(--|#|/\*|\*/|;--|;DROP|;--x)",
        r"(?i)('\s*(OR|AND)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+)",
        r"(?i)(UNION\s+SELECT)",
        r"(?i)(SLEEP|BENCHMARK|WAITFOR\s+DELAY)",
        r"(?i)(INFORMATION_SCHEMA|SYS\.TABLES|PG_SLEEP)",
    ]
    for pattern in sqli_patterns:
        if re.search(pattern, payload):
            return {
                "detected": True,
                "attack_type": "SQL Injection",
                "matched_pattern": pattern,
                "action": "block",
            }
    return {"detected": False}


def _check_xss(payload: str) -> dict:
    xss_patterns = [
        r"(?i)<\s*script[^>]*>",
        r"(?i)javascript\s*:",
        r"(?i)on\w+\s*=\s*['\"]",
        r"(?i)<\s*img[^>]+onerror",
        r"(?i)document\.cookie",
        r"(?i)<\s*iframe",
        r"(?i)eval\s*\(",
        r"(?i)alert\s*\(",
    ]
    for pattern in xss_patterns:
        if re.search(pattern, payload):
            return {
                "detected": True,
                "attack_type": "XSS",
                "matched_pattern": pattern,
                "action": "block",
            }
    return {"detected": False}


async def analyze_request(
    source_ip: str,
    target_url: str = "",
    payload: str = "",
    target_port: int = 0,
    user_id: int = 0,
    db: AsyncSession = None,
) -> dict:
    rules = rate_limit_rules.copy()
    rules.update(DEFAULT_RULES)

    results = []

    ddos_result = _check_ddos(source_ip, rules)
    if ddos_result["detected"]:
        results.append(ddos_result)

    if target_port:
        scan_result = _check_port_scan(source_ip, target_port, rules)
        if scan_result["detected"]:
            results.append(scan_result)

    brute_result = _check_brute_force(source_ip, rules)
    if brute_result["detected"]:
        results.append(brute_result)

    if payload:
        sqli_result = _check_sql_injection(payload)
        if sqli_result["detected"]:
            results.append(sqli_result)

        xss_result = _check_xss(payload)
        if xss_result["detected"]:
            results.append(xss_result)

    if results:
        blocked = True
        for r in results:
            if r.get("action") == "block":
                blocked = True
                break
    else:
        blocked = False

    if blocked:
        blocked_ips.add(source_ip)

    event = ProtectionEvent(
        user_id=user_id,
        event_type=", ".join(r["attack_type"] for r in results) if results else "clean",
        source_ip=source_ip,
        blocked=blocked,
        action_taken="block" if blocked else "allow",
        details=json.dumps({
            "detections": results,
            "target_url": target_url,
            "target_port": target_port,
            "analyzed_at": datetime.utcnow().isoformat(),
        }),
    )

    if db:
        db.add(event)
        await db.commit()

    return {
        "source_ip": source_ip,
        "blocked": blocked,
        "detections": results,
        "action": "block" if blocked else "allow",
        "recommendations": _protection_recommendations(results, blocked),
    }


def _protection_recommendations(results: list, blocked: bool) -> list:
    recs = []
    if not results:
        recs.append("请求安全，建议继续保持监控")
        return recs

    for r in results:
        attack = r.get("attack_type", "")
        if attack == "DDoS":
            recs.append("启用 DDoS 防护：配置速率限制和流量清洗")
        elif attack == "Port Scan":
            recs.append("检测到端口扫描：建议配置端口扫描检测规则")
        elif attack == "Brute Force":
            recs.append("检测到暴力破解：建议启用账号锁定机制和验证码")
        elif attack == "SQL Injection":
            recs.append("检测到 SQL 注入：建议使用参数化查询，启用 WAF 规则")
        elif attack == "XSS":
            recs.append("检测到 XSS 攻击：建议对用户输入进行转义，启用 CSP")

    if blocked:
        recs.append("已自动阻断恶意请求")
    return recs


async def get_blocked_ips() -> list:
    return list(blocked_ips)


async def unblock_ip(ip: str, user_id: int, db: AsyncSession = None) -> dict:
    blocked_ips.discard(ip)
    event = ProtectionEvent(
        user_id=user_id,
        event_type="unblock",
        source_ip=ip,
        blocked=False,
        action_taken="unblock",
        details=json.dumps({"message": f"IP {ip} has been unblocked"}),
    )
    if db:
        db.add(event)
        await db.commit()
    return {"ip": ip, "status": "unblocked"}


async def get_protection_history(user_id: int, db: AsyncSession, limit: int = 50) -> list:
    result = await db.execute(
        select(ProtectionEvent)
        .where(ProtectionEvent.user_id == user_id)
        .order_by(ProtectionEvent.created_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "source_ip": r.source_ip,
            "blocked": r.blocked,
            "action_taken": r.action_taken,
            "details": json.loads(r.details),
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


def update_rules(new_rules: dict) -> dict:
    global rate_limit_rules
    rate_limit_rules.update(new_rules)
    return {"status": "updated", "rules": {**DEFAULT_RULES, **rate_limit_rules}}


def get_rules() -> dict:
    return {**DEFAULT_RULES, **rate_limit_rules}
