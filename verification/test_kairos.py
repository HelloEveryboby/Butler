import sys
import os
import time
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from butler.core.battery_manager import battery_manager
from butler.core.cron_scheduler import cron_scheduler
from butler.core.dream_engine import DreamEngine
from butler.core.proactive_agent import ProactiveAgent
from butler.core.event_bus import event_bus

def test_battery_manager():
    print("--- Testing BatteryManager ---")
    percent, plugged = battery_manager.get_status()
    print(f"Status: {percent}%, Plugged: {plugged}")
    print(f"Should Throttle: {battery_manager.should_throttle()}")
    print(f"Sleep Multiplier: {battery_manager.get_sleep_multiplier()}")

def test_cron_scheduler():
    print("\n--- Testing CronScheduler ---")
    test_event_fired = [False]

    def on_test_event():
        print("Cron event fired!")
        test_event_fired[0] = True

    event_bus.on("cron:test_task", on_test_event)
    cron_scheduler.add_task("test_task", interval_seconds=1, permanent=True)

    # Manually trigger a check (usually happens in loop)
    cron_scheduler._check_and_run_tasks()

    if test_event_fired[0]:
        print("CronScheduler test passed.")
    else:
        print("CronScheduler test failed (event not fired).")

def test_dream_engine():
    print("\n--- Testing DreamEngine ---")
    # We need a mock jarvis app with nlu_service
    class MockNLU:
        def ask_llm(self, prompt, history):
            return "Consolidated Memory: User likes efficiency and low power."

    class MockJarvis:
        def __init__(self):
            self.nlu_service = MockNLU()

    jarvis = MockJarvis()
    dream_engine = DreamEngine(jarvis)

    print(f"Should Dream: {dream_engine.should_dream()}")
    # Force a dream
    print("Forcing a dream...")
    # Mock gather_signals to avoid needing actual log files
    dream_engine._gather_signals = lambda: "User: Hi\nAssistant: Hello"
    dream_engine.dream()

    memory_md = Path("data/butler_memory/MEMORY.md")
    if memory_md.exists():
        with open(memory_md, 'r') as f:
            content = f.read()
            if "Consolidated Memory" in content:
                print("DreamEngine test passed.")
            else:
                print("DreamEngine test failed (content not found).")
    else:
        print("DreamEngine test failed (MEMORY.md not created).")

def test_proactive_agent():
    print("\n--- Testing ProactiveAgent ---")
    class MockJarvis:
        def __init__(self):
            self.long_memory = type('obj', (object,), {'logs': type('obj', (object,), {'add_daily_log': lambda x: print(f"Log: {x}")})})

    jarvis = MockJarvis()
    agent = ProactiveAgent(jarvis)
    print(f"Last Activity: {agent.last_activity}")
    agent.update_activity()
    print(f"Updated Activity: {agent.last_activity}")

    # Mock idle time
    agent.last_activity = time.time() - 3 * 3600
    print("Simulating 3 hours idle...")
    agent.tick() # Should take initiative

if __name__ == "__main__":
    try:
        test_battery_manager()
        test_cron_scheduler()
        test_dream_engine()
        test_proactive_agent()
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if os.path.exists("data/scheduled_tasks.json"):
            os.remove("data/scheduled_tasks.json")
        if os.path.exists("data/.cron_lock"):
            os.remove("data/.cron_lock")
        # Keep MEMORY.md for now to verify but maybe cleanup later
