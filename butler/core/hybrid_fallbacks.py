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

def benchmark(url: str, count: int, concurrency: int) -> Dict[str, Any]:
    """Python fallback for HTTP benchmark."""
    import requests
    from concurrent.futures import ThreadPoolExecutor
    latencies = []
    def do_req():
        try:
            start = time.time()
            requests.get(url, timeout=10)
            return int((time.time() - start) * 1000)
        except:
            return -1

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(lambda _: do_req(), range(count)))

    latencies = [l for l in results if l != -1]
    if not latencies:
        return {"error": {"message": "All requests failed"}}

    latencies.sort()
    return {
        "total_requests": count,
        "success": len(latencies),
        "min_ms": latencies[0],
        "max_ms": latencies[-1],
        "avg_ms": sum(latencies) // len(latencies),
        "p95_ms": latencies[int(len(latencies) * 0.95)]
    }

def concurrent_download(url: str, path: str, concurrency: int) -> Dict[str, Any]:
    """Python fallback for concurrent download."""
    import requests
    # Simple single-threaded fallback for simplicity in fallback mode
    try:
        resp = requests.get(url, stream=True, timeout=30)
        with open(path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return {"status": "completed", "path": path}
    except Exception as e:
        return {"error": {"message": str(e)}}

def batch_ping(hosts: List[str]) -> List[Dict[str, Any]]:
    """Python fallback for batch ping."""
    results = []
    for h in hosts:
        try:
            start = time.time()
            socket.create_connection((h, 80), timeout=2).close()
            results.append({"host": h, "alive": True, "latency_ms": int((time.time() - start) * 1000)})
        except:
            results.append({"host": h, "alive": False})
    return results

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
    elif method == "benchmark":
        return benchmark(params.get("url", ""), int(params.get("count", 10)), int(params.get("concurrency", 2)))
    elif method == "concurrent_download":
        return concurrent_download(params.get("url", ""), params.get("path", ""), int(params.get("concurrency", 1)))
    elif method == "batch_ping":
        return batch_ping(params.get("hosts", []))
    elif method == "audit":
        return audit_dir(params.get("dir", "."))
    elif method == "log_scan":
        return log_scan(params.get("dir", "."), params.get("regex", ""))
    elif method == "discover_nodes":
        return discover_nodes()
    elif method == "remote_dispatch":
        return remote_dispatch(params.get("ip", ""), params.get("cmd", ""))
    elif method == "get_stats":
        return get_stats_fallback()
    else:
        return {"error": {"code": -32601, "message": f"Method {method} not supported in fallback"}}

def audit_dir(directory: str) -> List[Dict[str, Any]]:
    """Python implementation of directory auditing."""
    import os
    import hashlib
    results = []
    for root, _, files in os.walk(directory):
        for file in files:
            path = os.path.join(root, file)
            try:
                with open(path, "rb") as f:
                    h = hashlib.sha256()
                    while chunk := f.read(8192):
                        h.update(chunk)
                    results.append({"path": path, "hash": h.hexdigest()})
            except Exception as e:
                results.append({"path": path, "error": str(e)})
    return results

def log_scan(directory: str, regex_str: str) -> Dict[str, List[str]]:
    """Python implementation of log scanning."""
    import os
    import re
    results = {}
    try:
        pattern = re.compile(regex_str)
    except:
        return {}

    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in [".log", ".txt", ".go", ".py", ".sh"]):
                path = os.path.join(root, file)
                matches = []
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if pattern.search(line):
                                matches.append(line.strip())
                    if matches:
                        results[path] = matches
                except:
                    continue
    return results

def discover_nodes() -> List[str]:
    """Python implementation of node discovery via UDP broadcast."""
    import socket
    import os
    nodes = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(2)
        s.sendto(b"BUTLER_DISCOVER", ("255.255.255.255", 9999))
        while True:
            data, addr = s.recvfrom(1024)
            nodes.append(f"{addr[0]}:{addr[1]} -> {data.decode()}")
    except socket.timeout:
        pass
    except Exception:
        pass
    return nodes

def remote_dispatch(ip: str, cmd: str) -> Dict[str, str]:
    """Python implementation of remote command dispatch."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.sendto(f"BUTLER_CMD:{cmd}".encode(), (ip, 9999))
        data, _ = s.recvfrom(1024)
        return {"node_response": data.decode()}
    except Exception as e:
        return {"error": str(e)}

def get_stats_fallback() -> Dict[str, Any]:
    """Python implementation of basic stats."""
    import psutil
    import os
    return {
        "workers": os.cpu_count(),
        "goroutines": 0, # Not applicable in Python
        "alloc_mb": psutil.Process().memory_info().rss // (1024 * 1024),
        "sys_mb": psutil.virtual_memory().used // (1024 * 1024),
        "pq_len": 0
    }
