"""
BLE Connector Package.
Uses ctypes to interact with the C++ BLE Framework shared library.
This maintains the connection state within the Python process.
"""
import ctypes
import os
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Define structures to match C++
class BLEDeviceInfo(ctypes.Structure):
    _fields_ = [
        ("address", ctypes.c_char * 19),
        ("name", ctypes.c_char * 256),
        ("rssi", ctypes.c_int)
    ]

class BLEConnector:
    _instance = None
    _lib = None
    _fw = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BLEConnector, cls).__new__(cls)
            cls._init_library()
        return cls._instance

    @classmethod
    def _init_library(cls):
        try:
            # Find the .so file in the programs directory
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            lib_path = os.path.join(base_path, "programs/ble_framework/libble.so")

            if not os.path.exists(lib_path):
                # Fallback to local path if not in standard programs dir
                lib_path = "./programs/ble_framework/libble.so"

            cls._lib = ctypes.CDLL(os.path.abspath(lib_path))

            # Setup argument and return types
            cls._lib.ble_create.restype = ctypes.c_void_p
            cls._lib.ble_destroy.argtypes = [ctypes.c_void_p]

            cls._lib.ble_scan.argtypes = [ctypes.c_void_p, ctypes.c_int]

            cls._lib.ble_get_scan_results.argtypes = [ctypes.c_void_p, ctypes.POINTER(BLEDeviceInfo), ctypes.c_int]
            cls._lib.ble_get_scan_results.restype = ctypes.c_int

            cls._lib.ble_connect.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            cls._lib.ble_connect.restype = ctypes.c_bool

            cls._lib.ble_disconnect.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            cls._lib.ble_disconnect.restype = ctypes.c_bool

            cls._lib.ble_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint8), ctypes.c_int, ctypes.c_bool]
            cls._lib.ble_write.restype = ctypes.c_bool

            cls._lib.ble_get_rssi.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            cls._lib.ble_get_rssi.restype = ctypes.c_int

            cls._lib.ble_set_mtu.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
            cls._lib.ble_set_mtu.restype = ctypes.c_bool

            cls._fw = cls._lib.ble_create()
            logger.info("BLE Framework shared library loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load BLE shared library: {e}")

    def scan(self, duration_ms: int = 5000) -> Dict:
        if not self._fw: return {"results": [], "error": "Library not loaded"}
        self._lib.ble_scan(self._fw, duration_ms)

        max_results = 100
        results_array = (BLEDeviceInfo * max_results)()
        count = self._lib.ble_get_scan_results(self._fw, results_array, max_results)

        res = []
        for i in range(count):
            res.append({
                "address": results_array[i].address.decode('utf-8'),
                "name": results_array[i].name.decode('utf-8'),
                "rssi": results_array[i].rssi
            })
        return {"results": res}

    def connect(self, address: str) -> Dict:
        if not self._fw: return {"success": False}
        success = self._lib.ble_connect(self._fw, address.encode('utf-8'))
        return {"success": success}

    def disconnect(self, address: str) -> Dict:
        if not self._fw: return {"success": False}
        success = self._lib.ble_disconnect(self._fw, address.encode('utf-8'))
        return {"success": success}

    def write(self, address: str, service: str, char: str, hex_data: str, fast: bool = False) -> Dict:
        if not self._fw: return {"success": False}

        data_bytes = bytes.fromhex(hex_data)
        data_len = len(data_bytes)
        data_ptr = (ctypes.c_uint8 * data_len).from_buffer_copy(data_bytes)

        success = self._lib.ble_write(
            self._fw,
            address.encode('utf-8'),
            service.encode('utf-8'),
            char.encode('utf-8'),
            data_ptr,
            data_len,
            fast
        )
        return {"success": success}

    def get_rssi(self, address: str) -> Dict:
        if not self._fw: return {"rssi": 0}
        rssi = self._lib.ble_get_rssi(self._fw, address.encode('utf-8'))
        return {"rssi": rssi}

    def set_mtu(self, address: str, mtu: int) -> Dict:
        if not self._fw: return {"success": False}
        success = self._lib.ble_set_mtu(self._fw, address.encode('utf-8'), mtu)
        return {"success": success}

def run(command=None, *args, **kwargs):
    connector = BLEConnector()
    if not command:
        return "Commands: scan, connect, disconnect, write, rssi, mtu"

    try:
        if command == "scan":
            return connector.scan(int(args[0]) if args else 5000)
        elif command == "connect":
            return connector.connect(args[0])
        elif command == "disconnect":
            return connector.disconnect(args[0])
        elif command == "write":
            fast = (args[4] == "fast") if len(args) > 4 else False
            return connector.write(args[0], args[1], args[2], args[3], fast)
        elif command == "rssi":
            return connector.get_rssi(args[0])
        elif command == "mtu":
            return connector.set_mtu(args[0], int(args[1]))
    except Exception as e:
        return {"error": str(e)}

    return f"Unknown command: {command}"
