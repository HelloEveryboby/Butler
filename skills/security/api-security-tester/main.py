import json
import sys
from butler.core.sec_utils import SecUtils

def handle_request(action, **kwargs):
    target = kwargs.get("target")

    if action == "check_jwt":
        token = kwargs.get("token")
        if not token: return "Error: No JWT provided."
        parts = token.split('.')
        if len(parts) != 3: return "Invalid JWT format."

        header = SecUtils.decode_jwt_part(parts[0])
        payload = SecUtils.decode_jwt_part(parts[1])

        return {
            "header": json.loads(header) if '{' in header else header,
            "payload": json.loads(payload) if '{' in payload else payload
        }

    if action == "scan_api":
        if not target: return "Error: Target URL required."
        if SecUtils.check_dependency("nuclei"):
            cmd = ["nuclei", "-u", target, "-t", "headless/api", "-t", "vulnerabilities/generic/api-keys.yaml"]
            return SecUtils.run_safe_command(cmd)
        return "Nuclei not installed for API scanning."

    return f"Action {action} not supported."

if __name__ == "__main__":
    line = sys.stdin.readline()
    if line:
        try:
            data = json.loads(line)
            res = handle_request(data.get("action"), **data.get("kwargs", {}))
            print(json.dumps({"action": "result", "payload": res}))
        except Exception as e:
            print(json.dumps({"action": "result", "payload": str(e)}))
