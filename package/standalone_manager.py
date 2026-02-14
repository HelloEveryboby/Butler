import serial.tools.list_ports
import logging

logger = logging.getLogger(__name__)

def list_serial_ports():
    """列出当前连接的所有串口设备，帮助用户找到 ESP32。"""
    ports = serial.tools.list_ports.comports()
    result = []
    for port, desc, hwid in sorted(ports):
        result.append({"port": port, "description": desc})
    return result

def run(command=None, *args, **kwargs):
    """
    独立设备管理器。
    支持命令: list (列出串口)
    """
    if command == "list":
        ports = list_serial_ports()
        if not ports:
            return "未发现串口设备，请检查单片机是否已连接。"

        output = "发现以下串口设备:\n"
        for p in ports:
            output += f"- {p['port']}: {p['description']}\n"
        output += "\n您可以根据此信息在 Arduino IDE 中选择正确的端口进行烧录。"
        return output

    return "可用命令: list (查看串口连接情况)"
