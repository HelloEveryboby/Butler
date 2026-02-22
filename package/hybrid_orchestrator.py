"""
Butler Hybrid-Link Orchestrator
This tool demonstrates the power of mixed-language programming by coordinating:
1. C++ for high-performance math (Prime Factorization).
2. Go for high-concurrency networking (URL Status Checking).
3. Java for complex data transformation (Structured Reports).
4. Rust for high-safety data integrity (Hashing).
5. Python for AI orchestration and result presentation.
"""

import os
import sys
import subprocess
import logging
import threading
from typing import Dict, Any

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from butler.core.hybrid_link import HybridLinkClient

def run(*args, **kwargs):
    """
    Main entry point for the hybrid orchestrator.
    """
    from butler.core.extension_manager import extension_manager
    print("--- Butler Hybrid-Link System Starting ---")

    # 1. Discover and Initialize Clients
    extension_manager.code_execution_manager.scan_and_register()

    # Required Modules
    modules = ["hybrid_compute", "hybrid_net", "hybrid_secure", "hybrid_data"]
    infos = {}
    clients = {}

    for mod in modules:
        info = extension_manager.code_execution_manager.get_program(mod)
        if not info:
            return f"Error: Could not find BHL module '{mod}'. Please ensure it is compiled."
        infos[mod] = info

        # Determine executable path (special handling for Java)
        if mod == "hybrid_data":
            clients[mod] = HybridLinkClient("java", cwd=os.path.dirname(info['path']))
            # Override start to use the specific Main class
            def java_start(self=clients[mod]):
                self.process = subprocess.Popen(
                    ["java", "Main"],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, bufsize=1, cwd=self.cwd, shell=False
                )
                self._running = True
                threading.Thread(target=self._listen_stdout, daemon=True).start()
                threading.Thread(target=self._listen_stderr, daemon=True).start()
                return True
            import types
            clients[mod].start = types.MethodType(java_start, clients[mod])
        else:
            clients[mod] = HybridLinkClient(info['path'], cwd=os.path.dirname(info['path']))

    results = []

    try:
        # Start all modules
        print("[Python] Starting Polyglot Engine (C++, Go, Rust, Java)...")
        for client in clients.values():
            client.start()

        # 2. Performance Task (C++)
        target_number = 12345678901234567
        print(f"[Python -> C++] Requesting factorization of {target_number}...")
        math_result = clients["hybrid_compute"].call("factorize", {"number": target_number})
        if "error" in math_result:
            results.append(f"C++ Error: {math_result['error']['message']}")
        else:
            factors = math_result.get("factors", [])
            results.append(f"C++ Result: Factors of {target_number} are {factors}")

        # 3. Concurrency Task (Go)
        urls = ["https://www.python.org", "https://www.github.com", "https://www.rust-lang.org"]
        print(f"[Python -> Go] Requesting concurrent check of {len(urls)} URLs...")
        net_result = clients["hybrid_net"].call("check_network", {"urls": urls})
        if "error" in net_result:
            results.append(f"Go Error: {net_result['error']['message']}")
        else:
            results.append(f"Go Result: Checked {len(net_result.get('results', []))} URLs.")

        # 4. Data Transformation (Java)
        print("[Python -> Java] Requesting data transformation to XML...")
        data_result = clients["hybrid_data"].call("to_xml_simple", {"key": "status", "value": "Polyglot OK"})
        if "error" in data_result:
            results.append(f"Java Error: {data_result['error']['message']}")
        else:
            results.append(f"Java Result: XML created -> {data_result.get('xml')}")

        # 5. Security/Integrity (Rust)
        report = f"Full Status: C++={math_result.get('count')}, Java={data_result.get('xml')}"
        print("[Python -> Rust] Requesting high-speed integrity hash...")
        secure_result = clients["hybrid_secure"].call("hash_simple", {"data": report})
        if "error" in secure_result:
            results.append(f"Rust Error: {secure_result['error']['message']}")
        else:
            results.append(f"Rust Result: Integrity Hash -> {secure_result.get('hash')}")

    except Exception as e:
        return f"Orchestration Error: {e}"
    finally:
        print("[Python] Stopping polyglot modules...")
        for client in clients.values():
            client.stop()

    summary = "\n".join(results)
    return f"Hybrid System Execution Complete:\n\n{summary}"

if __name__ == "__main__":
    # For local testing
    print(run())
