"""
Python Fallback implementations for Butler Hybrid-Link modules.
This module provides pure Python versions of tasks normally handled by C++, Go, or Rust.
"""

import math
import hashlib
import socket
import time
from typing import Dict, Any, List

def factorize(number: int) -> Dict[str, Any]:
    """Python implementation of Prime Factorization."""
    n = number
    factors = []
    # 2s
    while n % 2 == 0:
        factors.append(2)
        n //= 2
    # odds
    for i in range(3, int(math.sqrt(n)) + 1, 2):
        while n % i == 0:
            factors.append(i)
            n //= i
    if n > 2:
        factors.append(n)
    return {"factors": factors, "count": len(factors)}

def fibonacci(n: int) -> Dict[str, Any]:
    """Python implementation of Fibonacci (Iterative)."""
    if n <= 1:
        return {"n": n, "value": n}
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return {"n": n, "value": b}

def check_network(urls: List[str]) -> Dict[str, Any]:
    """Python implementation of concurrent URL checking (using threads)."""
    import requests
    from concurrent.futures import ThreadPoolExecutor

    def check_one(url):
        try:
            start = time.time()
            resp = requests.get(url, timeout=5)
            duration = int((time.time() - start) * 1000)
            return {"url": url, "status": "ok", "code": resp.status_code, "duration": duration}
        except Exception as e:
            return {"url": url, "status": "error", "message": str(e)}

    with ThreadPoolExecutor(max_workers=len(urls) or 1) as executor:
        results = list(executor.map(check_one, urls))

    return {"results": results}

def scan_ports(host: str, start: int, end: int) -> Dict[str, Any]:
    """Python implementation of port scanning."""
    open_ports = []
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            if s.connect_ex((host, port)) == 0:
                open_ports.append(port)
    return {"host": host, "open_ports": open_ports}

def hash_sha256(text: str) -> Dict[str, Any]:
    """Python implementation of SHA256 hashing."""
    h = hashlib.sha256(text.encode()).hexdigest()
    return {"hash": h}

def get_system_info() -> Dict[str, Any]:
    """Python implementation of system info retrieval."""
    import psutil
    import os
    import time
    vm = psutil.virtual_memory()
    return {
        "uptime": int(time.time() - psutil.boot_time()),
        "load_1m": os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0.0,
        "total_mb": vm.total // (1024 * 1024),
        "free_mb": vm.available // (1024 * 1024)
    }

def list_processes() -> Dict[str, Any]:
    """Python implementation of process scanning."""
    import psutil
    processes = []
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = " ".join(proc.info['cmdline'] or [])
            if any(k in cmdline for k in ["butler", "package.", "hybrid_", "sysutil"]):
                processes.append({"pid": proc.info['pid'], "cmd": cmdline})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return {"processes": processes}

def fast_file_search(root: str, pattern: str) -> Dict[str, Any]:
    """Python implementation of file searching."""
    import os
    files = []
    for r, d, f in os.walk(root):
        if any(skip in r for skip in [".git", "/proc", "/sys", "/dev"]):
            continue
        for file in f:
            if pattern in file:
                files.append(os.path.join(r, file))
                if len(files) >= 100:
                    break
        if len(files) >= 100:
            break
    return {"files": files, "count": len(files)}

def dispatch_fallback(method: str, params: Dict[str, Any]) -> Any:
    """Dispatches a BHL call to a Python fallback implementation."""
    if method == "factorize":
        return factorize(int(params.get("number", 0)))
    elif method == "fibonacci":
        return fibonacci(int(params.get("n", 0)))
    elif method == "check_network":
        return check_network(params.get("urls", []))
    elif method == "scan_ports":
        return scan_ports(params.get("host", "127.0.0.1"),
                          int(params.get("start", 1)),
                          int(params.get("end", 1024)))
    elif method == "hash_sha256":
        return hash_sha256(params.get("text", ""))
    elif method == "get_system_info":
        return get_system_info()
    elif method == "list_processes":
        return list_processes()
    elif method == "fast_file_search":
        return fast_file_search(params.get("root", "."), params.get("pattern", ""))
    else:
        return {"error": {"code": -32601, "message": f"Method {method} not supported in fallback"}}
