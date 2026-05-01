import os
import json
import subprocess
import sys
import time

def handle_request(jarvis_app, config, manifest, **kwargs):
    """
    处理 AI 的截图请求
    """
    intent = kwargs.get("intent")
    entities = kwargs.get("entities", {})

    capture_type = entities.get("type", "full")
    url = entities.get("url")

    # 路径：programs/hybrid_screenshot/bridge.py
    bridge_path = os.path.join(os.getcwd(), "programs", "hybrid_screenshot", "bridge.py")

    if capture_type == "web" and url:
        return {
            "status": "pending",
            "message": f"正在启动网页滚动截图任务：{url}。完成后将保存至 Screenshots 目录。",
            "metadata": {"type": "web", "url": url}
        }

    elif capture_type == "region":
        subprocess.Popen([sys.executable, bridge_path, "--overlay"])
        return "截图 Overlay 已启动，请在屏幕上进行框选和标注。"

    elif capture_type == "window":
        try:
            from programs.hybrid_screenshot.bridge import ScreenshotBridge
            bridge = ScreenshotBridge()
            b64_data = bridge.capture_active_window()
            res = bridge.save_screenshot_to_file("data:image/png;base64," + b64_data)

            if res["status"] == "success":
                image_path = res['path']
                jarvis_app.ui_print(json.dumps({
                    "type": "media", "media_type": "image", "url": f"file://{image_path}", "title": "应用窗口截图"
                }), tag='media')
                return {"status": "success", "message": f"窗口截图已完成：{image_path}", "image_path": image_path}
            return f"窗口截图失败: {res.get('message')}"
        except Exception as e:
            return f"窗口截图执行错误: {str(e)}"

    else:
        try:
            from programs.hybrid_screenshot.bridge import ScreenshotBridge
            bridge = ScreenshotBridge()
            b64_data = bridge.capture_full_screen(0)
            res = bridge.save_screenshot_to_file("data:image/png;base64," + b64_data)

            if res["status"] == "success":
                image_path = res['path']
                jarvis_app.ui_print(json.dumps({
                    "type": "media", "media_type": "image", "url": f"file://{image_path}", "title": "全屏截图"
                }), tag='media')

                return {
                    "status": "success",
                    "message": f"全屏截图已完成：{image_path}",
                    "image_path": image_path
                }
            return f"全屏截图失败: {res.get('message')}"
        except Exception as e:
            return f"全屏截图执行错误: {str(e)}"

def run():
    print("Screenshot skill loaded.")
