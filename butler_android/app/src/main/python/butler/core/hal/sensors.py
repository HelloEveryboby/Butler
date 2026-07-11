import psutil
import logging
from typing import Dict, Any
from butler.core.hal.base import BaseSensor
from butler.core.battery_manager import battery_manager

logger = logging.getLogger("SystemResourceSensor")

class SystemResourceSensor(BaseSensor):
    """
    Sensor for gathering real-time CPU, RAM, Disk, and Battery statistics.
    Inherits from BaseSensor.
    """
    def __init__(self):
        super().__init__("system_resource")

    def read(self) -> Dict[str, Any]:
        """
        Gathers system resource stats.
        """
        stats = {
            "cpu": {
                "percent": 0.0,
                "count": 1
            },
            "memory": {
                "percent": 0.0,
                "total_gb": 0.0,
                "used_gb": 0.0
            },
            "disk": {
                "percent": 0.0,
                "total_gb": 0.0,
                "used_gb": 0.0
            },
            "battery": {
                "percent": 100,
                "plugged": True
            }
        }

        # 1. CPU Reading
        try:
            stats["cpu"]["percent"] = psutil.cpu_percent(interval=None)
            stats["cpu"]["count"] = psutil.cpu_count(logical=True) or 1
        except Exception as e:
            logger.error(f"Failed to read CPU stats: {e}")

        # 2. Memory Reading
        try:
            mem = psutil.virtual_memory()
            stats["memory"]["percent"] = mem.percent
            stats["memory"]["total_gb"] = round(mem.total / (1024 ** 3), 2)
            stats["memory"]["used_gb"] = round(mem.used / (1024 ** 3), 2)
        except Exception as e:
            logger.error(f"Failed to read memory stats: {e}")

        # 3. Disk Reading
        try:
            disk = psutil.disk_usage('/')
            stats["disk"]["percent"] = disk.percent
            stats["disk"]["total_gb"] = round(disk.total / (1024 ** 3), 2)
            stats["disk"]["used_gb"] = round(disk.used / (1024 ** 3), 2)
        except Exception as e:
            logger.error(f"Failed to read disk stats: {e}")

        # 4. Battery Reading (Integrated with battery_manager)
        try:
            percent, plugged = battery_manager.get_status()
            stats["battery"]["percent"] = percent
            stats["battery"]["plugged"] = plugged
        except Exception as e:
            logger.error(f"Failed to read battery stats: {e}")

        return stats
