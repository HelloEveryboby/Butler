"""
Butler 自动交换机 (Autonomous Switchboard V2.0 - 完整版)
------------------------------------------------------
功能说明：
1. 后台治理：作为 Butler 的后台守护进程，自动发现并管理所有 Butler 相关的子进程。
2. 负载均衡：实时监控 CPU 和内存占用。当系统资源紧张时，通过“自动熔断”机制清理低优先级或高耗能进程。
3. 冲突治理：在“独占模式”下，确保同一功能的模块不会重复运行，自动保留最新实例并清理旧实例。
4. 跨语言支持：能够识别并治理 Butler Hybrid-Link (BHL) 产生的 C++、Go、Rust 外部进程。
5. 动态反馈：支持根据负载动态调整检查频率，实现节能与高性能的平衡。

使用方法：
- Butler 系统自动启动
- 手动启动: `python -m package.core_utils.autonomous_switch`
"""

import os
import sys
import time
import threading
import psutil
from collections import defaultdict
from pathlib import Path
from package.core_utils.log_manager import LogManager
from package.core_utils.health_monitor import HealthMonitor

# 获取日志记录器
logger = LogManager.get_logger("autonomous_switch")

class AutonomousSwitch:
    """
    自动交换机：Butler 系统的资源协调与进程治理中心。
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AutonomousSwitch, cls).__new__(cls)
            return cls._instance

    def __init__(self, base_interval=5, exclusive_mode=True):
        """
        初始化交换机。

        Args:
            base_interval: 基础检查周期（秒）。
            exclusive_mode: 是否开启独占模式。
        """
        if hasattr(self, '_initialized'): return
        self.base_interval = base_interval
        self.current_interval = base_interval
        self.exclusive_mode = exclusive_mode
        self.running = False
        self._initialized = True
        self.health_monitor = HealthMonitor()

        # 尝试加载资源管理器
        try:
            from butler.resource_manager import ResourceManager
            self.res_mgr = ResourceManager()
        except ImportError:
            self.res_mgr = None

    def start(self, background=True):
        """
        启动交换机。
        """
        if self.running:
            return

        if self._is_already_running():
            logger.warning("另一个自动交换机实例正在运行，当前进程将退出。")
            return

        self.running = True
        logger.info(f"Butler 自动交换机已启动 (间隔: {self.base_interval}s, 独占模式: {self.exclusive_mode})")

        if background:
            self.thread = threading.Thread(target=self._run_loop, daemon=True)
            self.thread.start()
        else:
            self._run_loop()

    def _is_already_running(self):
        """通过进程名和命令行检查是否重复运行"""
        count = 0
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                if proc.info['pid'] == current_pid: continue
                cmdline = proc.info['cmdline']
                if cmdline and "autonomous_switch.py" in " ".join(cmdline):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return count > 0

    def stop(self):
        self.running = False
        logger.info("Butler 自动交换机正在停止...")

    def _discover_processes(self):
        """
        深入系统进程树，识别所有与 Butler 相关的 Python 和 BHL 二进制进程。
        """
        butler_procs = []
        # BHL 二进制程序关键字
        bhl_targets = ["hybrid_compute", "hybrid_net", "hybrid_crypto"]

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'create_time']):
            try:
                cmdline = proc.info['cmdline']
                if not cmdline: continue
                cmd_str = " ".join(cmdline)

                # 判定规则：
                # 1. 包含 "package." 的 Python 进程
                # 2. programs 目录下的 BHL 进程
                is_package = "package." in cmd_str
                is_bhl = any(target in cmd_str for target in bhl_targets)

                if (is_package or is_bhl) and "autonomous_switch" not in cmd_str:
                    butler_procs.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmd': cmd_str,
                        'cpu': proc.info['cpu_percent'],
                        'mem': proc.info['memory_info'].rss / (1024 * 1024),
                        'ctime': proc.info['create_time'],
                        'is_bhl': is_bhl
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return butler_procs

    def _run_loop(self):
        """主治理循环"""
        while self.running:
            try:
                procs = self._discover_processes()

                # 获取系统负载
                cpu_load = psutil.cpu_percent()
                mem_load = psutil.virtual_memory().percent

                # 动态频率调整：负载高时增加检查频率，负载低时减少
                if cpu_load > 70 or mem_load > 70:
                    self.current_interval = max(1, self.base_interval // 2)
                    # 资源紧张时，自动执行一次自愈扫描
                    self.health_monitor.run_self_healing()
                else:
                    self.current_interval = self.base_interval

                if procs:
                    # 1. 自动排序：按内存占用降序
                    procs.sort(key=lambda x: x['mem'], reverse=True)

                    # 2. 独占模式治理
                    if self.exclusive_mode:
                        cmd_groups = defaultdict(list)
                        for p in procs:
                            cmd_groups[p['cmd']].append(p)

                        for cmd, group in cmd_groups.items():
                            if len(group) > 1:
                                # 按创建时间排序，保留最新的 PID
                                group.sort(key=lambda x: x['ctime'], reverse=True)
                                survivor = group[0]
                                victims = group[1:]
                                logger.info(f"独占模式激活：保留最新进程 {survivor['pid']} ({cmd})，清理 {len(victims)} 个重复实例。")
                                for v in victims:
                                    self._terminate_process(v['pid'], "重复实例清理")

                    # 3. 资源熔断保护
                    if cpu_load > 90 or mem_load > 90:
                        logger.error(f"⚠️ 系统资源危急! CPU: {cpu_load}%, MEM: {mem_load}%。启动自动熔断。")
                        # 杀掉内存占用最高的一个进程（通常是失控的脚本）
                        target = procs[0]
                        self._terminate_process(target['pid'], "资源过载自动熔断")

            except Exception as e:
                logger.error(f"交换机循环执行异常: {e}")

            time.sleep(self.current_interval)

    def _terminate_process(self, pid, reason):
        """优雅终止进程及其所有子进程"""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                child.terminate()
            parent.terminate()

            # 等待 2 秒，如果不退出则强制杀掉
            gone, alive = psutil.wait_procs(children + [parent], timeout=2)
            for p in alive:
                p.kill()

            logger.info(f"已成功关闭进程 {pid}。原因: {reason}")
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            logger.error(f"关闭进程 {pid} 失败: {e}")

def run():
    """入口点"""
    switch = AutonomousSwitch(base_interval=3)
    # 以阻塞模式运行，适合独立进程启动
    switch.start(background=False)

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n👋 交换机已安全退出。")
