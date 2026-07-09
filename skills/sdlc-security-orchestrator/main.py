import json
import sys

def handle_request(action, **kwargs):
    if action == "run_pipeline":
        # In a real scenario, this would trigger other skills or CI tools
        return {
            "status": "success",
            "stages": [
                {"name": "SCA", "result": "Pass (0 high vulnerabilities)"},
                {"name": "SAST", "result": "Fail (2 hardcoded secrets found)"},
                {"name": "DAST", "result": "Skipped"}
            ],
            "recommendation": "Fix hardcoded secrets in src/config.py before merging."
        }
    return f"Action {action} not supported."

if __name__ == "__main__":
    line = sys.stdin.readline()
    if line:
        data = json.loads(line)
        res = handle_request(data.get("action"), **data.get("kwargs", {}))
        print(json.dumps({"action": "result", "payload": res}))
