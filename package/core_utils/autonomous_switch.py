"""
Butler Autonomous Switchboard (布特勒自动交换机)
无UI后台运行，通过自动排序和管理进程防止系统混乱。
"""

import os
import sys
import time
import threading
import subprocess
import psutil
from pathlib import Path
from package.log_manager import LogManager

# 使用 Butler 统一的日志管理器
logger = LogManager.get_logger("autonomous_switch")

class AutonomousSwitch:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AutonomousSwitch, cls).__new__(cls)
            return cls._instance

    def __init__(self, interval=5, exclusive_mode=True):
        if hasattr(self, '_initialized'): return
        self.interval = interval
        self.exclusive_mode = exclusive_mode
        self.running = False
        self._initialized = True

        # 延迟导入以避免循环依赖
        from butler.resource_manager import ResourceManager
        self.res_mgr = ResourceManager()

    def start(self):
        if self.running:
            logger.info("自动交换机已在运行中。")
            return

        # 检查是否已有其他进程在运行此脚本
        if self._is_already_running():
            logger.warning("检测到另一个自动交换机进程已在运行，当前实例将退出。")
            return

        self.running = True
        logger.info("Butler 自动交换机已启动 (后台模式)")
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _is_already_running(self):
        """检查系统中是否已有相同功能的进程"""
        count = 0
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and "autonomous_switch.py" in " ".join(cmdline):
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return count > 1

    def stop(self):
        self.running = False
        logger.info("Butler 自动交换机已停止")

    def _get_butler_processes(self):
        """发现所有 Butler 相关的进程"""
        butler_procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'create_time']):
            try:
                cmdline = proc.info['cmdline']
                if not cmdline: continue

                cmd_str = " ".join(cmdline)
                # 识别 Butler 包或程序 (排除当前主程序和本交换机)
                if ("package." in cmd_str or "programs/" in cmd_str) and "autonomous_switch" not in cmd_str:
                    butler_procs.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmd': cmd_str,
                        'cpu': proc.info['cpu_percent'],
                        'mem': proc.info['memory_info'].rss / (1024 * 1024), # MB
                        'ctime': proc.info['create_time']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return butler_procs

    def _run_loop(self):
        while self.running:
            try:
                procs = self._get_butler_processes()

                # 1. 系统资源检查
                cpu_usage = self.res_mgr.get_cpu_usage()
                mem_usage = self.res_mgr.get_memory_usage()

                if procs:
                    # 2. 自动排序 (按内存占用从高到低排序，防止内存溢出)
                    procs.sort(key=lambda x: x['mem'], reverse=True)

                    # 3. 混乱预防逻辑

                    # A. 独占模式：如果运行了多个主要程序，只保留最新的一个
                    if self.exclusive_mode and len(procs) > 1:
                        procs_by_time = sorted(procs, key=lambda x: x['ctime'], reverse=True)
                        latest = procs_by_time[0]
                        to_kill = procs_by_time[1:]

                        logger.warning(f"检测到程序冲突。保留最新: {latest['pid']}，清理其余 {len(to_kill)} 个。")
                        for p in to_kill:
                            self._kill_process(p['pid'], f"程序冲突自动清理")
                        procs = [latest]

                    # B. 资源过载保护
                    if cpu_usage > 90 or mem_usage > 90:
                        logger.error(f"资源过载 (CPU: {cpu_usage}%, MEM: {mem_usage}%)。执行紧急清理。")
                        if procs:
                            target = procs[0]
                            self._kill_process(target['pid'], f"资源过载自动熔断")

            except Exception as e:
                logger.error(f"交换机运行异常: {e}")

            time.sleep(self.interval)

    def _kill_process(self, pid, reason):
        try:
            p = psutil.Process(pid)
            for child in p.children(recursive=True):
                child.kill()
            p.kill()
            logger.info(f"已自动关闭进程 {pid}。原因: {reason}")
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            logger.error(f"无法关闭进程 {pid}: {e}")

def run():
    """Butler 包的统一入口"""
    switch = AutonomousSwitch(interval=3)

    if switch._is_already_running():
        logger.warning("检测到另一个自动交换机进程已在运行，当前实例将退出。")
        return

    # 直接运行循环，不再多开一层线程（除非是在 Butler 主进程中调用）
    if not switch.running:
        switch.running = True
        logger.info("Butler 自动交换机已启动 (阻塞模式)")
        try:
            switch._run_loop()
        except KeyboardInterrupt:
            switch.stop()

if __name__ == "__main__":
    run()
