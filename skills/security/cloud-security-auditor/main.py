import json
import sys
from butler.core.sec_utils import SecUtils

def handle_request(action, **kwargs):
    if action == "scan_image":
        image = kwargs.get("image")
        if not image: return "Error: Image name required."
        if SecUtils.check_dependency("trivy"):
            cmd = ["trivy", "image", "--severity", "HIGH,CRITICAL", image]
            return SecUtils.run_safe_command(cmd)
        return "Trivy not installed."

    if action == "audit_k8s":
        if SecUtils.check_dependency("trivy"):
            cmd = ["trivy", "k8s", "cluster", "--report", "summary"]
            return SecUtils.run_safe_command(cmd)
        return "Trivy not installed."

    return f"Action {action} not supported."

if __name__ == "__main__":
    line = sys.stdin.readline()
    if line:
        data = json.loads(line)
        res = handle_request(data.get("action"), **data.get("kwargs", {}))
        print(json.dumps({"action": "result", "payload": res}))
