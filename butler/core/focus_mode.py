import os
import sys
import threading
import time
import logging
from butler.core.event_bus import event_bus

logger = logging.getLogger("FocusMode")

class FocusMode:
    """
    沉浸模式 (P2)
    负责静音、全屏通知以及状态广播。
    """
    def __init__(self, jarvis):
        self.jarvis = jarvis
        self.active = False
        self.timer_thread = None

    def start(self, duration_minutes=25):
        if self.active: return "Focus mode already active."

        self.active = True
        logger.info(f"Starting Focus Mode for {duration_minutes}m")

        # 1. 静音系统 (模拟实现，针对不同平台可调用具体指令)
        self._mute_system()

        # 2. 广播状态
        self.jarvis.runner_server.broadcast_command("status_update", "BUSY")

        # 3. 通知前端展示全屏计时器
        event_bus.emit("ui_output", f"Focus Mode: {duration_minutes}m started.", tag="focus_start")

        # 4. 启动倒计时
        self.timer_thread = threading.Thread(target=self._timer_loop, args=(duration_minutes * 60,))
        self.timer_thread.daemon = True
        self.timer_thread.start()

        return f"Focus mode activated for {duration_minutes} minutes."

    def stop(self):
        if not self.active: return
        self.active = False
        self._unmute_system()
        self.jarvis.runner_server.broadcast_command("status_update", "AVAILABLE")
        event_bus.emit("ui_output", "Focus Mode ended.", tag="focus_stop")
        return "Focus mode stopped."

    def _timer_loop(self, seconds):
        while seconds > 0 and self.active:
            time.sleep(1)
            seconds -= 1
        if self.active:
            self.stop()
            self.jarvis.speak("专注于此的时间已结束，休息一下吧。")

    def _mute_system(self):
        # 针对 Windows/Linux 的简单静音尝试
        try:
            if sys.platform == "win32":
                import ctypes
                # 切换静音
                # ctypes.windll.user32.keybd_event(0xAD, 0, 0, 0)
                pass
            else:
                os.system("amixer set Master mute > /dev/null 2>&1")
        except: pass

    def _unmute_system(self):
        try:
            if sys.platform != "win32":
                os.system("amixer set Master unmute > /dev/null 2>&1")
        except: pass
