import threading
import time
from pynput import keyboard
from butler.core.event_bus import event_bus
from package.core_utils.log_manager import LogManager
from butler.core.config_loader import config_loader

logger = LogManager.get_logger(__name__)

class HotKeyObserver:
    def __init__(self, hotkey_str: str = None):
        # Default hotkey: <alt>+<space>
        self.hotkey_str = hotkey_str or config_loader.get("system.hotkey", "<alt>+<space>")
        self.listener = None
        self._running = False

    def _on_activate(self):
        logger.info(f"Hotkey {self.hotkey_str} activated!")
        event_bus.emit("system_toggle_ui")

    def start(self):
        if self.listener:
            return

        try:
            self.listener = keyboard.GlobalHotKeys({
                self.hotkey_str: self._on_activate
            })
            self.listener.start()
            self._running = True
            logger.info(f"HotKeyObserver started with hotkey: {self.hotkey_str}")
        except Exception as e:
            logger.error(f"Failed to start HotKeyObserver: {e}")

    def stop(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
            self._running = False
            logger.info("HotKeyObserver stopped")

# Global singleton-like service
hotkey_service = HotKeyObserver()

def start_hotkey_service():
    threading.Thread(target=hotkey_service.start, daemon=True).start()
