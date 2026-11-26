import os
import subprocess


def handle_request(action, **kwargs):
    if action == "run" or action == "scan":
        target = kwargs.get("target", "127.0.0.1")
        return start_scan(target)
    return f"Action {action} not supported."

def start_scan(target):
    # Determine binary path
    bin_path = "./bin/skill_sec_radar"
    if os.name == 'nt': bin_path += ".exe"

    # In this template, we just call the go run if bin doesn't exist for dev
    scanner = os.path.join(os.path.dirname(os.path.abspath(__file__)), "syn_scanner.go")
    cmd = ["go", "run", scanner, "--target", target]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return f"Scan Report for {target}:\n{result.stdout}"
    except Exception as e:
        return f"Scan failed: {e}"
