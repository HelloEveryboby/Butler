"""防护服务 — 使用 StateStore 替代进程内存"""

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts import alert_manager
from app.models.protection import ProtectionEvent
from app.store.base import StateStore


class ProtectionService:
    def __init__(self, db: AsyncSession, store: StateStore):
        self.db = db
        self.store = store

    @property
    async def _rules(self) -> dict:
        defaults = {
            "ddos_threshold": 100,
            "ddos_window_seconds": 10,
            "port_scan_threshold": 20,
            "brute_force_threshold": 5,
            "brute_force_window_seconds": 60,
        }
        stored = await self.store.get_rules()
        return {**defaults, **stored}

    # ── 检测方法 ──

    async def _check_ddos(self, source_ip: str, rules: dict) -> dict:
        window = rules.get("ddos_window_seconds", 10)
        threshold = rules.get("ddos_threshold", 100)
        count = await self.store.increment_counter(f"ddos:{source_ip}", window)
        if count >= threshold:
            return {
                "detected": True, "attack_type": "DDoS",
                "request_count": count, "threshold": threshold, "action": "block",
            }
        return {"detected": False}

    async def _check_port_scan(self, source_ip: str, target_port: int, rules: dict) -> dict:
        threshold = rules.get("port_scan_threshold", 20)
        count = await self.store.increment_counter(f"scan:{source_ip}:{target_port}", 300)
        if count >= threshold:
            return {
                "detected": True, "attack_type": "Port Scan",
                "ports_attempted": count, "threshold": threshold, "action": "block",
            }
        return {"detected": False}

    async def _check_brute_force(self, source_ip: str, rules: dict) -> dict:
        window = rules.get("brute_force_window_seconds", 60)
        threshold = rules.get("brute_force_threshold", 5)
        count = await self.store.increment_counter(f"bf:{source_ip}", window)
        if count >= threshold:
            return {
                "detected": True, "attack_type": "Brute Force",
                "attempt_count": count, "threshold": threshold, "action": "block",
            }
        return {"detected": False}

    @staticmethod
    def _check_sql_injection(payload: str) -> dict:
        patterns = [
            r"(?i)(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b.*\b(FROM|INTO|TABLE)\b)",
            r"(?i)(--|#|/\*|\*/|;--|;DROP|;--x)",
            r"(?i)('\s*(OR|AND)\s+['\"]?\d+['\"]?\s*=\s*['\"]?\d+)",
            r"(?i)(UNION\s+SELECT)",
            r"(?i)(SLEEP|BENCHMARK|WAITFOR\s+DELAY)",
            r"(?i)(INFORMATION_SCHEMA|SYS\.TABLES|PG_SLEEP)",
        ]
        for pattern in patterns:
            if re.search(pattern, payload):
                return {
                    "detected": True, "attack_type": "SQL Injection",
                    "matched_pattern": pattern, "action": "block",
                }
        return {"detected": False}

    @staticmethod
    def _check_xss(payload: str) -> dict:
        patterns = [
            r"(?i)<\s*script[^>]*>",
            r"(?i)javascript\s*:",
            r"(?i)on\w+\s*=\s*['\"]",
            r"(?i)<\s*img[^>]+onerror",
            r"(?i)document\.cookie",
            r"(?i)<\s*iframe",
            r"(?i)eval\s*\(",
            r"(?i)alert\s*\(",
        ]
        for pattern in patterns:
            if re.search(pattern, payload):
                return {
                    "detected": True, "attack_type": "XSS",
                    "matched_pattern": pattern, "action": "block",
                }
        return {"detected": False}

    # ── 主分析方法 ──

    async def analyze(
        self,
        source_ip: str,
        target_url: str = "",
        payload: str = "",
        target_port: int = 0,
        user_id: int = 0,
    ) -> dict:
        rules = await self._rules
        detections = []

        ddos = await self._check_ddos(source_ip, rules)
        if ddos["detected"]:
            detections.append(ddos)

        if target_port:
            scan = await self._check_port_scan(source_ip, target_port, rules)
            if scan["detected"]:
                detections.append(scan)

        brute = await self._check_brute_force(source_ip, rules)
        if brute["detected"]:
            detections.append(brute)

        if payload:
            sqli = self._check_sql_injection(payload)
            if sqli["detected"]:
                detections.append(sqli)
            xss = self._check_xss(payload)
            if xss["detected"]:
                detections.append(xss)

        blocked = any(r.get("action") == "block" for r in detections)
        if blocked:
            await self.store.block_ip(source_ip, 3600)

        # 持久化
        event = ProtectionEvent(
            user_id=user_id,
            event_type=", ".join(r["attack_type"] for r in detections) or "clean",
            source_ip=source_ip,
            blocked=blocked,
            action_taken="block" if blocked else "allow",
            details={
                "detections": detections,
                "target_url": target_url,
                "target_port": target_port,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.db.add(event)
        await self.db.commit()

        # WebSocket 告警
        if blocked:
            await alert_manager.send_alert(user_id, {
                "type": "attack_blocked",
                "source_ip": source_ip,
                "attacks": [d["attack_type"] for d in detections],
                "action": "block",
            })

        return {
            "source_ip": source_ip,
            "blocked": blocked,
            "detections": detections,
            "action": "block" if blocked else "allow",
            "recommendations": self._recommendations(detections, blocked),
        }

    @staticmethod
    def _recommendations(results: list, blocked: bool) -> list[str]:
        if not results:
            return ["请求安全，建议继续保持监控"]

        recs = []
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

    # ── 管理方法 ──

    async def get_blocked_ips(self) -> list[str]:
        return await self.store.get_blocked_ips()

    async def unblock_ip(self, ip: str, user_id: int) -> dict:
        await self.store.unblock_ip(ip)
        event = ProtectionEvent(
            user_id=user_id,
            event_type="unblock",
            source_ip=ip,
            blocked=False,
            action_taken="unblock",
            details={"message": f"IP {ip} has been unblocked"},
        )
        self.db.add(event)
        await self.db.commit()
        return {"ip": ip, "status": "unblocked"}

    async def get_history(self, user_id: int, limit: int = 50) -> list[dict]:
        result = await self.db.execute(
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
                "details": r.details,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]

    async def update_rules(self, new_rules: dict) -> dict:
        for k, v in new_rules.items():
            await self.store.set_rule(k, v)
        rules = await self._rules
        return {"status": "updated", "rules": rules}

    async def get_rules(self) -> dict:
        return await self._rules
