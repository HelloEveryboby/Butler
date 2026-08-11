"""流量抓包服务"""

import asyncio
import io
import os
import tempfile
import time
from datetime import datetime, timezone


class CaptureService:
    """网络流量抓包（需要 root 权限或 pcap 权限）"""

    async def capture(self, interface: str = "eth0", duration: int = 10,
                      filter_expr: str = "", packet_count: int = 100) -> dict:
        """
        抓包并返回统计信息。
        注意：需要 root 权限或 CAP_NET_RAW 能力。
        """
        try:
            from scapy.all import sniff, wrpcap, TCP, UDP, ICMP, IP
        except ImportError:
            return {"error": "scapy not installed", "hint": "pip install scapy"}

        start_time = time.time()

        try:
            # 异步执行抓包（scapy 是同步的）
            packets = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sniff(
                    iface=interface,
                    timeout=duration,
                    count=packet_count,
                    filter=filter_expr if filter_expr else None,
                ),
            )
        except PermissionError:
            return {"error": "Permission denied", "hint": "Run with root or set CAP_NET_RAW"}
        except Exception as e:
            return {"error": str(e)}

        # 分析抓包结果
        stats = {
            "total_packets": len(packets),
            "duration_seconds": round(time.time() - start_time, 2),
            "interface": interface,
            "filter": filter_expr,
            "protocols": {},
            "top_sources": {},
            "top_destinations": {},
            "total_bytes": 0,
        }

        for pkt in packets:
            # 协议统计
            if pkt.haslayer(TCP):
                stats["protocols"]["TCP"] = stats["protocols"].get("TCP", 0) + 1
            elif pkt.haslayer(UDP):
                stats["protocols"]["UDP"] = stats["protocols"].get("UDP", 0) + 1
            elif pkt.haslayer(ICMP):
                stats["protocols"]["ICMP"] = stats["protocols"].get("ICMP", 0) + 1
            else:
                stats["protocols"]["Other"] = stats["protocols"].get("Other", 0) + 1

            # IP 统计
            if pkt.haslayer(IP):
                src = pkt[IP].src
                dst = pkt[IP].dst
                stats["top_sources"][src] = stats["top_sources"].get(src, 0) + 1
                stats["top_destinations"][dst] = stats["top_destinations"].get(dst, 0) + 1

            stats["total_bytes"] += len(pkt)

        # 排序 top 10
        stats["top_sources"] = dict(sorted(stats["top_sources"].items(), key=lambda x: -x[1])[:10])
        stats["top_destinations"] = dict(sorted(stats["top_destinations"].items(), key=lambda x: -x[1])[:10])

        # 保存 pcap 文件
        pcap_path = None
        if packets:
            fd, pcap_path = tempfile.mkstemp(suffix=".pcap", prefix="netguard_")
            os.close(fd)
            wrpcap(pcap_path, packets)
            stats["pcap_file"] = pcap_path

        stats["captured_at"] = datetime.now(timezone.utc).isoformat()
        return stats
