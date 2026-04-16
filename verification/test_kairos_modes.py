import sys
import os
import time
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from butler.core.battery_manager import battery_manager
from butler.resource_manager import ResourceManager, PerformanceMode

def test_performance_modes():
    print("--- Testing Performance Modes ---")
    res_mgr = ResourceManager()
    battery_manager.res_mgr = res_mgr

    # 1. Test ECO (Default)
    print(f"\nMode: {res_mgr.get_mode().value}")
    print(f"Should Throttle: {battery_manager.should_throttle()}")
    print(f"Sleep Multiplier: {battery_manager.get_sleep_multiplier()}")

    # 2. Test HIGH_PERFORMANCE
    res_mgr.set_mode(PerformanceMode.HIGH_PERFORMANCE)
    print(f"\nMode: {res_mgr.get_mode().value}")
    print(f"Should Throttle: {battery_manager.should_throttle()}")
    print(f"Sleep Multiplier: {battery_manager.get_sleep_multiplier()}")

    # 3. Test Battery Awareness in ECO
    res_mgr.set_mode(PerformanceMode.ECO)
    # Mock battery status
    import psutil
    original_battery = psutil.sensors_battery
    class MockBattery:
        def __init__(self, percent, plugged):
            self.percent = percent
            self.power_plugged = plugged

    psutil.sensors_battery = lambda: MockBattery(15, False)
    print("\n--- Low Battery Simulation (15%, Unplugged, ECO) ---")
    print(f"Should Throttle: {battery_manager.should_throttle()}")
    print(f"Sleep Multiplier: {battery_manager.get_sleep_multiplier()}")

    # Clean up
    psutil.sensors_battery = original_battery

if __name__ == "__main__":
    test_performance_modes()
