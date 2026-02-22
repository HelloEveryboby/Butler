"""
Butler Hybrid-Link Orchestrator (Enhanced)
This tool demonstrates the power of multi-language collaboration:
1. C++ for high-performance math (Prime Factorization & Fibonacci).
2. Go for concurrent networking (URL Checking & Port Scanning).
3. Rust for memory-safe high-speed crypto (SHA256 Hashing).
4. Python for orchestration and event handling.
"""

import os
import sys
import time
import traceback
from typing import Dict, Any

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from butler.core.hybrid_link import HybridLinkClient

def on_bhl_event(event: Dict[str, Any]):
    """Callback for BHL events."""
    method = event.get("method")
    params = event.get("params")
    print(f"!!! [Event Received] Method: {method}, Data: {params}")

def run(*args, **kwargs):
    """
    Main entry point for the hybrid orchestrator.
    """
    from butler.core.extension_manager import extension_manager
    print("\n" + "="*50)
    print("      Butler Hybrid-Link System (V2.0)")
    print("="*50)

    # 1. Initialize Clients
    extension_manager.code_execution_manager.scan_and_register()

    compute_info = extension_manager.code_execution_manager.get_program("hybrid_compute")
    net_info = extension_manager.code_execution_manager.get_program("hybrid_net")
    crypto_info = extension_manager.code_execution_manager.get_program("hybrid_crypto")

    if not all([compute_info, net_info, crypto_info]):
        missing = []
        if not compute_info: missing.append("C++ (hybrid_compute)")
        if not net_info: missing.append("Go (hybrid_net)")
        if not crypto_info: missing.append("Rust (hybrid_crypto)")
        return f"Error: Missing BHL modules: {', '.join(missing)}. Please compile them."

    results = []

    # Using the new Context Manager for automatic cleanup
    try:
        with HybridLinkClient(compute_info['path'], cwd=os.path.dirname(compute_info['path'])) as compute_client, \
             HybridLinkClient(net_info['path'], cwd=os.path.dirname(net_info['path'])) as net_client, \
             HybridLinkClient(crypto_info['path'], cwd=os.path.dirname(crypto_info['path'])) as crypto_client:

            # Register event callback for Go module
            net_client.register_event_callback(on_bhl_event)

            print("[Python] All modules started successfully.")

            # --- 1. Rust Task: Hashing ---
            secret_msg = "Butler is the best AI assistant!"
            print(f"[Python -> Rust] Hashing message: '{secret_msg}'")
            rust_result = crypto_client.call("hash_sha256", {"text": secret_msg})
            if "error" in rust_result:
                results.append(f"Rust Error: {rust_result['error']['message']}")
            else:
                results.append(f"Rust Result: SHA256 of '{secret_msg}' is {rust_result['hash'][:16]}...")

            # --- 2. C++ Task: Heavy Math ---
            n_fib = 40
            print(f"[Python -> C++] Calculating Fibonacci({n_fib})...")
            math_result = compute_client.call("fibonacci", {"n": n_fib})
            if "error" in math_result:
                results.append(f"C++ Error: {math_result['error']['message']}")
            else:
                results.append(f"C++ Result: Fibonacci({n_fib}) = {math_result['value']}")

            # --- 3. Go Task: Network Scan (with Events) ---
            target_host = "127.0.0.1"
            print(f"[Python -> Go] Scanning common ports on {target_host}...")
            # We'll scan a small range for speed in demo
            net_result = net_client.call("scan_ports", {"host": target_host, "start": 20, "end": 1024}, timeout=15)
            if "error" in net_result:
                results.append(f"Go Error: {net_result['error']['message']}")
            else:
                open_ports = net_result.get("open_ports", [])
                results.append(f"Go Result: Found {len(open_ports)} open ports on {target_host}: {open_ports}")

    except Exception as e:
        return f"Orchestration Error: {e}\n{traceback.format_exc()}"

    summary = "\n".join(results)
    return f"\n--- Hybrid System Execution Summary ---\n{summary}\n"

if __name__ == "__main__":
    # For local testing
    print(run())
