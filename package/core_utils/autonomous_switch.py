"""
Butler 自动交换机 (Autonomous Switchboard V2.0)
---------------------------------------------
功能：
1. 无 UI 后台运行，监控 Butler 系统的所有相关进程。
2. 自动排序进程优先级，根据内存和 CPU 占用情况防止系统负载过高。
3. 冲突管理：在独占模式下，确保同一功能程序只运行一个最新实例。
4. 混合系统管理：支持监控 Butler Hybrid-Link (BHL) 生成的外部程序进程。
"""

import os
import sys
import time
import threading
import subprocess
import psutil
from pathlib import Path
from package.core_utils.log_manager import LogManager

# 获取日志记录器
logger = LogManager.get_logger("autonomous_switch")

class AutonomousSwitch:
    """
    自动交换机类，负责 Butler 系统进程的治理与协调。
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AutonomousSwitch, cls).__new__(cls)
            return cls._instance

    def __init__(self, interval=5, exclusive_mode=True):
        """
        初始化交换机。

        Args:
            interval: 检查周期（秒）。
            exclusive_mode: 是否开启独占模式（即同类程序仅保留最新运行的一个）。
        """
        if hasattr(self, '_initialized'): return
        self.interval = interval
        self.exclusive_mode = exclusive_mode
        self.running = False
        self._initialized = True

        # 延迟导入资源管理器，避免启动循环依赖
        try:
            from butler.resource_manager import ResourceManager
            self.res_mgr = ResourceManager()
        except ImportError:
            self.res_mgr = None

    def start(self):
        """启动后台监控线程"""
        if self.running:
            logger.info("自动交换机已在运行中。")
            return

        if self._is_already_running():
            logger.warning("检测到另一个自动交换机进程已在运行，当前实例将退出。")
            return

        self.running = True
        logger.info("Butler 自动交换机已启动 (后台监控模式)")
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _is_already_running(self):
        """检查系统中是否已存在运行中的交换机进程"""
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
        """停止监控"""
        self.running = False
        logger.info("Butler 自动交换机已停止")

    def _get_butler_processes(self):
        """
        发现并识别所有 Butler 相关的进程。
        包括 Python 扩展包、插件以及 BHL 编译的外部二进制程序。
        """
        butler_procs = []
        # 扩展识别范围：包含 BHL 程序通常所在的目录
        bhl_keywords = ["programs/hybrid_compute", "programs/hybrid_net", "programs/hybrid_crypto"]

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'create_time']):
            try:
                cmdline = proc.info['cmdline']
                if not cmdline: continue

                cmd_str = " ".join(cmdline)

                # 识别逻辑：
                # 1. Python 包形式运行的程序
                # 2. 直接运行在 programs/ 目录下的 BHL 程序
                is_butler_package = "package." in cmd_str
                is_bhl_program = any(kw in cmd_str for kw in bhl_keywords)

                if (is_butler_package or is_bhl_program) and "autonomous_switch" not in cmd_str:
                    butler_procs.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cmd': cmd_str,
                        'cpu': proc.info['cpu_percent'],
                        'mem': proc.info['memory_info'].rss / (1024 * 1024), # 转换为 MB
                        'ctime': proc.info['create_time'],
                        'type': 'BHL' if is_bhl_program else 'Python'
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return butler_procs

    def _run_loop(self):
        """核心监控循环"""
        while self.running:
            try:
                procs = self._get_butler_processes()

                # 获取系统整体资源状态
                cpu_usage = self.res_mgr.get_cpu_usage() if self.res_mgr else psutil.cpu_percent()
                mem_usage = self.res_mgr.get_memory_usage() if self.res_mgr else psutil.virtual_memory().percent

                if procs:
                    # 1. 自动排序：按内存占用从高到低排序
                    procs.sort(key=lambda x: x['mem'], reverse=True)

                    # 2. 独占模式处理：如果多个进程运行同一个包，只保留最新的一个
                    if self.exclusive_mode:
                        # 按命令字符串分组
                        from collections import defaultdict
                        groups = defaultdict(list)
                        for p in procs:
                            groups[p['cmd']].append(p)

                        for cmd, group in groups.items():
                            if len(group) > 1:
                                # 按创建时间排序，保留最新的
                                group.sort(key=lambda x: x['ctime'], reverse=True)
                                to_kill = group[1:]
                                logger.warning(f"检测到同类程序冲突 ({cmd})。保留最新: {group[0]['pid']}，清理其余 {len(to_kill)} 个。")
                                for p in to_kill:
                                    self._kill_process(p['pid'], "同类程序独占模式清理")

                    # 3. 资源过载保护（熔断机制）
                    if cpu_usage > 90 or mem_usage > 90:
                        logger.error(f"系统资源过载 (CPU: {cpu_usage}%, MEM: {mem_usage}%)。执行紧急熔断清理。")
                        # 杀掉占用内存最高的一个 Butler 相关进程
                        target = procs[0]
                        self._kill_process(target['pid'], "资源过载自动熔断")

            except Exception as e:
                logger.error(f"交换机运行异常: {e}")

            time.sleep(self.interval)

    def _kill_process(self, pid, reason):
        """安全地终止进程及其所有子进程"""
        try:
            p = psutil.Process(pid)
            # 递归杀掉子进程
            children = p.children(recursive=True)
            for child in children:
                child.kill()
            p.kill()
            logger.info(f"已强制关闭进程 {pid}。原因: {reason}")
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            logger.error(f"无法关闭进程 {pid}: {e}")

def run():
    """
    Butler 扩展包统一入口。
    """
    # 默认以 3 秒为周期运行
    switch = AutonomousSwitch(interval=3)

    if switch._is_already_running():
        logger.warning("检测到另一个自动交换机进程已在运行，当前实例将退出。")
        return

    if not switch.running:
        switch.running = True
        logger.info("Butler 自动交换机已启动 (阻塞模式)")
        try:
            switch._run_loop()
        except KeyboardInterrupt:
            switch.stop()

if __name__ == "__main__":
    run()
