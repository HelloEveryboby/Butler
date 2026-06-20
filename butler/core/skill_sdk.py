import sys
import json
from typing import Any, Optional

class ButlerSkillSDK:
    """
    Butler 技能极简 SDK。
    为隔离运行的技能提供与 Butler 核心通信的便捷接口。
    """
    @staticmethod
    def speak(text: str):
        """让 Butler 朗读文本"""
        print(json.dumps({"action": "speak", "payload": {"text": text}}), flush=True)

    @staticmethod
    def ui_print(text: str, tag: str = "ai_response"):
        """在 Butler UI 中打印消息"""
        print(json.dumps({"action": "ui_print", "payload": {"text": text, "tag": tag}}), flush=True)

    @staticmethod
    def set_result(data: Any):
        """发送最终执行结果并结束技能"""
        print(json.dumps({"action": "result", "payload": data}), flush=True)

    @staticmethod
    def write_blackboard(key: str, value: Any, ttl: float = 60.0):
        """向 Butler 黑板写入临时数据 (ESB)"""
        print(json.dumps({
            "action": "blackboard_write",
            "payload": {"key": key, "value": value, "ttl": ttl}
        }), flush=True)

    @staticmethod
    def get_input() -> Optional[dict]:
        """获取来自 Butler 的初始输入载荷 (action, config, manifest, kwargs)"""
        line = sys.stdin.readline()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

# 便捷实例
sdk = ButlerSkillSDK()
