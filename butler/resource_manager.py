import psutil
from enum import Enum

class PerformanceMode(Enum):
    NORMAL = "NORMAL"
    ECO = "ECO"

class ResourceManager:
    def __init__(self):
        self.mode = PerformanceMode.NORMAL

    def set_mode(self, mode: PerformanceMode):
        self.mode = mode
        print(f"性能模式设置为: {self.mode.value}")

    def get_mode(self) -> PerformanceMode:
        return self.mode

    def get_cpu_usage(self) -> float:
        return psutil.cpu_percent(interval=1)

    def get_memory_usage(self) -> float:
        return psutil.virtual_memory().percent

if __name__ == '__main__':
    # 示例用法
    manager = ResourceManager()
    print(f"当前模式: {manager.get_mode().value}")
    print(f"CPU 使用率: {manager.get_cpu_usage()}%")
    print(f"内存使用率: {manager.get_memory_usage()}%")

    manager.set_mode(PerformanceMode.ECO)
    print(f"当前模式: {manager.get_mode().value}")
