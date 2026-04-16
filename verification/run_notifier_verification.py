import time
import json
import os
import sys
import threading

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from butler.core.notifier_system import notifier
from butler.core.event_bus import event_bus

def trigger_test_notifications():
    time.sleep(2)
    print("Triggering Toast Notification...")
    notifier.push({
        "title": "测试提醒 (Toast)",
        "content": "这是一条普通的低优先级测试提醒。",
        "priority": 1
    })

    time.sleep(2)
    print("Triggering Fullscreen Notification...")
    notifier.push({
        "title": "核心警报 (Fullscreen)",
        "content": "检测到核心系统异常，请立即检查！",
        "priority": 2
    })

if __name__ == "__main__":
    # Start trigger thread
    threading.Thread(target=trigger_test_notifications, daemon=True).start()

    # Run Modern UI
    from frontend.program.modern_app import main
    main()
