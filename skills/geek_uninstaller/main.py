"""Geek Uninstaller — Butler Skill 入口。

遵循 Butler 技能约定:暴露 ``handle_request(action, **kwargs)`` 入口,
返回纯 JSON 可序列化字典,供前端 pywebview 桥接或 CLI 调用。

后端引擎复用 ``core`` 包(utils / uninstaller / cleaner / monitor)。
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

# 确保能导入同级 core 包
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

from core.cleaner import JunkCleaner
from core.monitor import SystemMonitor
from core.uninstaller import Uninstaller
from core.utils import format_bytes, format_size_short

logger = logging.getLogger("GeekUninstaller")

# 单例引擎,避免每次调用重新初始化(psutil 预热等)
_uninstaller: Uninstaller | None = None
_cleaner: JunkCleaner | None = None
_monitor: SystemMonitor | None = None


def _get_uninstaller() -> Uninstaller:
    global _uninstaller
    if _uninstaller is None:
        _uninstaller = Uninstaller()
    return _uninstaller


def _get_cleaner() -> JunkCleaner:
    global _cleaner
    if _cleaner is None:
        _cleaner = JunkCleaner()
    return _cleaner


def _get_monitor() -> SystemMonitor:
    global _monitor
    if _monitor is None:
        _monitor = SystemMonitor()
    return _monitor


# ---------------- 软件盘点 ----------------

def list_software(kwargs: dict) -> dict:
    """列出已安装软件。"""
    try:
        sw_list = _get_uninstaller().list_software()
        return {
            "status": "ok",
            "count": len(sw_list),
            "items": [_software_to_dict(sw) for sw in sw_list],
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("list_software failed")
        return {"status": "error", "message": str(e)}


def _software_to_dict(sw) -> dict:
    return {
        "name": sw.name,
        "version": sw.version or "",
        "publisher": sw.publisher or "",
        "install_location": sw.install_location or "",
        "uninstall_string": sw.uninstall_string or "",
        "size": sw.size,
        "size_text": sw.size_text,
        "source": sw.source or "",
        "package": sw.package or "",
    }


# ---------------- 残留扫描 ----------------

def scan_leftovers(kwargs: dict) -> dict:
    """扫描指定软件名的残留文件。"""
    name = kwargs.get("name", "").strip()
    if not name:
        return {"status": "error", "message": "缺少参数 name"}
    try:
        leftovers = _get_uninstaller().scan_leftovers(name)
        total = sum(lf.size for lf in leftovers)
        return {
            "status": "ok",
            "name": name,
            "count": len(leftovers),
            "total_size": total,
            "total_size_text": format_bytes(total),
            "items": [
                {"kind": lf.kind, "path": lf.path, "size": lf.size,
                 "size_text": lf.size_text}
                for lf in leftovers
            ],
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("scan_leftovers failed")
        return {"status": "error", "message": str(e)}


# ---------------- 深度卸载 ----------------

def uninstall(kwargs: dict) -> dict:
    """深度卸载指定软件:调用官方卸载程序 → 扫描残留 → 清理残留。

    dry_run=True 时仅模拟,不实际删除。
    """
    name = kwargs.get("name", "").strip()
    if not name:
        return {"status": "error", "message": "缺少参数 name"}
    dry_run = bool(kwargs.get("dry_run", True))
    try:
        un = _get_uninstaller()
        sw = un.find(name)
        if not sw:
            return {"status": "not_found",
                    "message": f"未找到匹配的软件: {name}"}
        result = un.uninstall(sw, dry_run=dry_run)
        return {
            "status": "ok",
            "dry_run": dry_run,
            "name": sw.name,
            "version": sw.version or "",
            "source": sw.source or "",
            "uninstall_string": sw.uninstall_string or sw.package or "",
            "uninstalled": result.uninstalled,
            "leftover_count": len(result.leftovers),
            "leftover_total_size": sum(lf.size for lf in result.leftovers),
            "cleaned": result.cleaned,
            "freed_bytes": result.freed_bytes,
            "freed_text": format_bytes(result.freed_bytes),
            "message": result.message,
            "leftovers": [
                {"kind": lf.kind, "path": lf.path, "size_text": lf.size_text}
                for lf in result.leftovers
            ],
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("uninstall failed")
        return {"status": "error", "message": str(e)}


# ---------------- 垃圾清理 ----------------

def scan_junk(kwargs: dict) -> dict:
    """扫描系统垃圾文件。categories 可选逗号分隔字符串或列表。"""
    try:
        cats = kwargs.get("categories")
        if isinstance(cats, str):
            cats = [c.strip() for c in cats.split(",") if c.strip()]
        items = _get_cleaner().scan(cats)
        total = sum(it.size for it in items)
        return {
            "status": "ok",
            "count": len(items),
            "total_size": total,
            "total_size_text": format_bytes(total),
            "items": [
                {"category": it.category, "description": it.description,
                 "path": it.path, "size": it.size, "size_text": it.size_text}
                for it in items
            ],
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("scan_junk failed")
        return {"status": "error", "message": str(e)}


def clean_junk(kwargs: dict) -> dict:
    """清理垃圾文件。dry_run=True 时仅模拟。"""
    dry_run = bool(kwargs.get("dry_run", True))
    try:
        cats = kwargs.get("categories")
        if isinstance(cats, str):
            cats = [c.strip() for c in cats.split(",") if c.strip()]
        cleaner = _get_cleaner()
        items = cleaner.scan(cats)
        report = cleaner.clean(items, dry_run=dry_run)
        return {
            "status": "ok",
            "dry_run": dry_run,
            "scanned": report.scanned,
            "cleaned": report.cleaned,
            "skipped": report.skipped,
            "freed_bytes": report.freed_bytes,
            "freed_text": format_bytes(report.freed_bytes),
            "total_size_text": format_bytes(report.total_size),
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("clean_junk failed")
        return {"status": "error", "message": str(e)}


# ---------------- 系统监控 ----------------

def system_info(kwargs: dict) -> dict:
    """返回系统静态信息 + 当前资源快照。"""
    try:
        mon = _get_monitor()
        info = mon.system_info()
        cpu = mon.cpu(interval=0.0)
        mem = mon.memory()
        disks = mon.disks()
        net = mon.network()
        from core.monitor import uptime_text
        return {
            "status": "ok",
            "system": info,
            "uptime_text": uptime_text(info["uptime_sec"]),
            "cpu": {
                "percent": round(cpu.percent, 1),
                "per_core": [round(c, 1) for c in cpu.per_core],
                "count": cpu.count,
                "freq_mhz": round(cpu.freq_mhz, 0),
                "load_avg": list(cpu.load_avg),
            },
            "memory": {
                "total": mem.total, "used": mem.used, "percent": round(mem.percent, 1),
                "total_text": format_bytes(mem.total),
                "used_text": format_bytes(mem.used),
                "swap_total": mem.swap_total, "swap_used": mem.swap_used,
                "swap_percent": round(mem.swap_percent, 1),
            },
            "disks": [
                {"device": d.device, "mountpoint": d.mountpoint, "fstype": d.fstype,
                 "total": d.total, "used": d.used, "free": d.free,
                 "percent": round(d.percent, 1),
                 "total_text": format_bytes(d.total), "used_text": format_bytes(d.used)}
                for d in disks
            ],
            "network": {
                "bytes_sent": net.bytes_sent, "bytes_recv": net.bytes_recv,
                "bytes_sent_text": format_bytes(net.bytes_sent),
                "bytes_recv_text": format_bytes(net.bytes_recv),
                "packets_sent": net.packets_sent, "packets_recv": net.packets_recv,
            },
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("system_info failed")
        return {"status": "error", "message": str(e)}


def top_processes(kwargs: dict) -> dict:
    """返回占用最高的进程。sort_by: cpu / memory。"""
    try:
        limit = int(kwargs.get("limit", 15))
        sort_by = kwargs.get("sort_by", "cpu")
        if sort_by not in ("cpu", "memory"):
            sort_by = "cpu"
        procs = _get_monitor().top_processes(limit=limit, sort_by=sort_by)
        return {
            "status": "ok",
            "sort_by": sort_by,
            "count": len(procs),
            "items": [
                {"pid": p.pid, "name": p.name, "username": p.username,
                 "cpu_percent": round(p.cpu_percent, 1),
                 "memory_percent": round(p.memory_percent, 1),
                 "memory_text": format_size_short(p.memory_bytes),
                 "status": p.status, "command": p.command}
                for p in procs
            ],
        }
    except Exception as e:  # noqa: BLE001
        logger.exception("top_processes failed")
        return {"status": "error", "message": str(e)}


# ---------------- Butler 入口 ----------------

# action 分发表
_ACTIONS = {
    "list_software": list_software,
    "scan_leftovers": scan_leftovers,
    "uninstall": uninstall,
    "scan_junk": scan_junk,
    "clean_junk": clean_junk,
    "system_info": system_info,
    "top_processes": top_processes,
}


def handle_request(action: str, **kwargs) -> dict:
    """Butler 技能统一入口。

    :param action: 动作名,见 ``_ACTIONS``
    :param kwargs: 动作参数
    :return: JSON 可序列化字典
    """
    handler = _ACTIONS.get(action)
    if handler is None:
        return {"status": "error", "message": f"Unknown action: {action}",
                "available": list(_ACTIONS.keys())}
    logger.info("GeekUninstaller action=%s kwargs=%s", action, kwargs)
    return handler(kwargs or {})


# ---------------- CLI 直跑(便于调试,与 sys_cleaner 一致) ----------------

def _cli() -> int:
    import json
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Geek Uninstaller — Butler Skill")
        print("用法: python main.py <action> [key=value ...]")
        print(f"可用 action: {', '.join(_ACTIONS.keys())}")
        print("示例: python main.py list_software")
        print("      python main.py scan_leftovers name=firefox")
        print("      python main.py uninstall name=firefox dry_run=true")
        print("      python main.py scan_junk")
        print("      python main.py system_info")
        return 0
    action = sys.argv[1]
    kwargs: dict[str, Any] = {}
    for arg in sys.argv[2:]:
        if "=" in arg:
            k, v = arg.split("=", 1)
            # 简单类型转换
            if v.lower() in ("true", "false"):
                kwargs[k] = v.lower() == "true"
            elif v.isdigit():
                kwargs[k] = int(v)
            else:
                kwargs[k] = v
    result = handle_request(action, **kwargs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") != "error" else 1


if __name__ == "__main__":
    sys.exit(_cli())
