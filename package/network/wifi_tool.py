import os
import subprocess
import json
import logging
from typing import List, Dict, Any, Optional

# Attempt to use BHL native core if available
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from butler.core.hybrid_link import HybridLinkClient

class WiFiTool:
    """
    Butler WiFi 交互工具 (WiFi Interaction Tool)
    支持 BHL 原生核心调用与 Python 回退。
    """
    def __init__(self):
        self.logger = logging.getLogger("WiFiTool")
        self.sysutil_path = os.path.join(PROJECT_ROOT, "programs/hybrid_sysutil/sysutil")
        self.native_client = None
        if os.path.exists(self.sysutil_path):
            self.native_client = HybridLinkClient(self.sysutil_path)

    def scan_networks(self) -> List[Dict[str, str]]:
        """扫描周边 WiFi 网络 (优先使用 BHL 原生核心)"""
        # 1. 尝试 BHL
        if self.native_client:
            try:
                self.native_client.start()
                res = self.native_client.call("scan_wifi", {})
                self.native_client.stop()
                if res and "networks" in res:
                    return res["networks"]
            except Exception as e:
                self.logger.debug(f"BHL WiFi Scan failed: {e}. Falling back...")

        # 2. 回退到 Python
        networks = []
        try:
            if os.name == "nt":
                cmd = ["netsh", "wlan", "show", "networks", "mode=bssid"]
                output = subprocess.check_output(cmd, universal_newlines=True, encoding='gbk', errors='ignore')
                lines = output.splitlines()
                for line in lines:
                    if "SSID" in line and ":" in line:
                        ssid = line.split(":", 1)[1].strip()
                        if ssid: networks.append({"ssid": ssid})
            else:
                cmd = ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi"]
                output = subprocess.check_output(cmd, universal_newlines=True)
                for line in output.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 3:
                        networks.append({"ssid": parts[0], "signal": parts[1], "security": parts[2]})
        except Exception as e:
            self.logger.error(f"WiFi Scan Error: {e}")

        return networks

    def get_current_connection(self) -> Dict[str, str]:
        """获取当前连接的 WiFi 信息"""
        info = {"status": "Disconnected", "ssid": "N/A", "signal": "N/A"}
        try:
            if os.name == "nt":
                cmd = ["netsh", "wlan", "show", "interfaces"]
                output = subprocess.check_output(cmd, universal_newlines=True, encoding='gbk', errors='ignore')
                for line in output.splitlines():
                    if " SSID" in line and ":" in line:
                        info["ssid"] = line.split(":", 1)[1].strip()
                        info["status"] = "Connected"
                    if "信号" in line or "Signal" in line:
                        info["signal"] = line.split(":", 1)[1].strip()
            else:
                cmd = ["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "dev", "wifi"]
                output = subprocess.check_output(cmd, universal_newlines=True)
                for line in output.splitlines():
                    if line.startswith("yes"):
                        parts = line.split(":")
                        info["status"] = "Connected"
                        info["ssid"] = parts[1]
                        info["signal"] = parts[2]
        except Exception: pass
        return info

def run():
    """Package 入口"""
    tool = WiFiTool()
    print("[*] 正在检查当前 WiFi 连接状态...")
    conn = tool.get_current_connection()
    print(json.dumps(conn, indent=4, ensure_ascii=False))

    print("\n[*] 正在扫描周边可用网络 (优先调用 BHL 原生核心)...")
    nets = tool.scan_networks()
    for n in nets[:10]:
        print(f"    - SSID: {n.get('ssid')} | 信号: {n.get('signal', '??')}")

if __name__ == "__main__":
    run()
