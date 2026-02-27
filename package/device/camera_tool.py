import os
import time
import base64
import logging

try:
    import cv2
except ImportError:
    cv2 = None

class CameraTool:
    """
    Butler 摄像头交互工具 (Camera Interaction Tool)
    支持拍照、简单的视频帧获取，可用于视觉识别或安全监控。
    """
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        self.logger = logging.getLogger("CameraTool")

    def take_photo(self, save_path="data/captured_photo.jpg") -> str:
        """拍摄一张照片并保存"""
        if cv2 is None:
            return "Error: opencv-python is not installed. Camera access unavailable."

        # 确保目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            return "Error: Could not open camera."

        # 给摄像头一点预热时间
        time.sleep(1)

        ret, frame = cap.read()
        if ret:
            cv2.imwrite(save_path, frame)
            cap.release()
            return f"Photo saved to {save_path}"
        else:
            cap.release()
            return "Error: Failed to capture frame."

    def get_frame_base64(self) -> str:
        """获取当前帧并返回 Base64 编码的字符串（用于 UI 展示）"""
        if cv2 is None:
            return "Error: opencv-python is not installed."

        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            return "Error: Could not open camera."

        ret, frame = cap.read()
        cap.release()

        if ret:
            _, buffer = cv2.imencode('.jpg', frame)
            b64_string = base64.b64encode(buffer).decode('utf-8')
            return b64_string
        return "Error: Failed to capture frame."

def run():
    """Package 入口"""
    if cv2 is None:
        print("[!] 错误：未安装 opencv-python 库。请通过 'pip install opencv-python' 安装以启用摄像头功能。")
        return

    tool = CameraTool()
    print("[*] 正在尝试调用摄像头拍摄预览照...")
    res = tool.take_photo()
    print(res)

if __name__ == "__main__":
    run()
