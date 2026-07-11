import json
import sys

def handle_request(action, **kwargs):
    if action == "checklist":
        platform = kwargs.get("platform", "android").lower()
        if platform == "android":
            return [
                "Check for android:debuggable=true in Manifest",
                "Verify deep link vulnerabilities",
                "Check for cleartext traffic permission",
                "Test local storage for sensitive data (SharedPreferences, SQLite)"
            ]
        else:
            return [
                "Verify ATS (App Transport Security) configuration",
                "Check for sensitive data in Keychain vs NSUserDefaults",
                "Test for Jailbreak detection mechanisms",
                "Check for hardcoded secrets in Binary"
            ]
    return f"Action {action} not supported."

if __name__ == "__main__":
    line = sys.stdin.readline()
    if line:
        data = json.loads(line)
        res = handle_request(data.get("action"), **data.get("kwargs", {}))
        print(json.dumps({"action": "result", "payload": res}))
