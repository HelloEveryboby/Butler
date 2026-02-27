import os
import time
import subprocess
import threading
import json
import logging
import socket
from typing import Dict, List, Any

# Try to import psutil for advanced connection monitoring
try:
    import psutil
except ImportError:
    psutil = None

class NetworkSecurityMonitor:
    """
    Butler 网络安全与卡顿监测系统 (Network Security & Performance Monitor)
    功能：
    1. 实时延迟监测：检测电脑与手机常用网络节点的延迟与丢包率。
    2. 卡顿原因分析：区分是网络带宽不足、高延迟还是潜在的恶意干扰。
    3. 安全扫描：监测异常的连接高峰或可疑的本地连接（简单防破坏检测）。
    4. 自动告警：当网络环境显著恶化时提醒用户。
    """

    def __init__(self, target_hosts=["8.8.8.8", "114.114.114.114", "www.baidu.com"]):
        self.target_hosts = target_hosts
        self.logger = logging.getLogger("NetMonitor")
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.monitoring = False
        self.stats = {host: {"latency": [], "loss": 0} for host in target_hosts}
        self.last_alerts = []

    def ping_host(self, host: str) -> Dict[str, Any]:
        """执行 Ping 操作获取延迟和丢包"""
        param = "-n" if os.name == "nt" else "-c"
        command = ["ping", param, "3", host]

        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT, universal_newlines=True)
            # 解析延迟（这里简化解析，不同系统输出略有不同）
            if os.name == "nt":
                lines = output.splitlines()
                # 寻找 "平均 = 20ms" 或类似的行
                avg_latency = -1
                for line in lines:
                    if "平均" in line or "Average" in line:
                        avg_latency = float(line.split("=")[-1].strip().replace("ms", ""))
                return {"latency": avg_latency, "status": "OK" if avg_latency != -1 else "Fail"}
            else:
                # Linux/Mac 解析
                if "avg" in output:
                    avg_latency = float(output.split("avg/")[1].split("/")[1])
                    return {"latency": avg_latency, "status": "OK"}
        except Exception:
            pass
        return {"latency": -1, "status": "Timeout/Fail"}

    def check_suspicious_connections(self) -> List[str]:
        """检测可疑连接（简单逻辑：连接数瞬时暴增或大量未知 IP）"""
        alerts = []
        if psutil:
            conns = psutil.net_connections()
            established = [c for c in conns if c.status == 'ESTABLISHED']
            if len(established) > 200: # 阈值可根据需要调整
                alerts.append(f"检测到大量活跃连接 ({len(established)})，可能存在扫描或 DDoS 攻击。")

            # 检测本地监听端口是否被异常篡改（此处为示例，可扩展核心端口白名单）
        return alerts

    def monitor_once(self):
        """执行单次全量检测"""
        print(f"\n[*] 正在执行网络环境安全检测...")
        report = []

        # 1. 延迟检测
        for host in self.target_hosts:
            res = self.ping_host(host)
            status_icon = "√" if res["status"] == "OK" else "×"
            latency_str = f"{res['latency']}ms" if res["latency"] != -1 else "超时"
            print(f"    - {host:<15}: {status_icon} {latency_str}")

            if res["latency"] == -1:
                report.append(f"严重：无法访问 {host}，可能存在断网或网络干扰。")
            elif res["latency"] > 200:
                report.append(f"警告：至 {host} 的延迟过高 ({res['latency']}ms)，网络环境变慢。")

        # 2. 安全扫描
        security_alerts = self.check_suspicious_connections()
        for alert in security_alerts:
            print(f"    [!] {alert}")
            report.append(alert)

        # 3. 综合判断
        if not report:
            print("[√] 网络环境安全且流畅。")
        else:
            print("\n[!] 发现异常状况：")
            for r in report:
                print(f"    - {r}")

        self.last_alerts = report
        return report

    def start_background_monitoring(self, interval=60):
        """启动后台持续监控"""
        self.monitoring = True
        def loop():
            while self.monitoring:
                self.monitor_once()
                time.sleep(interval)

        t = threading.Thread(target=loop, daemon=True)
        t.start()
        print(f"[*] 后台网络监控已启动，每 {interval}s 检测一次。")

def run():
    """Package 入口点"""
    monitor = NetworkSecurityMonitor()
    monitor.monitor_once()

if __name__ == "__main__":
    run()
