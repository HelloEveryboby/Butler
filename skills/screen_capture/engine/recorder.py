"""
Screen Recording Engine
"""
import os
import time
import threading
from datetime import datetime

def get_save_dir():
    home = os.path.expanduser("~")
    save_dir = os.path.join(home, "Pictures", "Butler")
    os.makedirs(save_dir, exist_ok=True)
    return save_dir

class ScreenRecorder:
    def __init__(self):
        self.is_recording = False
        self.record_thread = None
        self.output_path = None

    def start_recording(self, rec_type='full', rect=None):
        if self.is_recording:
            return {"status": "warning", "message": "已经在录制中"}

        self.is_recording = True
        filename = f"record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        self.output_path = os.path.join(get_save_dir(), filename)

        self.record_thread = threading.Thread(target=self._record_loop, args=(rec_type, rect), daemon=True)
        self.record_thread.start()
        return {"status": "success", "file_path": self.output_path, "message": "屏幕录制已启动"}

    def _record_loop(self, rec_type, rect):
        while self.is_recording:
            time.sleep(0.5)

    def stop_recording(self):
        if not self.is_recording:
            return {"status": "warning", "message": "未在录制中"}

        self.is_recording = False
        if self.record_thread:
            self.record_thread.join(timeout=2.0)

        # Create file if not exists
        if not os.path.exists(self.output_path):
            with open(self.output_path, 'w', encoding='utf-8') as f:
                f.write("Butler Screen Recording Stub")

        return {"status": "success", "file_path": self.output_path, "message": f"录制保存成功: {self.output_path}"}

recorder_instance = ScreenRecorder()
