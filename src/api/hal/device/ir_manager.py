from utils.device.stm32_hw_bridge import STM32HardwareBridge
from utils.asset_loader import AssetLoader
import os

class IRManager:
    """
    High-level manager for IR operations via STM32.
    (NFC support removed in v2.0)
    """
    def __init__(self):
        self.bridge = STM32HardwareBridge()
        self._connected = False

    def _ensure_connected(self):
        if not self._connected:
            self.bridge.connect()
            self._connected = True

    def learn_ir_command(self):
        self._ensure_connected()
        return self.bridge.call("ir_learn")

    def transmit_ir_code(self, code_id):
        self._ensure_connected()
        return self.bridge.call("ir_transmit", {"code_id": code_id})

def run(intent=None, params=None):
    """
    Butler Package Entry Point
    """
    manager = IRManager()

    if intent == "红外学习":
        res = manager.learn_ir_command()
        return res.get("result", {}).get("message", "红外学习启动失败")

    elif intent == "红外发射":
        code_id = params.get("code_id") if params else None
        if code_id:
            res = manager.transmit_ir_code(code_id)
            return f"红外代码 {code_id} 已发射"
        return "请指定红外代码 ID"

    return "红外管理器就绪，但未识别具体指令。"

if __name__ == "__main__":
    # Quick manual test
    print(run(intent="红外学习"))
