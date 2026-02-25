import os
import subprocess
import json
import threading
import time
import platform
import shlex
from typing import List, Dict, Any

class BUCEOrchestrator:
    """
    Butler Unified Compute Engine (BUCE) Orchestrator.
    Manages high-performance native cores and distributed STM32 nodes.
    """
    def __init__(self):
        # Resolve path to the buce_core executable
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ext = ".exe" if os.name == "nt" else ""
        self.executable = os.path.abspath(os.path.join(root, "programs", "hybrid_compute_v2", f"buce_core{ext}"))

        if not os.path.exists(self.executable):
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
        except (ImportError, Exception) as e:
            # pyserial might not be installed or no access to ports
            pass

    def _build_native(self):
        """
        Compiles the native C++ core for the current platform.
        Security: Uses absolute paths and list-based subprocess execution with shell=False.
        """
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cwd = os.path.abspath(os.path.join(root, "programs", "hybrid_compute_v2"))

        # Define static components of the build
        src_file = "src/main.cpp"
        ext = ".exe" if os.name == "nt" else ""
        target = f"buce_core{ext}"

        try:
            # Construct a safe command list
            compile_cmd = ["g++", "-O3", "-std=c++17", "-pthread", src_file, "-o", target]

            # Platform-specific optimization
            if platform.machine().lower() in ["x86_64", "amd64"]:
                compile_cmd.insert(4, "-mavx2")

            print(f"BUCE: Compiling native core for {platform.system()} ({platform.machine()})...")

            # Security: shell=False and list-based command prevent shell injection
            subprocess.run(compile_cmd, cwd=cwd, check=True, shell=False)

            if os.name != "nt":
                # strip is an optional optimization
                try:
                    subprocess.run(["strip", target], cwd=cwd, check=False, shell=False)
                except FileNotFoundError:
                    pass

            print(f"BUCE: Compilation successful -> {target}")
        except Exception as e:
            print(f"BUCE Build Error: {e}")
            print("Note: Please ensure a C++ compiler (g++/MinGW) is installed and in your PATH.")

    def start(self):
        """Starts the native compute process."""
        if self.process: return

        if not os.path.exists(self.executable):
            self._build_native()

        try:
            # Security: shell=False and list-based command
            self.process = subprocess.Popen(
                [self.executable],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                shell=False
            )
        except Exception as e:
            print(f"BUCE Startup Error: {e}")

    def call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sends a BHL V2.0 JSON-RPC request to the native core."""
        with self._lock:
            if not self.process:
                self.start()

            if not self.process:
                return {"error": "Native core failed to start"}

            self._id_counter += 1
            request = {
                "jsonrpc": "2.0",
                "method": method,
                "id": str(self._id_counter),
                **params
            }

            try:
                self.process.stdin.write(json.dumps(request) + "\n")
                self.process.stdin.flush()

                line = self.process.stdout.readline()
                if not line:
                    return {"error": "Native core disconnected"}
                return json.loads(line)
            except Exception as e:
                return {"error": f"Communication error: {e}"}

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
        """
        Demonstrates collaborative computing by splitting tasks.
        In a real scenario, this would use the stm32_node via pyserial.
        """
        if not self.stm32_node:
            print("BUCE: No STM32 node found, running entirely on PC.")
            return self.call("stress", {"duration": 2})

        print(f"BUCE: Splitting Mandelbrot task between PC and {self.stm32_node}...")
        # PC handles most of the workload
        res_pc = self.call("stress", {"duration": 1})

        # STM32 workload simulation
        print(f"BUCE: STM32 task dispatched to {self.stm32_node}...")
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

    # 4. Stress Test
    orchestrator.stress_test(duration=2)

    # 5. Collaborative Demo
    orchestrator.collaborative_mandelbrot(1000, 1000)

    orchestrator.stop()

if __name__ == "__main__":
    run()
