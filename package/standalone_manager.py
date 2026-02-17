import serial
import serial.tools.list_ports
import threading
import time
import logging
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class StandaloneManager:
    def __init__(self, jarvis_app=None, port=None, baudrate=115200):
        self.jarvis = jarvis_app
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.running = False
        self.read_thread = None

    def find_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def connect(self, port=None):
        target_port = port or self.port
        if not target_port:
            available = self.find_ports()
            if available: target_port = available[0]
            else: return False, "No serial ports found"

        try:
            self.serial_conn = serial.Serial(target_port, self.baudrate, timeout=1)
            self.running = True
            self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self.read_thread.start()
            logger.info(f"Connected to standalone hardware on {target_port}")
            return True, f"Connected to {target_port}"
        except Exception as e:
            logger.error(f"Failed to connect to serial: {e}")
            return False, str(e)

    def _read_loop(self):
        while self.running and self.serial_conn and self.serial_conn.is_open:
            try:
                if self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode('utf-8').strip()
                    if line:
                        logger.info(f"Serial Received: {line}")
                        if self.jarvis:
                            # 假设硬件发送的是指令文本
                            self.jarvis.handle_user_command(line)
            except Exception as e:
                logger.error(f"Serial read error: {e}")
                break
            time.sleep(0.1)

    def send_data(self, data):
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write(data.encode('utf-8'))
                return True
            except Exception as e:
                logger.error(f"Serial write error: {e}")
        return False

    def disconnect(self):
        self.running = False
        if self.serial_conn:
            self.serial_conn.close()

def run(command=None, *args, **kwargs):
    manager = StandaloneManager()
    if command == "list":
        return manager.find_ports()
    elif command == "connect":
        port = args[0] if args else None
        success, msg = manager.connect(port)
        return msg
    elif command == "send":
        data = args[0] if args else ""
        if manager.connect()[0]: # Auto connect if not connected
            manager.send_data(data)
            return f"Sent: {data}"
    return "Usage: run(command='list'|'connect'|'send', args=['...'])"
