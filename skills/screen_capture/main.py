"""
Screen Capture & Recording Main Entry Point
"""
from skills.screen_capture.engine.capture import (
    capture_full_screen,
    capture_area_screen,
    capture_long_screenshot
)
from skills.screen_capture.engine.recorder import recorder_instance

def execute(action, **kwargs):
    """
    Skill entry point for Screen Capture & Recording
    """
    if action == "full_screenshot":
        return capture_full_screen(kwargs.get("save_path"))
    elif action == "area_screenshot":
        return capture_area_screen(kwargs.get("rect"), kwargs.get("save_path"))
    elif action == "long_screenshot":
        return capture_long_screenshot(kwargs.get("save_path"))
    elif action == "start_recording":
        return recorder_instance.start_recording(kwargs.get("type", "full"), kwargs.get("rect"))
    elif action == "stop_recording":
        return recorder_instance.stop_recording()
    else:
        return {"status": "error", "message": f"未知的操作类型: {action}"}
