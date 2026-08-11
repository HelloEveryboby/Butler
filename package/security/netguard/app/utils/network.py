"""网络工具：IP/域名校验、端口解析、SSRF 防护"""

import ipaddress
import re

# ── 内网地址段（扫描禁止） ──
PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# ── 常见端口 ──
COMMON_PORTS = {
    21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP",
    443: "HTTPS", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt",
    9200: "Elasticsearch", 27017: "MongoDB",
}

# ── 目标类型检测 ──
_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$")


def detect_target_type(target: str) -> str:
    """检测目标类型：ip / domain / url / unknown"""
    if _IP_RE.match(target):
        return "ip"
    if target.startswith(("http://", "https://")):
        return "url"
    if "." in target and _DOMAIN_RE.match(target):
        return "domain"
    return "unknown"


def validate_scan_target(target: str) -> str:
    """
    校验扫描目标，防止 SSRF。
    - 禁止扫描内网地址
    - 禁止明显非法格式
    """
    # 去掉协议前缀
    clean = target
    for prefix in ("http://", "https://"):
        if clean.startswith(prefix):
            clean = clean[len(prefix):]
    clean = clean.split("/")[0].split(":")[0]  # 取 host 部分

    try:
        ip = ipaddress.ip_address(clean)
        for network in PRIVATE_NETWORKS:
            if ip in network:
                raise ValueError(
                    f"Scanning private/reserved networks is not allowed: {target}"
                )
        return target
    except ValueError as e:
        if "not allowed" in str(e):
            raise
        # 不是 IP，当域名处理
        if not _DOMAIN_RE.match(clean):
            raise ValueError(f"Invalid target format: {target}")
        return target


def parse_port_range(port_range: str) -> list[int]:
    """
    安全解析端口范围。
    - "common" → 常见端口列表
    - "1-1024" → 范围
    - "80,443,8080" → 列表
    """
    if port_range == "common":
        return list(COMMON_PORTS.keys())

    if "-" in port_range:
        parts = port_range.split("-", 1)
        start, end = int(parts[0]), int(parts[1])
        if not (1 <= start <= 65535 and 1 <= end <= 65535 and start <= end):
            raise ValueError(f"Invalid port range: {port_range}")
        return list(range(start, min(end + 1, 65536)))

    ports = [int(p.strip()) for p in port_range.split(",")]
    if not all(1 <= p <= 65535 for p in ports):
        raise ValueError("Port out of valid range (1-65535)")
    return ports
