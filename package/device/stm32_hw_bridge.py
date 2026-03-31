import json
import serial
import serial.tools.list_ports
import threading
import time
from typing import Callable, Optional


class STM32HardwareBridge:
    """
    PC-side bridge for communicating with STM32 Hardware Nodes via BHL Protocol.
    """

    def __init__(self, port: str = None, baudrate: int = 115200, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser: Optional[serial.Serial] = None
        self.running = False
        self._callback: Optional[Callable[[dict], None]] = None
        self._request_id = 0
        self._pending_requests = {}

    def find_node(self) -> Optional[str]:
        """Automatically detect STM32 nodes based on common USB-TTL chips."""
        ports = serial.tools.list_ports.comports()
        for p in ports:
            # Common chips like CH340, CP2102, FT232
            if any(
                id_str in p.description.upper()
                for id_str in ["CH340", "CP210", "FT232", "USB-SERIAL", "STM32"]
            ):
                return p.device
        return None

    def connect(self):
        if not self.port:
            self.port = self.find_node()

        if not self.port:
            raise Exception("No STM32 hardware node found. Please specify a port.")

        self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        self.running = True
        threading.Thread(target=self._read_loop, daemon=True).start()
        print(f"[*] Connected to STM32 Node on {self.port}")

    def _read_loop(self):
        while self.running and self.ser:
            try:
                line = self.ser.readline().decode("utf-8").strip()
                if not line:
                    continue

                data = json.loads(line)

                # Handle Response
                if "id" in data and data["id"] in self._pending_requests:
                    event = self._pending_requests.pop(data["id"])
                    event["response"] = data
                    event["flag"].set()

                # Handle Async Notification
                elif self._callback:
                    self._callback(data)

            except Exception as e:
                print(f"[!] Bridge Read Error: {e}")
                time.sleep(1)

    def call(
        self, method: str, params: dict = None, wait: bool = True, timeout: float = 5.0
    ) -> Optional[dict]:
        """Call a BHL method on the STM32 hardware."""
        self._request_id += 1
        req_id = self._request_id

        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": req_id,
        }

        event = {"flag": threading.Event(), "response": None}
        self._pending_requests[req_id] = event

        self.ser.write((json.dumps(payload) + "\n").encode("utf-8"))

        if wait:
            if event["flag"].wait(timeout):
                return event["response"]
            else:
                self._pending_requests.pop(req_id, None)
                raise TimeoutError(f"Hardware response timeout for method {method}")
        return None

    def close(self):
        self.running = False
        if self.ser:
            self.ser.close()


if __name__ == "__main__":
    # Test script
    try:
        bridge = STM32HardwareBridge()
        bridge.connect()
        print(f"Node UID: {bridge.call('nfc_get_uid')}")
    except Exception as e:
        print(f"Test failed: {e}")
