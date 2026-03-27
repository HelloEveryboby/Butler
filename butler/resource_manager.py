import psutil
from enum import Enum
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class PerformanceMode(Enum):
    NORMAL = "NORMAL"
    ECO = "ECO"

class ResourceManager:
    def __init__(self):
        self.mode = PerformanceMode.NORMAL

    def set_mode(self, mode: PerformanceMode):
        self.mode = mode
        logger.info(f"性能模式设置为: {self.mode.value}")

    def get_mode(self) -> PerformanceMode:
        return self.mode

    def get_cpu_usage(self) -> float:
        return psutil.cpu_percent(interval=1)

    def get_memory_usage(self) -> float:
        return psutil.virtual_memory().percent

if __name__ == '__main__':
    # 示例用法
    manager = ResourceManager()
    logger.info(f"当前模式: {manager.get_mode().value}")
    logger.info(f"CPU 使用率: {manager.get_cpu_usage()}%")
    logger.info(f"内存使用率: {manager.get_memory_usage()}%")

    manager.set_mode(PerformanceMode.ECO)
    logger.info(f"当前模式: {manager.get_mode().value}")
