"""
Butler Hybrid-Link Orchestrator (V2: Intelligent Fallback Edition)
This tool demonstrates the power of mixed-language programming with a "Zero-Download" policy.
- Performance: C++ (Fallback: Python)
- Concurrency: Go (Fallback: Python + Threading)
- Data: Java (Fallback: Python)
- Safety: Rust (Fallback: Python)
"""

import os
import sys
import subprocess
import logging
import threading
import uuid
import math
import hashlib
import json
from typing import Dict, Any, List
from urllib import request as urllib_request

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from butler.core.hybrid_link import HybridLinkClient

# --- Python Fallback Implementations (Standard Library Only) ---

def python_factorize(n: int) -> List[int]:
    """Prime factorization (C++ fallback)."""
    factors = []
    d = 2
    temp = n
    while d * d <= temp:
        while temp % d == 0:
            factors.append(d)
            temp //= d
        d += 1
    if temp > 1:
        factors.append(temp)
    return factors

def python_check_network(urls: List[str]) -> List[Dict[str, Any]]:
    """Concurrent URL checking (Go fallback)."""
    results = []
    def check(url):
        try:
            with urllib_request.urlopen(url, timeout=5) as response:
                results.append({"url": url, "status": "ok", "code": response.getcode()})
        except Exception as e:
            results.append({"url": url, "status": "error", "message": str(e)})

    threads = []
    for url in urls:
        t = threading.Thread(target=check, args=(url,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()
    return results

def python_to_xml(key: str, value: str) -> str:
    """Simple data transformation (Java fallback)."""
    return f"<entry><key>{key}</key><value>{value}</value><engine>python-fallback</engine></entry>"

def python_hash_simple(data: str) -> str:
    """Simple integrity check (Rust fallback)."""
    # Using SHA-256 from standard library for reliable safety
    return hashlib.sha256(data.encode()).hexdigest()[:16]

# --- Main Orchestration Logic ---

def run(*args, **kwargs):
    """
    Main entry point for the hybrid orchestrator.
    """
    try:
        from butler.core.extension_manager import extension_manager
        extension_manager.code_execution_manager.scan_and_register()
        mgr = extension_manager.code_execution_manager
    except ImportError:
        mgr = None
        print("[System] Extension manager not available, using pure Python mode.")

    print("--- Butler Hybrid-Link System (Intelligent Fallback) ---")

    results = []
    modules = ["hybrid_compute", "hybrid_net", "hybrid_secure", "hybrid_data"]
    clients = {}

    # Initialize BHL Clients if available
    if mgr:
        for mod in modules:
            info = mgr.get_program(mod)
            if info:
                # Resolve paths and setup client
                if mod == "hybrid_data":
                    clients[mod] = HybridLinkClient("java", cwd=os.path.dirname(info['path']))
                    def java_start(self=clients[mod]):
                        try:
                            self.process = subprocess.Popen(
                                ["java", "Main"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, bufsize=1, cwd=self.cwd, shell=False
                            )
                            self._running = True
                            threading.Thread(target=self._listen_stdout, daemon=True).start()
                            return True
                        except: return False
                    import types
                    clients[mod].start = types.MethodType(java_start, clients[mod])
                else:
                    clients[mod] = HybridLinkClient(info['path'], cwd=os.path.dirname(info['path']))

    # 1. Performance Task (C++ vs Python)
    target_num = 12345678901234567
    client = clients.get("hybrid_compute")
    if client and client.start():
        print(f"[Engine] Using Optimized C++ for factorization...")
        # C++ expects [number]
        res = client.call("factorize", [target_num])
        factors = res.get("result", []) if "result" in res else []
        results.append(f"Math (C++): {factors}")
        client.stop()
    else:
        print(f"[Engine] Environment not found. Falling back to Python for factorization...")
        factors = python_factorize(target_num)
        results.append(f"Math (Python): {factors}")

    # 2. Concurrency Task (Go vs Python)
    urls = ["https://www.python.org", "https://www.github.com"]
    client = clients.get("hybrid_net")
    if client and client.start():
        print(f"[Engine] Using Go Coroutines for network checks...")
        # Go expects [urls]
        res = client.call("check_urls", [urls])
        count = len(res.get("result", [])) if "result" in res else 0
        results.append(f"Network (Go): Checked {count} URLs")
        client.stop()
    else:
        print(f"[Engine] Environment not found. Falling back to Python Threading...")
        net_res = python_check_network(urls)
        results.append(f"Network (Python): Checked {len(net_res)} URLs")

    # 3. Data Task (Java vs Python)
    client = clients.get("hybrid_data")
    if client and client.start():
        print(f"[Engine] Using Java JVM for data logic...")
        # Java expects [key, value]
        res = client.call("to_xml", ["id", "bhl-001"])
        xml = res.get("result") if "result" in res else "Error"
        results.append(f"Data (Java): {xml}")
        client.stop()
    else:
        print(f"[Engine] Environment not found. Falling back to Python String Logic...")
        xml = python_to_xml("id", "bhl-001")
        results.append(f"Data (Python): {xml}")

    # 4. Security Task (Rust vs Python)
    client = clients.get("hybrid_secure")
    report = "BHL-Final-Report"
    if client and client.start():
        print(f"[Engine] Using Rust for memory-safe hashing...")
        # Rust expects [data]
        res = client.call("hash", [report])
        h = res.get("result") if "result" in res else "Error"
        results.append(f"Safety (Rust): Integrity {h}")
        client.stop()
    else:
        print(f"[Engine] Environment not found. Falling back to Python Hashlib...")
        h = python_hash_simple(report)
        results.append(f"Safety (Python): Integrity {h}")

    summary = "\n".join(results)
    return f"Hybrid Execution Result (Status: Complete):\n\n{summary}"

if __name__ == "__main__":
    print(run())
