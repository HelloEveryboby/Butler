import os
import subprocess
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional

# Attempt to use the BHL native core if available
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from butler.core.hybrid_link import HybridLinkClient

# Try to import bleak for modern BLE interaction (Python fallback)
try:
    from bleak import BleakScanner, BleakClient
except ImportError:
    BleakScanner = None
    BleakClient = None

class BLEConnector:
    """
    Butler 蓝牙低功耗交互工具 (BLE Interaction Tool)
    支持 BHL 原生核心调用与 Python (bleak) 回退。
    """
    def __init__(self):
        self.logger = logging.getLogger("BLEConnector")
        self.ble_exec = os.path.join(PROJECT_ROOT, "programs/ble_framework/ble_framework")
        self.native_client = None
        if os.path.exists(self.ble_exec):
            # Note: ble_framework currently uses command-line args, not JSON-RPC.
            # Here we wrap it in a cleaner Python interface.
            pass

    def _call_native(self, command: str, args: List[str] = []) -> Optional[str]:
        """调用 C++ 编写的 ble_framework 二进制程序"""
        if not os.path.exists(self.ble_exec):
            return None
        try:
            cmd = [self.ble_exec, command] + args
            output = subprocess.check_output(cmd, universal_newlines=True)
            return output
        except Exception as e:
            self.logger.error(f"Native BLE Call Error: {e}")
            return None

    async def scan_ble_devices(self, timeout=5) -> List[Dict[str, Any]]:
        """扫描周边 BLE 设备 (优先使用原生核心)"""
        # 1. 尝试原生核心
        native_res = self._call_native("scan", [str(timeout * 1000)])
        if native_res:
            try:
                data = json.loads(native_res)
                return data.get("results", [])
            except: pass

        # 2. 回退到 Python bleak
        devices = []
        if BleakScanner:
            try:
                scanner = BleakScanner()
                scanned = await scanner.discover(timeout=timeout)
                for d in scanned:
                    devices.append({
                        "name": d.name if d.name else "Unknown",
                        "address": d.address,
                        "rssi": d.rssi
                    })
            except Exception as e:
                self.logger.error(f"Bleak Scan Error: {e}")
        else:
            self.logger.warning("bleak library is not installed and native core failed. BLE scan unavailable.")

        return devices

    def run_scan_sync(self):
        """同步方式运行扫描"""
        try:
            return asyncio.run(self.scan_ble_devices())
        except Exception as e:
            self.logger.error(f"BLE Scan Error: {e}")
            return []

    def connect(self, address: str) -> bool:
        """连接到设备"""
        res = self._call_native("connect", [address])
        if res:
            try:
                return json.loads(res).get("success", False)
            except: pass
        return False

    def get_adapter_status(self) -> Dict[str, str]:
        """获取蓝牙适配器状态"""
        info = {"status": "Off/Unavailable", "name": "N/A"}
        try:
            if os.name == "nt":
                cmd = ["powershell", "Get-PnpDevice -FriendlyName '*Bluetooth*' | Select-Object Status, FriendlyName"]
                output = subprocess.check_output(cmd, universal_newlines=True)
                if "OK" in output:
                    info["status"] = "OK"
                    info["name"] = "Windows Bluetooth Adapter"
            else:
                cmd = ["bluetoothctl", "show"]
                output = subprocess.check_output(cmd, universal_newlines=True)
                if "Powered: yes" in output:
                    info["status"] = "Powered On"
                    info["name"] = "Linux Bluetooth Adapter"
        except Exception:
            pass
        return info

def run():
    """Package 入口"""
    connector = BLEConnector()
    print("[*] 正在检测蓝牙适配器状态...")
    status = connector.get_adapter_status()
    print(json.dumps(status, indent=4, ensure_ascii=False))

    print("\n[*] 正在扫描周边 BLE 设备 (优先调用 BHL 原生核心)...")
    devices = connector.run_scan_sync()
    if not devices:
        print("    - 未发现设备或环境不支持蓝牙扫描。")
    for d in devices:
        print(f"    - [{d.get('rssi', '??')} dBm] {d.get('name', 'Unknown')} ({d.get('address', 'N/A')})")

if __name__ == "__main__":
    run()
