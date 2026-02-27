import os
import shutil
import json
import logging
import subprocess
from typing import Dict, List, Any, Optional

# Attempt to use BHL native core if available
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from butler.core.hybrid_link import HybridLinkClient

# Try to import psutil for advanced disk statistics
try:
    import psutil
except ImportError:
    psutil = None

class DiskManager:
    """
    Butler 硬盘交互与监控工具 (Disk Interaction & Monitor Tool)
    支持 BHL 原生核心调用与 Python 回退。
    """
    def __init__(self):
        self.logger = logging.getLogger("DiskManager")
        self.sysutil_path = os.path.join(PROJECT_ROOT, "programs/hybrid_sysutil/sysutil")
        self.native_client = None
        if os.path.exists(self.sysutil_path):
            self.native_client = HybridLinkClient(self.sysutil_path)

    def get_disk_usage(self) -> List[Dict[str, Any]]:
        """获取所有分区的磁盘使用情况 (优先使用 BHL 原生核心)"""
        # 1. 尝试 BHL
        if self.native_client:
            try:
                self.native_client.start()
                res = self.native_client.call("get_disk_usage", {})
                self.native_client.stop()
                if res and "partitions" in res:
                    return res["partitions"]
            except Exception as e:
                self.logger.debug(f"BHL Disk Usage failed: {e}. Falling back...")

        # 2. 回退到 Python
        usage_list = []
        try:
            if psutil:
                partitions = psutil.disk_partitions()
                for part in partitions:
                    if os.name == 'nt' and 'cdrom' in part.opts: continue
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        usage_list.append({
                            "device": part.device,
                            "mount": part.mountpoint,
                            "total": f"{usage.total / (1024**3):.2f} GB",
                            "used": f"{usage.used / (1024**3):.2f} GB",
                            "free": f"{usage.free / (1024**3):.2f} GB",
                            "percent": usage.percent
                        })
                    except Exception: continue
            else:
                total, used, free = shutil.disk_usage("/")
                usage_list.append({
                    "device": "Root (shutil fallback)",
                    "mount": "/",
                    "total": f"{total / (1024**3):.2f} GB",
                    "used": f"{used / (1024**3):.2f} GB",
                    "free": f"{free / (1024**3):.2f} GB",
                    "percent": f"{(used/total)*100:.2f}%"
                })
        except Exception as e:
            self.logger.error(f"Disk Usage Error: {e}")

        return usage_list

    def get_smart_status(self) -> str:
        """简单的硬盘健康状态检测"""
        try:
            if os.name == "nt":
                cmd = ["wmic", "diskdrive", "get", "status"]
                output = subprocess.check_output(cmd, universal_newlines=True)
                lines = output.strip().splitlines()
                if len(lines) > 1: return f"Smart Status: {lines[-1].strip()}"
            else:
                return "Smart Status: Check requires smartmontools"
        except Exception: pass
        return "Smart Status: Unavailable"

def run():
    """Package 入口"""
    manager = DiskManager()
    print("[*] 正在分析硬盘分区使用情况 (优先调用 BHL 原生核心)...")
    usage = manager.get_disk_usage()
    print(json.dumps(usage, indent=4, ensure_ascii=False))

    print(f"\n[*] 正在检测硬盘健康状态 (SMART)...")
    res = manager.get_smart_status()
    print(res)

if __name__ == "__main__":
    run()
