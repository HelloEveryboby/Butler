import json
import sys
import os

# Adjust path to import modules and butler core
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.recon import ReconModule
from modules.scanner import ScannerModule
from modules.checklist import ChecklistModule

def handle_request(action, **kwargs):
    config = kwargs.get("config", {})
    proxy = kwargs.get("proxy") or config.get("proxy")

    recon = ReconModule(proxy=proxy)
    scanner = ScannerModule(proxy=proxy)
    checklist = ChecklistModule()

    if action == "run" or action == "test":
        target = kwargs.get("target")
        if not target:
            return "Please provide a target URL or IP."

        mode = kwargs.get("mode", "full")

        results = {}
        if mode in ["recon", "full"]:
            results["recon"] = recon.run_nmap(target)

        if mode in ["scan", "full"]:
            results["scan"] = scanner.run_nuclei(target)

        return format_output(results)

    elif action == "checklist":
        scenario = kwargs.get("scenario", "general web app")
        items = checklist.generate_business_checklist(scenario)
        return "\n".join([f"- [ ] {item}" for item in items])

    return f"Action {action} not supported by WebSecurityTester."

def format_output(results):
    report = "## Web Security Test Results\n\n"
    for part, res in results.items():
        report += f"### {part.capitalize()}\n"
        if isinstance(res, dict):
            if res.get("success"):
                report += f"```\n{res['stdout'][:1000]}...\n```\n"
            else:
                report += f"Error: {res.get('error') or res.get('stderr')}\n"
        else:
            report += f"{res}\n"
    return report

if __name__ == "__main__":
    line = sys.stdin.readline()
    if line:
        try:
            data = json.loads(line)
            res = handle_request(data.get("action"), **data.get("kwargs", {}))
            print(json.dumps({"action": "result", "payload": res}))
        except Exception as e:
            print(json.dumps({"action": "result", "payload": f"Error: {str(e)}"}))
