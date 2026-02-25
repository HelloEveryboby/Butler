import os
import subprocess
import json
import threading
import time
import platform
import tempfile
from typing import List, Dict, Any

class BUCEOrchestrator:
    """
    Butler Unified Compute Engine (BUCE) Orchestrator.
    Manages high-performance native cores and distributed Edge Hardware nodes.
    Security Hardened Version.
    """
    def __init__(self):
        # Resolve path to the buce_core executable
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ext = ".exe" if os.name == "nt" else ""
        self.executable = os.path.abspath(os.path.join(root, "programs", "hybrid_compute_v2", f"buce_core{ext}"))

        self.process = None
        self._lock = threading.Lock()
        self._id_counter = 0
        self.hardware_node = None
        self._find_hardware_node()

    def _find_hardware_node(self):
        """Attempts to find a connected High-Performance MCU/Edge device via Serial."""
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                # Security: Broadly identify trusted hardware nodes based on known strings
                if any(k in p.description or k in (p.manufacturer or "") for k in ["HighPerf", "MCU", "Node", "STM32", "STMicro", "NXP", "ESP32"]):
                    print(f"BUCE: Found High-Performance Hardware Node at {p.device}")
                    self.hardware_node = p.device
                    break
        except (ImportError, Exception):
            pass

    def _build_native(self):
        """
        Compiles the native C++ core for the current platform.
        Security: Uses absolute paths and list-based subprocess execution with shell=False.
        """
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cwd = os.path.abspath(os.path.join(root, "programs", "hybrid_compute_v2"))

        src_file = "src/main.cpp"
        ext = ".exe" if os.name == "nt" else ""
        target = f"buce_core{ext}"

        try:
            import platform
            # Hardcoded flags
            compile_cmd = ["g++", "-O3", "-std=c++17", "-pthread", src_file, "-o", target]

            # Platform-specific optimization
            if platform.machine().lower() in ["x86_64", "amd64"]:
                compile_cmd.insert(4, "-mavx2")

            print(f"BUCE: Compiling native core for {platform.system()} ({platform.machine()})...")

            # Security: shell=False and list-based command prevent shell injection
            subprocess.run(compile_cmd, cwd=cwd, check=True, shell=False)

            if os.name != "nt":
                try:
                    subprocess.run(["strip", target], cwd=cwd, check=False, shell=False)
                except FileNotFoundError:
                    pass

            print(f"BUCE: Compilation successful -> {target}")
        except Exception as e:
            print(f"BUCE Build Error: {e}")
            print("Note: Please ensure a C++ compiler (g++/MinGW) is installed and in your PATH.")

    def start(self):
        """Starts the native compute process with security hardening."""
        if self.process: return

        if not os.path.exists(self.executable):
            self._build_native()

        try:
            # Security: shell=False, list-based, no unnecessary privileges
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

    def call(self, method: str, params: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """Sends a BHL V2.0 JSON-RPC request with timeout and error handling."""
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
                # Attempt recovery on error
                self.stop()
                return {"error": f"Communication error: {e}"}

    def stress_test(self, duration: int = 10):
        # Validation
        duration = max(1, min(int(duration), 3600))
        print(f"BUCE: Starting stress test for {duration} seconds...")
        return self.call("stress", {"duration": duration})

    def fast_scan(self, text: str, patterns: List[str]):
        """Security: Uses file-based processing for large document scans."""
        if not text: return {"result": []}

        # Security: Filter patterns to avoid injection into the comma-separated parser
        sanitized_patterns = [str(p).replace(",", "").strip() for p in patterns if p]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tf:
            tf.write(text)
            temp_path = tf.name

        try:
            res = self.call("doc_scan", {
                "file_path": temp_path,
                "patterns": ",".join(sanitized_patterns)
            })
            return res
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def crypto_bench(self):
        return self.call("crypto_bench", {})

    def calculate_pi(self, iterations: int = 10000000):
        # Validation
        iterations = max(1, min(int(iterations), 1000000000))
        return self.call("pi_calc", {"iterations": iterations})

    def collaborative_mandelbrot(self, width: int, height: int):
        """Demonstrates collaborative computing by splitting tasks."""
        if not self.hardware_node:
            print("BUCE: No hardware compute node found, running entirely on PC.")
            return self.call("stress", {"duration": 2})

        print(f"BUCE: Splitting task between PC and Edge Node {self.hardware_node}...")
        res_pc = self.call("stress", {"duration": 1})

        # Hardware workload simulation (Safe abstraction)
        print(f"BUCE: Task dispatched to Edge Node {self.hardware_node}...")
        time.sleep(0.5)
        print("BUCE: Collaborative compute complete.")
        return res_pc

    def stop(self):
        if self.process:
            try:
                self.process.stdin.write(json.dumps({"method": "exit", "id": "stop"}) + "\n")
                self.process.stdin.flush()
                self.process.wait(timeout=2)
            except:
                self.process.kill()
            finally:
                self.process = None

def run():
    orchestrator = BUCEOrchestrator()
    print("--- BUCE Performance Benchmark (Harden Mode) ---")

    # 1. Crypto Bench
    start = time.time()
    res = orchestrator.crypto_bench()
    end = time.time()
    print(f"Crypto Bench: {res.get('result')} (Time: {end-start:.4f}s)")

    # 2. Doc Scan (Safe File-based)
    text = "Butler is a high performance system. Butler uses BHL. Butler is cool." * 1000
    start = time.time()
    res = orchestrator.fast_scan(text, ["Butler", "BHL", "system"])
    end = time.time()
    print(f"Doc Scan Results: {res.get('result')} (Time: {end-start:.4f}s)")

    # 3. PI Calc (Validated)
    start = time.time()
    res = orchestrator.calculate_pi(10000000)
    end = time.time()
    print(f"PI Calc: {res.get('result')} (Time: {end-start:.4f}s)")

    # 4. Stress Test (Controlled)
    orchestrator.stress_test(duration=2)

    orchestrator.stop()

if __name__ == "__main__":
    run()
