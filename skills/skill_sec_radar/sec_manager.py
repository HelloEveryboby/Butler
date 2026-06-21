import subprocess
import os

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
    cmd = ["go", "run", "syn_scanner.go", "--target", target]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return f"Scan Report for {target}:\n{result.stdout}"
    except Exception as e:
        return f"Scan failed: {e}"
