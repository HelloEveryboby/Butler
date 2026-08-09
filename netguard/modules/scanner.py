import json
import socket
import asyncio
import time
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.models import ScanRecord


COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
    443: "HTTPS", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt", 9200: "Elasticsearch",
    27017: "MongoDB",
}


async def scan_port(target: str, port: int, timeout: float = 2.0) -> dict:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(target, port),
            timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return {"port": port, "status": "open", "service": COMMON_PORTS.get(port, "unknown")}
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return {"port": port, "status": "closed", "service": COMMON_PORTS.get(port, "unknown")}


async def port_scan(target: str, port_range: str = "1-1024", user_id: int = 0, db: AsyncSession = None) -> dict:
    start_time = time.time()

    ports = []
    if port_range == "common":
        ports = list(COMMON_PORTS.keys())
    elif "-" in port_range:
        parts = port_range.split("-")
        start, end = int(parts[0]), int(parts[1])
        ports = list(range(start, min(end + 1, 65536)))
    else:
        ports = [int(p.strip()) for p in port_range.split(",")]

    sem = asyncio.Semaphore(50)

    async def limited_scan(port):
        async with sem:
            return await scan_port(target, port)

    tasks = [limited_scan(p) for p in ports]
    results = await asyncio.gather(*tasks)

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

    if db and user_id:
        record = ScanRecord(
            user_id=user_id,
            target=target,
            scan_type="port_scan",
            results=json.dumps(scan_result),
            duration_ms=duration_ms,
        )
        db.add(record)
        await db.commit()

    return scan_result


def detect_service_banner(target: str, port: int, timeout: float = 3.0) -> dict:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((target, port))

        if port in [80, 8080]:
            sock.send(b"HEAD / HTTP/1.0\r\nHost: target\r\n\r\n")
            banner = sock.recv(1024).decode("utf-8", errors="replace")
            service = "HTTP"
        elif port in [443, 8443]:
            service = "HTTPS"
            banner = "TLS endpoint"
        elif port == 22:
            banner = sock.recv(1024).decode("utf-8", errors="replace")
            service = "SSH"
        elif port == 21:
            banner = sock.recv(1024).decode("utf-8", errors="replace")
            service = "FTP"
        elif port == 25:
            sock.send(b"HELO netguard.local\r\n")
            banner = sock.recv(1024).decode("utf-8", errors="replace")
            service = "SMTP"
        elif port == 3306:
            banner = sock.recv(1024).decode("utf-8", errors="replace")
            service = "MySQL"
        else:
            banner = sock.recv(256).decode("utf-8", errors="replace")
            service = COMMON_PORTS.get(port, "unknown")

        sock.close()
        return {"port": port, "service": service, "banner": banner[:200]}
    except Exception as e:
        return {"port": port, "service": "unknown", "banner": str(e)}


async def vulnerability_probe(target: str, user_id: int, db: AsyncSession) -> dict:
    scan_result = await port_scan(target, "common", user_id, db)

    probe_results = []
    for port_info in scan_result["open_ports"]:
        banner_info = detect_service_banner(target, port_info["port"])
        probe_results.append(banner_info)

        vulns = []
        service = banner_info.get("service", "")
        if service == "HTTP" and "Server" in banner_info.get("banner", ""):
            pass
        if port_info["port"] in [21, 23] and port_info["port"] in [21, 23]:
            vulns.append({"severity": "high", "issue": f"Unencrypted protocol on port {port_info['port']}"})
        if port_info["port"] == 3306 and "root" not in banner_info.get("banner", ""):
            pass

    result = {
        "target": target,
        "open_ports_found": scan_result["open_count"],
        "service_probes": probe_results,
        "potential_vulnerabilities": [],
        "risk_level": _assess_risk(scan_result, probe_results),
    }

    if db:
        record = ScanRecord(
            user_id=user_id,
            target=target,
            scan_type="vuln_probe",
            results=json.dumps(result),
            duration_ms=scan_result["duration_ms"],
        )
        db.add(record)
        await db.commit()

    return result


def _assess_risk(scan_result: dict, probe_results: list) -> str:
    risk_score = 0
    open_ports = scan_result.get("open_count", 0)
    risk_score += min(open_ports * 0.1, 0.5)

    for probe in probe_results:
        service = probe.get("service", "")
        if service in ["Telnet", "FTP"]:
            risk_score += 0.2
        elif service in ["MySQL", "PostgreSQL", "Redis", "MongoDB"]:
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


async def get_scan_history(user_id: int, db: AsyncSession, limit: int = 50) -> list:
    result = await db.execute(
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
            "results": json.loads(r.results),
            "duration_ms": r.duration_ms,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
