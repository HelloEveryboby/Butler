"""扫描服务 — 全异步"""

import asyncio
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import ScanRecord
from app.utils.network import COMMON_PORTS, parse_port_range, validate_scan_target


async def _scan_port(target: str, port: int, timeout: float = 2.0) -> dict:
    """异步扫描单个端口"""
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(target, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return {"port": port, "status": "open", "service": COMMON_PORTS.get(port, "unknown")}
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return {"port": port, "status": "closed", "service": COMMON_PORTS.get(port, "unknown")}


async def _detect_banner(target: str, port: int, timeout: float = 3.0) -> dict:
    """全异步 Banner 抓取"""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(target, port), timeout=timeout
        )

        banner = b""
        service = COMMON_PORTS.get(port, "unknown")

        if port in (80, 8080):
            writer.write(b"HEAD / HTTP/1.0\r\nHost: target\r\n\r\n")
            await writer.drain()
            banner = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            service = "HTTP"
        elif port in (443, 8443):
            service = "HTTPS"
            banner = b"TLS endpoint"
        elif port == 22:
            banner = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            service = "SSH"
        elif port == 21:
            banner = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            service = "FTP"
        elif port == 25:
            writer.write(b"HELO netguard.local\r\n")
            await writer.drain()
            banner = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            service = "SMTP"
        elif port == 3306:
            banner = await asyncio.wait_for(reader.read(1024), timeout=timeout)
            service = "MySQL"
        else:
            try:
                banner = await asyncio.wait_for(reader.read(256), timeout=1.0)
            except asyncio.TimeoutError:
                pass

        writer.close()
        await writer.wait_closed()

        return {
            "port": port,
            "service": service,
            "banner": banner.decode("utf-8", errors="replace")[:200],
        }
    except Exception as e:
        return {"port": port, "service": "unknown", "banner": str(e)}


def _assess_risk(scan_result: dict, probe_results: list) -> str:
    """评估目标风险等级"""
    risk_score = 0.0
    open_ports = scan_result.get("open_count", 0)
    risk_score += min(open_ports * 0.1, 0.5)

    for probe in probe_results:
        service = probe.get("service", "")
        if service in ("Telnet", "FTP"):
            risk_score += 0.2
        elif service in ("MySQL", "PostgreSQL", "Redis", "MongoDB"):
            risk_score += 0.15
        elif service == "HTTP":
            risk_score += 0.05

    if risk_score >= 0.7:
        return "high"
    elif risk_score >= 0.4:
        return "medium"
    elif risk_score >= 0.2:
        return "low"
    return "minimal"


class ScanService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def port_scan(
        self, target: str, port_range: str, user_id: int
    ) -> dict:
        """端口扫描"""
        target = validate_scan_target(target)
        start_time = time.time()

        ports = parse_port_range(port_range)
        sem = asyncio.Semaphore(50)

        async def limited_scan(port):
            async with sem:
                return await _scan_port(target, port)

        results = await asyncio.gather(*[limited_scan(p) for p in ports])
        open_ports = [r for r in results if r["status"] == "open"]
        duration_ms = int((time.time() - start_time) * 1000)

        scan_result = {
            "target": target,
            "scan_type": "port_scan",
            "total_ports": len(ports),
            "open_ports": open_ports,
            "open_count": len(open_ports),
            "duration_ms": duration_ms,
        }

        # 持久化
        record = ScanRecord(
            user_id=user_id,
            target=target,
            scan_type="port_scan",
            results=scan_result,
            duration_ms=duration_ms,
        )
        self.db.add(record)
        await self.db.commit()

        return scan_result

    async def vulnerability_probe(
        self, target: str, user_id: int
    ) -> dict:
        """漏洞探测"""
        target = validate_scan_target(target)

        # 先做常见端口扫描
        scan_result = await self.port_scan(target, "common", user_id)
        # 注意：port_scan 已经 commit 了一条记录，这里不需要重复

        probe_results = []
        vulnerabilities = []

        for port_info in scan_result["open_ports"]:
            banner_info = await _detect_banner(target, port_info["port"])
            probe_results.append(banner_info)

            # 检测漏洞
            service = banner_info.get("service", "")
            port = banner_info["port"]

            if port in (21, 23):
                vulnerabilities.append({
                    "severity": "high",
                    "issue": f"Unencrypted protocol ({service}) on port {port}",
                })
            if service in ("MySQL", "PostgreSQL", "Redis", "MongoDB"):
                vulnerabilities.append({
                    "severity": "medium",
                    "issue": f"Database service ({service}) exposed on port {port}",
                })

        result = {
            "target": target,
            "open_ports_found": scan_result["open_count"],
            "service_probes": probe_results,
            "potential_vulnerabilities": vulnerabilities,
            "risk_level": _assess_risk(scan_result, probe_results),
        }

        # 写一条 vuln_probe 记录
        record = ScanRecord(
            user_id=user_id,
            target=target,
            scan_type="vuln_probe",
            results=result,
            duration_ms=scan_result["duration_ms"],
        )
        self.db.add(record)
        await self.db.commit()

        return result

    async def get_history(self, user_id: int, limit: int = 50) -> list[dict]:
        result = await self.db.execute(
            select(ScanRecord)
            .where(ScanRecord.user_id == user_id)
            .order_by(ScanRecord.created_at.desc())
            .limit(limit)
        )
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "target": r.target,
                "scan_type": r.scan_type,
                "results": r.results,
                "duration_ms": r.duration_ms,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]
