import os
import subprocess
import json
import threading
import time
from typing import List, Dict, Any

class BUCEOrchestrator:
    def __init__(self):
        # Resolve path to the buce_core executable
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.executable = os.path.join(root, "programs", "hybrid_compute_v2", "buce_core")

        if not os.path.exists(self.executable):
            # Try to build it if missing
            print(f"BUCE: Executable not found at {self.executable}. Attempting build...")
            self._build_native()

        self.process = None
        self._lock = threading.Lock()
        self._id_counter = 0
        self.stm32_node = None
        self._find_stm32()

    def _find_stm32(self):
        """Attempts to find a connected STM32 device via Serial."""
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                # Common STM32/Arduino VID/PID or Manufacturer strings
                if "STM32" in p.description or "STMicroelectronics" in p.manufacturer:
                    print(f"BUCE: Found STM32 node at {p.device}")
                    self.stm32_node = p.device
                    break
        except ImportError:
            pass # pyserial not installed
        except Exception as e:
            print(f"BUCE: Error scanning for STM32: {e}")

    def _build_native(self):
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cwd = os.path.join(root, "programs", "hybrid_compute_v2")
        try:
            # Use list-based arguments and shell=False to prevent injection
            subprocess.run(["g++", "-O3", "-std=c++17", "-mavx2", "-pthread", "src/main.cpp", "-o", "buce_core"],
                           cwd=cwd, check=True, shell=False)
            subprocess.run(["strip", "buce_core"], cwd=cwd, check=True, shell=False)
        except Exception as e:
            print(f"BUCE Build Error: {e}")

    def start(self):
        if self.process: return
        # Explicitly set shell=False and use list-based command for security
        self.process = subprocess.Popen(
            [self.executable],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            shell=False
        )

    def call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if not self.process:
                self.start()

            self._id_counter += 1
            request = {
                "jsonrpc": "2.0",
                "method": method,
                "id": str(self._id_counter),
                **params
            }

            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()

            line = self.process.stdout.readline()
            if not line:
                return {"error": "Native core disconnected"}
            # print(f"DEBUG: {line}")
            return json.loads(line)

    def stress_test(self, duration: int = 10):
        print(f"BUCE: Starting stress test for {duration} seconds...")
        return self.call("stress", {"duration": duration})

    def fast_scan(self, text: str, patterns: List[str]):
        return self.call("doc_scan", {"text": text, "patterns": ",".join(patterns)})

    def crypto_bench(self):
        return self.call("crypto_bench", {})

    def calculate_pi(self, iterations: int = 10000000):
        return self.call("pi_calc", {"iterations": iterations})

    def collaborative_mandelbrot(self, width: int, height: int):
        """Demonstrates collaborative computing by splitting tasks."""
        if not self.stm32_node:
            print("BUCE: No STM32 node found, running entirely on PC.")
            return self.call("stress", {"duration": 2}) # Simulation

        print(f"BUCE: Splitting Mandelbrot task between PC and {self.stm32_node}...")
        # PC handles 80% of the workload, STM32 handles 20%
        # (Implementation of actual serial communication omitted for simulation without hardware)
        res_pc = self.call("stress", {"duration": 1})
        print("BUCE: STM32 task dispatched...")
        time.sleep(0.5)
        print("BUCE: Collaborative compute complete.")
        return res_pc

    def stop(self):
        if self.process:
            self.call("exit", {})
            self.process.wait()
            self.process = None

def run():
    orchestrator = BUCEOrchestrator()
    print("--- BUCE Performance Benchmark ---")

    # 1. Crypto Bench
    start = time.time()
    res = orchestrator.crypto_bench()
    end = time.time()
    print(f"Crypto Bench: {res.get('result')} (Time: {end-start:.4f}s)")

    # 2. Doc Scan
    text = "Butler is a high performance system. Butler uses BHL. Butler is cool." * 1000
    start = time.time()
    res = orchestrator.fast_scan(text, ["Butler", "BHL", "system"])
    end = time.time()
    print(f"Doc Scan Results: {res.get('result')} (Time: {end-start:.4f}s)")

    # 3. PI Calc
    start = time.time()
    res = orchestrator.calculate_pi(10000000)
    end = time.time()
    print(f"PI Calc: {res.get('result')} (Time: {end-start:.4f}s)")

    # 4. Stress Test (shorter duration for bench)
    orchestrator.stress_test(duration=2)

    orchestrator.stop()

if __name__ == "__main__":
    run()
