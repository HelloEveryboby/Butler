import os
import sys
import threading
import time
import json
import logging
from typing import Optional, Dict, Any

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from package.core_utils.log_manager import LogManager

class StandaloneManager:
    """
    Manages Butler's hardware lifecycle on standalone media (Dev Boards, USB sticks).
    Specifically handles detection of host connections and display availability via a data cable.
    """
    def __init__(self, jarvis_app=None):
        self.logger = LogManager.get_logger(__name__)
        self.jarvis = jarvis_app
        self._running = False
        self._monitor_thread = None

        # State
        self.connection_status = "Disconnected"
        self.display_detected = False
        self.detected_devices = []
        self.last_check_time = 0
        self.check_interval = 5.0 # Seconds

    def start(self):
        """Starts the hardware monitoring loop."""
        if self._running:
            return
        self._running = True
        self._monitor_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._monitor_thread.start()
        self.logger.info("StandaloneManager hardware monitoring started.")

    def stop(self):
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1)

    def _run_loop(self):
        """Monitors hardware connections and display status."""
        while self._running:
            try:
                if self.jarvis and hasattr(self.jarvis, 'sysutil'):
                    # 1. Check for Host Connections (Serial/USB)
                    conn_info = self.jarvis.sysutil.call("check_connections", {})
                    new_conn_status = "Connected" if (conn_info and conn_info.get("connection_found")) else "Disconnected"

                    if new_conn_status != self.connection_status:
                        self.connection_status = new_conn_status
                        self.detected_devices = conn_info.get("devices", "").split() if conn_info else []
                        self._on_connection_change(new_conn_status)

                    # 2. Check for Display Availability
                    display_info = self.jarvis.sysutil.call("detect_displays", {})
                    new_display_state = display_info.get("detected", False) if display_info else False

                    if new_display_state != self.display_detected:
                        self.display_detected = new_display_state
                        self._on_display_change(new_display_state)

            except Exception as e:
                self.logger.error(f"StandaloneManager loop error: {e}")

            time.sleep(self.check_interval)

    def _on_connection_change(self, status: str):
        """Called when a data cable is connected or disconnected."""
        self.logger.info(f"Data Link Status Changed: {status}")
        if status == "Connected":
            msg = f"检测到数据线连接。可用设备: {', '.join(self.detected_devices)}"
            self.logger.info(msg)
            # Notify the main app
            if self.jarvis:
                self.jarvis.ui_print(msg, tag='system_message')

    def _on_display_change(self, detected: bool):
        """Called when a screen is plugged in or unplugged."""
        self.logger.info(f"Display Detection Changed: {detected}")
        if detected and self.jarvis:
            # Trigger the UI suggestion logic in the main app
            if hasattr(self.jarvis, 'suggest_ui_activation'):
                self.jarvis.suggest_ui_activation()

    def get_status(self) -> Dict[str, Any]:
        return {
            "connection": self.connection_status,
            "devices": self.detected_devices,
            "display": "Detected" if self.display_detected else "None",
            "is_board": os.path.exists("/proc/device-tree/model") or os.uname().machine.startswith("arm")
        }

def run(jarvis_app=None):
    """Entry point for the StandaloneManager service."""
    manager = StandaloneManager(jarvis_app)
    manager.start()
    return manager
