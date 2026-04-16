import psutil
from package.core_utils.log_manager import LogManager
from butler.resource_manager import PerformanceMode

logger = LogManager.get_logger("battery_manager")

class BatteryManager:
    """
    Butler 电池管理器 (Battery Manager)
    监控系统电池状态，为低功耗运行提供决策支持。
    """
    def __init__(self, low_battery_threshold=20):
        self.low_battery_threshold = low_battery_threshold
        # 在运行时由 app 注入 resource_manager
        self.res_mgr = None

    def get_status(self):
        """
        获取当前电池状态。
        返回: (percent, power_plugged)
        """
        try:
            battery = psutil.sensors_battery()
            if battery:
                return battery.percent, battery.power_plugged
        except Exception as e:
            logger.error(f"无法获取电池状态: {e}")

        return 100, True

    def should_throttle(self):
        """
        是否应该节流。
        """
        # 如果处于全性能模式，除非电量极低 ( < 5% )，否则不节流
        if self.res_mgr and self.res_mgr.get_mode() == PerformanceMode.HIGH_PERFORMANCE:
            percent, plugged = self.get_status()
            return not plugged and percent <= 5

        # 默认模式 (ECO) 或 NORMAL 下的节流逻辑
        percent, plugged = self.get_status()
        if not plugged and percent <= self.low_battery_threshold:
            return True

        return False

    def can_run_background_task(self):
        """
        判断是否允许运行耗电的后台任务（如做梦）。
        在 ECO 模式下，只有在充电时才允许运行这些任务。
        """
        percent, plugged = self.get_status()

        # 高性能模式：电量 > 10% 即可运行
        if self.res_mgr and self.res_mgr.get_mode() == PerformanceMode.HIGH_PERFORMANCE:
            return plugged or percent > 10

        # ECO 模式：必须插电或电量 > 80% 且不是深夜
        if self.res_mgr and self.res_mgr.get_mode() == PerformanceMode.ECO:
            if plugged: return True
            import time
            hour = time.localtime().tm_hour
            # 只有在非深度休眠时间 (8:00 - 23:00) 且高电量时才运行
            return percent > 80 and (8 <= hour <= 23)

        # NORMAL 模式
        return plugged or percent > 30

    def get_sleep_multiplier(self):
        """
        获取睡眠时间乘数。
        """
        mode = self.res_mgr.get_mode() if self.res_mgr else PerformanceMode.ECO

        if mode == PerformanceMode.HIGH_PERFORMANCE:
            return 0.5  # 高性能模式，加快响应

        percent, plugged = self.get_status()

        # ECO 模式默认增加间隔
        base_multiplier = 2.0 if mode == PerformanceMode.ECO else 1.0

        if plugged:
            return base_multiplier

        if percent <= self.low_battery_threshold:
            return base_multiplier * 5.0
        elif percent <= 50:
            return base_multiplier * 2.0

        return base_multiplier

battery_manager = BatteryManager()
