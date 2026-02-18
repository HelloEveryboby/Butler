"""
设备配置工具 - 用于管理和配置系统连接的各种硬件设备。
"""
import os
import json
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "system_config.json")

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def run(command=None, **kwargs):
    config = load_config()

    if not command:
        return f"当前配置: {json.dumps(config, indent=2, ensure_ascii=False)}"

    if command == "set_usb_screen":
        width = kwargs.get("width")
        height = kwargs.get("height")
        if width and height:
            if "display" not in config: config["display"] = {}
            if "usb_screen" not in config["display"]: config["display"]["usb_screen"] = {}
            config["display"]["usb_screen"]["width"] = int(width)
            config["display"]["usb_screen"]["height"] = int(height)
            save_config(config)
            return "USB 屏幕配置已更新。"
        return "错误: 请提供 width 和 height。"

    elif command == "set_voice_mode":
        mode = kwargs.get("mode")
        if mode in ["online", "offline"]:
            if "voice" not in config: config["voice"] = {}
            config["voice"]["mode"] = mode
            save_config(config)
            return f"语音模式已设置为 {mode}。"
        return "错误: 无效的模式 (online/offline)。"

    elif command == "set_mqtt":
        broker = kwargs.get("broker")
        if broker:
            if "iot" not in config: config["iot"] = {}
            config["iot"]["mqtt_broker"] = broker
            save_config(config)
            return "MQTT 配置已更新。"
        return "错误: 请提供 broker 地址。"

    return f"未知命令: {command}。支持: set_usb_screen, set_voice_mode, set_mqtt"
