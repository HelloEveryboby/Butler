"""系统信息监控模块。

基于 psutil 提供:CPU / 内存 / 磁盘 / 网络 / 进程 Top 列表 / 启动信息。
支持单次快照与持续刷新两种模式。
"""

from __future__ import annotations

import os
import platform
import time
from dataclasses import dataclass, field
from typing import List, Optional

import psutil

from .utils import format_bytes


@dataclass
class CpuInfo:
    percent: float
    per_core: List[float] = field(default_factory=list)
    count: int = 0
    freq_mhz: float = 0.0
    load_avg: tuple = ()


@dataclass
class MemInfo:
    total: int
    used: int
    percent: float
    swap_total: int = 0
    swap_used: int = 0
    swap_percent: float = 0.0


@dataclass
class DiskInfo:
    device: str
    mountpoint: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float


@dataclass
class NetInfo:
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int


@dataclass
class ProcessInfo:
    pid: int
    name: str
    username: str
    cpu_percent: float
    memory_percent: float
    memory_bytes: int
    status: str
    command: str


class SystemMonitor:
    """系统监控:快照采集与持续刷新。"""

    def __init__(self) -> None:
        # 首次调用 cpu_percent 会返回 0,提前预热
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(percpu=True, interval=None)

    # ---------------- 基础信息 ----------------

    def system_info(self) -> dict:
        """返回系统静态信息。"""
        vm = psutil.virtual_memory()
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor() or platform.machine(),
            "hostname": platform.node(),
            "python": platform.python_version(),
            "boot_time": psutil.boot_time(),
            "uptime_sec": time.time() - psutil.boot_time(),
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_count_physical": psutil.cpu_count(logical=False),
            "memory_total": vm.total,
        }

    # ---------------- CPU ----------------

    def cpu(self, interval: float = 0.0) -> CpuInfo:
        per_core = psutil.cpu_percent(percpu=True, interval=interval)
        freq = psutil.cpu_freq()
        load = ()
        if hasattr(os, "getloadavg"):
            try:
                load = os.getloadavg()
            except OSError:
                load = ()
        return CpuInfo(
            percent=sum(per_core) / len(per_core) if per_core else 0.0,
            per_core=per_core,
            count=len(per_core),
            freq_mhz=freq.current if freq else 0.0,
            load_avg=load,
        )

    # ---------------- 内存 ----------------

    def memory(self) -> MemInfo:
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        return MemInfo(
            total=vm.total,
            used=vm.used,
            percent=vm.percent,
            swap_total=sm.total,
            swap_used=sm.used,
            swap_percent=sm.percent,
        )

    # ---------------- 磁盘 ----------------

    def disks(self) -> List[DiskInfo]:
        result: List[DiskInfo] = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
            except (OSError, PermissionError):
                continue
            result.append(DiskInfo(
                device=part.device,
                mountpoint=part.mountpoint,
                fstype=part.fstype,
                total=usage.total,
                used=usage.used,
                free=usage.free,
                percent=usage.percent,
            ))
        return result

    def disk_io(self) -> dict:
        counters = psutil.disk_io_counters()
        if not counters:
            return {}
        return {
            "read_bytes": counters.read_bytes,
            "write_bytes": counters.write_bytes,
            "read_count": counters.read_count,
            "write_count": counters.write_count,
        }

    # ---------------- 网络 ----------------

    def network(self) -> NetInfo:
        c = psutil.net_io_counters()
        return NetInfo(
            bytes_sent=c.bytes_sent,
            bytes_recv=c.bytes_recv,
            packets_sent=c.packets_sent,
            packets_recv=c.packets_recv,
        )

    # ---------------- 进程 ----------------

    def top_processes(self, limit: int = 15, sort_by: str = "cpu") -> List[ProcessInfo]:
        """返回占用最高的进程,sort_by: cpu / memory。"""
        procs: List[ProcessInfo] = []
        for p in psutil.process_iter(["pid", "name", "username", "cpu_percent",
                                      "memory_percent", "memory_info", "status", "cmdline"]):
            try:
                info = p.info
                mem = info.get("memory_info")
                procs.append(ProcessInfo(
                    pid=info["pid"],
                    name=info.get("name", "") or "",
                    username=info.get("username", "") or "",
                    cpu_percent=info.get("cpu_percent", 0.0) or 0.0,
                    memory_percent=info.get("memory_percent", 0.0) or 0.0,
                    memory_bytes=mem.rss if mem else 0,
                    status=info.get("status", "") or "",
                    command=" ".join(info.get("cmdline") or [])[:120],
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
        procs.sort(key=lambda x: getattr(x, key), reverse=True)
        return procs[:limit]

    # ---------------- 持续刷新 ----------------

    def watch(self, callback, interval: float = 1.0, count: Optional[int] = None) -> None:
        """持续调用 callback(monitor) 直到 count 次或被中断。

        callback 返回 False 可提前终止。
        """
        i = 0
        try:
            while True:
                if callback(self) is False:
                    break
                i += 1
                if count is not None and i >= count:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            pass


def uptime_text(seconds: float) -> str:
    """把秒数格式化为可读的运行时长。"""
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"
