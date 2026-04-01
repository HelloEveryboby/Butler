from package.device.stm32_hw_bridge import STM32HardwareBridge

class NFCIRManager:
    """
    High-level manager for NFC and IR operations via STM32.
    """
    def __init__(self):
        self.bridge = STM32HardwareBridge()
        self._connected = False

    def _ensure_connected(self):
        if not self._connected:
            self.bridge.connect()
            self._connected = True

    def get_nfc_uid(self):
        self._ensure_connected()
        response = self.bridge.call("nfc_get_uid")
        if "result" in response:
            return response["result"].get("uid")
        return None

    def clone_nfc_tag(self):
        self._ensure_connected()
        return self.bridge.call("nfc_clone")

    def read_nfc_sector(self, sector=0):
        self._ensure_connected()
        return self.bridge.call("nfc_read_sector", {"sector": sector})

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
    manager = NFCIRManager()

    if intent == "NFC读取":
        uid = manager.get_nfc_uid()
        return f"读取到 NFC UID: {uid}" if uid else "未检测到 NFC 标签"

    elif intent == "红外学习":
        res = manager.learn_ir_command()
        return res.get("result", {}).get("message", "红外学习启动失败")

    elif intent == "NFC克隆":
        res = manager.clone_nfc_tag()
        if "result" in res:
            return res["result"].get("msg", "NFC 克隆已启动")
        return "NFC 克隆失败"

    return "硬件管理器就绪，但未识别具体指令。"

if __name__ == "__main__":
    # Quick manual test
    print(run(intent="NFC读取"))
