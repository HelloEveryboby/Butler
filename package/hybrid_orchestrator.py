"""
Butler Hybrid-Link Orchestrator
This tool demonstrates the power of mixed-language programming by coordinating:
1. C++ for high-performance math (Prime Factorization).
2. Go for high-concurrency networking (URL Status Checking).
3. Python for AI orchestration and result presentation.
"""

import os
import sys
import logging
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

    # 1. Initialize Clients
    # We find the executables via CodeExecutionManager (via ExtensionManager)
    compute_info = extension_manager.code_execution_manager.get_program("hybrid_compute")
    net_info = extension_manager.code_execution_manager.get_program("hybrid_net")

    if not compute_info or not net_info:
        # Try to scan again if not found
        extension_manager.code_execution_manager.scan_and_register()
        compute_info = extension_manager.code_execution_manager.get_program("hybrid_compute")
        net_info = extension_manager.code_execution_manager.get_program("hybrid_net")

    if not compute_info or not net_info:
        return "Error: Could not find BHL modules. Please ensure they are compiled."

    compute_client = HybridLinkClient(compute_info['path'], cwd=os.path.dirname(compute_info['path']))
    net_client = HybridLinkClient(net_info['path'], cwd=os.path.dirname(net_info['path']))

    results = []

    try:
        # Start modules
        print("[Python] Starting C++ and Go modules...")
        compute_client.start()
        net_client.start()

        # 2. Performance Task (C++)
        target_number = 12345678901234567
        print(f"[Python -> C++] Requesting factorization of {target_number}...")
        math_result = compute_client.call("factorize", {"number": target_number})
        if "error" in math_result:
            results.append(f"C++ Error: {math_result['error']['message']}")
        else:
            factors = math_result.get("factors", [])
            results.append(f"C++ Result: Factors of {target_number} are {factors}")

        # 3. Concurrency Task (Go)
        urls = [
            "https://www.google.com",
            "https://www.github.com",
            "https://www.python.org",
            "https://www.golang.org",
            "https://www.cppreference.com"
        ]
        print(f"[Python -> Go] Requesting concurrent check of {len(urls)} URLs...")
        net_result = net_client.call("check_network", {"urls": urls})
        if "error" in net_result:
            results.append(f"Go Error: {net_result['error']['message']}")
        else:
            status_list = net_result.get("results", [])
            results.append(f"Go Result: Checked {len(status_list)} URLs concurrently.")
            for r in status_list:
                results.append(f"  - {r['url']}: {r['status']} ({r.get('code', 'N/A')})")

    except Exception as e:
        return f"Orchestration Error: {e}"
    finally:
        print("[Python] Stopping modules...")
        compute_client.stop()
        net_client.stop()

    summary = "\n".join(results)
    return f"Hybrid System Execution Complete:\n\n{summary}"

if __name__ == "__main__":
    # For local testing
    print(run())
