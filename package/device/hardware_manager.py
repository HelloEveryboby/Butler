"""
硬件管理器 (HardwareManager)
负责与 STM32 硬件进行串口通信，遵循 HCP v1 协议。
支持控制指令、状态查询和报警。
"""
import time
import json
import threading
from typing import Optional, Callable
try:
    import serial
except ImportError:
    serial = None

class HardwareManager:
    PROTOCOL_HEADER = 0xAA
    PROTOCOL_END = 0x55

    # Device Types
    DEV_LED = 0x10
    DEV_MOTOR = 0x20
    DEV_SENSOR = 0x30
    DEV_NFC = 0x40
    DEV_SYSTEM = 0xFF

    # Command Types
    CMD_CONTROL = 0x01
    CMD_QUERY = 0x02
    CMD_ALARM = 0x03

    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.running = False
        self.callback: Optional[Callable] = None

    def connect(self) -> bool:
        if not serial:
            print("错误: 未安装 pyserial 库。")
            return False
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            self.running = True
            threading.Thread(target=self._listen_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"硬件连接失败: {e}")
            return False

    def disconnect(self):
        self.running = False
        if self.ser:
            self.ser.close()

    def send_command(self, cmd_type: int, device: int, action: int, data: int = 0):
        """
        构建并发送 Hex 指令包。
        | Header (1) | Type (1) | Device (1) | Action (1) | Data (4) | CheckSum (1) | End (1) |
        """
        if not self.ser or not self.ser.is_open:
            return

        # Data 拆分为 4 字节 (Big-Endian)
        data_bytes = data.to_bytes(4, byteorder='big')

        packet = bytearray([
            self.PROTOCOL_HEADER,
            cmd_type,
            device,
            action
        ])
        packet.extend(data_bytes)

        # 计算 CheckSum (前 8 位异或)
        checksum = 0
        for b in packet:
            checksum ^= b
        packet.append(checksum)
        packet.append(self.PROTOCOL_END)

        try:
            self.ser.write(packet)
            self.ser.flush()
        except Exception as e:
            print(f"指令发送失败: {e}")

    def _listen_loop(self):
        """持续监听硬件反馈。"""
        while self.running and self.ser:
            try:
                if self.ser.in_waiting >= 10:
                    header = self.ser.read(1)
                    if header[0] == self.PROTOCOL_HEADER:
                        rest = self.ser.read(9)
                        if len(rest) == 9 and rest[8] == self.PROTOCOL_END:
                            # 校验逻辑...
                            self._handle_response(rest)
            except Exception:
                pass
            time.sleep(0.1)

    def _handle_response(self, packet_rest: bytes):
        """解析硬件返回的包。"""
        cmd_type = packet_rest[0]
        device = packet_rest[1]
        action = packet_rest[2]
        data = int.from_bytes(packet_rest[3:7], byteorder='big')

        if self.callback:
            self.callback(cmd_type, device, action, data)

    def set_callback(self, callback: Callable):
        self.callback = callback

    # 快捷方法
    def blink_green(self):
        self.send_command(self.CMD_CONTROL, self.DEV_LED, 0x01, 0x00FF00) # Green LED

    def alarm_red(self):
        self.send_command(self.CMD_ALARM, self.DEV_SYSTEM, 0x01, 0xFF0000) # Red Alarm

    def lock_hardware(self):
        self.send_command(self.CMD_CONTROL, self.DEV_SYSTEM, 0x00, 0xDEADBEEF)

if __name__ == "__main__":
    # 模拟测试
    mgr = HardwareManager(port="COM3") # 替换为实际串口
    if mgr.connect():
        print("连接成功，尝试闪烁绿灯...")
        mgr.blink_green()
        time.sleep(1)
        mgr.disconnect()
