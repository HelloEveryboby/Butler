import logging
from typing import Dict, Any

logger = logging.getLogger("system_monitor")
_context = None

def initialize_core(context) -> None:
    """
    Hook called by SkillManager upon load.
    Directly injects the privileged CorePluginContext.
    """
    global _context
    _context = context
    logger.info("system_monitor core plugin successfully initialized with privileges.")

    # Auto-run an initial sensor read to populate the blackboard
    try:
        stats = _context.system_sensor.read()
        _context.blackboard.write("system.stats", stats)
    except Exception as e:
        logger.error(f"Initial stats load failed: {e}")


def format_progress_bar(percent: float, width: int = 15) -> str:
    """Helper to format a beautiful ASCII progress bar."""
    filled_length = int(round(width * percent / 100))
    bar = "█" * filled_length + "░" * (width - filled_length)
    return f"[{bar}] {percent}%"


def handle_request(action: str, **kwargs) -> Any:
    """
    Handles request for system monitoring.
    Supported actions:
    - 'run' / 'status': Gathers and prints stats.
    - 'read_raw': Returns raw stats dictionary.
    """
    global _context
    if _context is None:
        return "Error: Core plugin context is not initialized."

    # 1. Read real-time telemetry from HAL SystemResourceSensor
    try:
        stats = _context.system_sensor.read()
    except Exception as e:
        logger.error(f"HAL sensor read failed: {e}")
        return f"Error gathering stats: {e}"

    # 2. Write to the Blackboard for system-wide awareness
    _context.blackboard.write("system.stats", stats)

    if action == "read_raw":
        return stats

    # 3. Format visual glassmorphic metrics card for rendering
    cpu = stats["cpu"]
    mem = stats["memory"]
    disk = stats["disk"]
    batt = stats["battery"]

    plugged_str = "🔌 已插电" if batt["plugged"] else "🔋 电池供电"

    card = (
        f"╔═════════════════════════════════════════════╗\n"
        f"║  🖥️  Butler 系统监控卡片 (Glassmorphism Mode)   ║\n"
        f"╠═════════════════════════════════════════════╣\n"
        f"║  ⚙️  CPU 负载:  {format_progress_bar(cpu['percent']):<31} ║\n"
        f"║  ⚡ 核心数量:  {cpu['count']:<31} ║\n"
        f"║  🧠 内存占用:  {format_progress_bar(mem['percent'])}  ({mem['used_gb']}G / {mem['total_gb']}G) ║\n"
        f"║  💽 磁盘空间:  {format_progress_bar(disk['percent'])}  ({disk['used_gb']}G / {disk['total_gb']}G) ║\n"
        f"║  🔋 电池电量:  {format_progress_bar(batt['percent']):<18} ({plugged_str}) ║\n"
        f"╚═════════════════════════════════════════════╝"
    )

    # Optionally push to event_bus if requested
    if kwargs.get("broadcast"):
        _context.event_bus.emit("ui_output", card, "ai_response", None)

    return card
