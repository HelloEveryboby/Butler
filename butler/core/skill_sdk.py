import os
import sys
import json
import ctypes
import logging
import gc

logger = logging.getLogger("SkillSDK")

def scrub_env(key: str):
    """
    物理级内存擦除：直接改写环境变量所在的内存空间。
    """
    if key not in os.environ:
        return

    val = os.environ[key]
    if not val:
        return

    try:
        # 在 Python 中，os.environ 映射到 C 层的 environ
        # 我们尝试通过 ctypes 找到该字符串的地址并清零
        # 注意：这在某些平台上可能由于内存保护而失败，但在 Headless Linux 上通常有效
        if sys.platform == 'win32':
            # Windows 上的实现略有不同
            pass
        else:
            libc = ctypes.CDLL("libc.so.6")
            # 找到 getenv 返回的原始指针
            libc.getenv.restype = ctypes.c_void_p
            ptr = libc.getenv(key.encode('utf-8'))
            if ptr:
                # 覆盖内存为 0
                ctypes.memset(ptr, 0, len(val))
    except Exception as e:
        logger.debug(f"Scrub memory failed for {key}: {e}")

    # 应用层同步删除
    if key in os.environ:
        del os.environ[key]
    gc.collect()

class SkillSDK:
    """
    Skill 开发工具包，提供统一的 IPC 与安全接口。
    """
    @staticmethod
    def get_input():
        """读取 Go 内核下发的初始载荷"""
        line = sys.stdin.readline()
        if not line:
            return {}
        return json.loads(line)

    @staticmethod
    def send_result(data: any):
        """向 Go 内核发送执行结果"""
        msg = {
            "action": "result",
            "payload": data
        }
        print(json.dumps(msg), flush=True)

    @staticmethod
    def speak(text: str):
        msg = {"action": "speak", "payload": {"text": text}}
        print(json.dumps(msg), flush=True)

    @staticmethod
    def ui_print(text: str, tag: str = "ai_response"):
        msg = {"action": "ui_print", "payload": {"text": text, "tag": tag}}
        print(json.dumps(msg), flush=True)

    @staticmethod
    def push_snapshot(state: dict):
        """推送当前状态快照到时序总线"""
        msg = {"action": "snapshot_push", "payload": state}
        print(json.dumps(msg), flush=True)

    @staticmethod
    def cleanup():
        """强制清理敏感环境变量"""
        for key in list(os.environ.keys()):
            if key.startswith("VAULT_") or key == "BUTLER_TOKEN":
                scrub_env(key)
        gc.collect()

# Helper for platform native OCR (Placeholder for logic)
def native_ocr(image_path):
    if sys.platform == 'win32':
        # logic for Windows.Media.Ocr
        return "Windows Native OCR Result"
    elif sys.platform == 'darwin':
        # logic for Apple Vision
        return "Apple Vision OCR Result"
    return "Generic OCR Result"
