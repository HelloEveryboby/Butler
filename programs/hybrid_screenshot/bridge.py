import sys
import os
import json
import base64
import threading
import subprocess
import time
import webview
from io import BytesIO
import mss
import mss.tools
from PIL import Image
import keyboard

# Ensure we can import core modules if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

class ScreenshotBridge:
    def __init__(self):
        self.sct = mss.mss()
        self.window = None

    def capture_full_screen(self, monitor_idx=0):
        """Captures full screen."""
        monitor = self.sct.monitors[monitor_idx]
        sct_img = self.sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def open_overlay(self):
        """Opens the transparent overlay."""
        virtual_screen = self.sct.monitors[0]
        html_path = "file://" + os.path.join(os.path.dirname(__file__), 'ui', 'overlay.html')

        self.window = webview.create_window(
            'Butler Screenshot Overlay',
            url=html_path,
            transparent=True,
            frameless=True,
            width=virtual_screen['width'],
            height=virtual_screen['height'],
            x=virtual_screen['left'],
            y=virtual_screen['top'],
            on_top=True
        )

        self.window.expose(self.save_screenshot_to_file)
        self.window.expose(self.close_overlay)
        self.window.expose(self.get_full_screenshot_b64)

        webview.start()

    def get_full_screenshot_b64(self):
        return self.capture_full_screen(0)

    def save_screenshot_to_file(self, data_url):
        try:
            header, encoded = data_url.split(",", 1)
            data = base64.b64decode(encoded)
            save_dir = os.path.join(os.getcwd(), "data", "screenshots")
            if not os.path.exists(save_dir): os.makedirs(save_dir)
            filename = f"screenshot_{int(time.time())}.png"
            filepath = os.path.join(save_dir, filename)
            with open(filepath, "wb") as f: f.write(data)
            return {"status": "success", "path": filepath}
        except Exception as e: return {"status": "error", "message": str(e)}

    def close_overlay(self):
        if self.window: self.window.destroy()

if __name__ == "__main__":
    bridge = ScreenshotBridge()
    if "--overlay" in sys.argv: bridge.open_overlay()
    elif "--full" in sys.argv: print(bridge.capture_full_screen())
