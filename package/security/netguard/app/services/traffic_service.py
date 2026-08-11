"""流量分析服务"""

import socket
import struct
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.traffic import TrafficAnalysisRecord


def _parse_packet(packet_data: bytes) -> dict:
    """解析 IPv4 数据包"""
    try:
        if len(packet_data) < 40:
            return {"error": "Packet too short"}

        ip_header = packet_data[0:20]
        version_ihl = ip_header[0]
        ip_version = version_ihl >> 4
        ihl = version_ihl & 0x0F

        if ip_version != 4:
            return {"error": "Not IPv4", "ip_version": ip_version}

        protocol = ip_header[9]
        src_ip = socket.inet_ntoa(ip_header[12:16])
        dst_ip = socket.inet_ntoa(ip_header[16:20])
        total_length = struct.unpack("!H", ip_header[2:4])[0]

        result = {
            "ip_version": ip_version,
            "protocol": protocol,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "total_length": total_length,
        }

        if protocol == 6:  # TCP
            transport_header = packet_data[20:40]
            src_port = struct.unpack("!H", transport_header[0:2])[0]
            dst_port = struct.unpack("!H", transport_header[2:4])[0]
            result.update({"transport": "TCP", "src_port": src_port, "dst_port": dst_port})
        elif protocol == 17:  # UDP
            transport_header = packet_data[20:28]
            src_port = struct.unpack("!H", transport_header[0:2])[0]
            dst_port = struct.unpack("!H", transport_header[2:4])[0]
            result.update({"transport": "UDP", "src_port": src_port, "dst_port": dst_port})
        elif protocol == 1:
            result["transport"] = "ICMP"
        else:
            result["transport"] = f"Unknown({protocol})"

        return result
    except Exception as e:
        return {"error": str(e)}


def _analyze_anomalies(parsed_packets: list) -> dict:
    """异常检测"""
    if not parsed_packets:
        return {"anomaly_detected": False, "score": 0.0, "details": {}}

    anomalies = []
    score = 0.0

    src_ips = Counter(p.get("src_ip", "unknown") for p in parsed_packets)
    dst_ips = Counter(p.get("dst_ip", "unknown") for p in parsed_packets)
    protocols = Counter(p.get("transport", p.get("protocol", "unknown")) for p in parsed_packets)
    sizes = [p.get("total_length", 0) for p in parsed_packets]

    unique_sources = len(src_ips)
    unique_dests = len(dst_ips)
    total_packets = len(parsed_packets)

    if total_packets > 100 and unique_sources < 3:
        anomalies.append("High packet volume from few sources (possible DDoS)")
        score += 0.3

    if total_packets > 500:
        anomalies.append("Very high packet count (potential traffic spike)")
        score += 0.2

    if sizes:
        avg_size = sum(sizes) / len(sizes)
        if avg_size < 64 and total_packets > 50:
            anomalies.append("Many small packets (possible SYN flood or scanning)")
            score += 0.2

    tcp_count = protocols.get("TCP", 0)
    if tcp_count > total_packets * 0.9 and total_packets > 100:
        anomalies.append("Predominantly TCP traffic (check for connection floods)")
        score += 0.1

    if unique_dests > total_packets * 0.8 and total_packets > 50:
        anomalies.append("Traffic to many different destinations (possible scanning)")
        score += 0.15

    score = min(score, 1.0)

    return {
        "anomaly_detected": score > 0.3,
        "anomaly_score": round(score, 3),
        "details": {
            "total_packets": total_packets,
            "unique_sources": unique_sources,
            "unique_destinations": unique_dests,
            "protocol_distribution": dict(protocols),
            "avg_packet_size": round(sum(sizes) / max(len(sizes), 1), 1),
            "anomalies_found": anomalies,
        },
    }


def _traffic_recommendations(analysis: dict) -> list[str]:
    recs = []
    details = analysis["details"]
    if analysis["anomaly_detected"]:
        if any("DDoS" in a for a in details.get("anomalies_found", [])):
            recs.append("启用 DDoS 防护规则，限制单源 IP 流量")
        if any("scanning" in a for a in details.get("anomalies_found", [])):
            recs.append("检测到扫描行为，建议启用端口扫描检测")
        if any("flood" in a.lower() for a in details.get("anomalies_found", [])):
            recs.append("可能存在 Flood 攻击，建议启用 SYN Cookie")
    else:
        recs.append("流量正常，继续保持监控")
    return recs


class TrafficService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_packets(
        self, packet_data_list: list[str], user_id: int
    ) -> dict:
        """分析数据包"""
        parsed_packets = []
        for data in packet_data_list:
            if isinstance(data, str):
                data = bytes.fromhex(data)
            parsed = _parse_packet(data)
            if "error" not in parsed:
                parsed_packets.append(parsed)

        analysis = _analyze_anomalies(parsed_packets)

        # 批量写入
        for pkt in parsed_packets:
            record = TrafficAnalysisRecord(
                user_id=user_id,
                source_ip=pkt.get("src_ip", "0.0.0.0"),
                dest_ip=pkt.get("dst_ip", "0.0.0.0"),
                protocol=pkt.get("transport", "UNKNOWN"),
                anomaly_detected=analysis["anomaly_detected"],
                anomaly_score=analysis["anomaly_score"],
                details={
                    "src_port": pkt.get("src_port"),
                    "dst_port": pkt.get("dst_port"),
                    "anomalies": analysis["details"].get("anomalies_found", []),
                },
            )
            self.db.add(record)
        await self.db.commit()

        return {
            "total_packets_analyzed": len(parsed_packets),
            "anomaly_detected": analysis["anomaly_detected"],
            "anomaly_score": analysis["anomaly_score"],
            "analysis": analysis["details"],
            "recommendations": _traffic_recommendations(analysis),
        }

    async def get_history(self, user_id: int, limit: int = 50) -> list[dict]:
        result = await self.db.execute(
            select(TrafficAnalysisRecord)
            .where(TrafficAnalysisRecord.user_id == user_id)
            .order_by(TrafficAnalysisRecord.created_at.desc())
            .limit(limit)
        )
        records = result.scalars().all()
        return [
            {
                "id": r.id,
                "source_ip": r.source_ip,
                "dest_ip": r.dest_ip,
                "protocol": r.protocol,
                "anomaly_detected": r.anomaly_detected,
                "anomaly_score": r.anomaly_score,
                "details": r.details,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]
