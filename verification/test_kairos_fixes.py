import sys
import os
import time
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from butler.core.cron_scheduler import cron_scheduler
from butler.core.battery_manager import battery_manager
from butler.resource_manager import ResourceManager, PerformanceMode

def test_cron_persistence():
    print("--- Testing Cron Persistence ---")
    tasks_file = "data/test_tasks.json"
    if os.path.exists(tasks_file): os.remove(tasks_file)

    scheduler = type(cron_scheduler)(tasks_file=tasks_file)

    # 1. Add a task
    print("Adding initial task...")
    scheduler.add_task("persist_test", interval_seconds=3600)
    next_run_1 = scheduler.tasks["persist_test"]["next_run"]

    # 2. Simulate restart and add task again
    print("Simulating restart...")
    scheduler2 = type(cron_scheduler)(tasks_file=tasks_file)
    scheduler2.add_task("persist_test", interval_seconds=3600)
    next_run_2 = scheduler2.tasks["persist_test"]["next_run"]

    if abs(next_run_1 - next_run_2) < 1:
        print("Cron Persistence test passed (timer preserved).")
    else:
        print(f"Cron Persistence test failed: {next_run_1} vs {next_run_2}")

def test_eco_background_running():
    print("\n--- Testing ECO Background Running ---")
    res_mgr = ResourceManager()
    battery_manager.res_mgr = res_mgr
    res_mgr.set_mode(PerformanceMode.ECO)

    import psutil
    original_battery = psutil.sensors_battery
    class MockBattery:
        def __init__(self, percent, plugged):
            self.percent = percent
            self.power_plugged = plugged

    # Plugged in should allow background tasks in ECO
    psutil.sensors_battery = lambda: MockBattery(50, True)
    print("Plugged in, ECO mode:")
    print(f"Can Run Background Task: {battery_manager.can_run_background_task()}")

    # Unplugged and low battery should NOT allow
    psutil.sensors_battery = lambda: MockBattery(15, False)
    print("Unplugged, 15% battery, ECO mode:")
    print(f"Can Run Background Task: {battery_manager.can_run_background_task()}")

    psutil.sensors_battery = original_battery

if __name__ == "__main__":
    test_cron_persistence()
    test_eco_background_running()
