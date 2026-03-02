import os
import subprocess
import json
import re
from typing import List, Dict, Any, Optional
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class SystematicDebuggingTool:
    def __init__(self, project_root: str = "."):
        self.project_root = os.path.abspath(project_root)

    def analyze_recent_changes(self, days: int = 1) -> List[Dict[str, Any]]:
        """Checks git commits in the last N days."""
        try:
            cmd = ["git", "log", f"--since={days} day ago", "--name-status", "--pretty=format:%h - %an, %ar : %s"]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
            if result.returncode != 0:
                return []

            commits = []
            current_commit = None
            for line in result.stdout.splitlines():
                if line.strip() == "":
                    continue
                if " - " in line and " : " in line:
                    if current_commit:
                        commits.append(current_commit)
                    current_commit = {"info": line, "files": []}
                elif current_commit:
                    current_commit["files"].append(line.strip())

            if current_commit:
                commits.append(current_commit)

            return commits
        except Exception as e:
            logger.error(f"Error analyzing git changes: {e}")
            return []

    def scan_logs(self, log_dir: str = "logs", max_entries: int = 10) -> List[Dict[str, Any]]:
        """Scans the logs directory for ERROR and CRITICAL entries line by line."""
        errors = []
        full_log_dir = os.path.join(self.project_root, log_dir)
        if not os.path.exists(full_log_dir):
            return []

        # Sort files to check newest first if possible
        files = sorted(os.listdir(full_log_dir), reverse=True)
        for filename in files:
            if filename.endswith(".log") or filename.endswith(".json"):
                file_path = os.path.join(full_log_dir, filename)
                try:
                    # Use a buffered approach for efficiency and memory safety
                    with open(file_path, "r", encoding="utf-8") as f:
                        if filename.endswith(".json"):
                            # Read from end of file would be better, but line by line is safer than read()
                            # To keep it simple but safer, we limit the number of entries we collect
                            lines = f.readlines()
                            for line in reversed(lines):
                                try:
                                    entry = json.loads(line)
                                    if entry.get("level") in ["ERROR", "CRITICAL"]:
                                        errors.append(entry)
                                        if len(errors) >= max_entries:
                                            break
                                except json.JSONDecodeError:
                                    continue
                        else:
                            # Standard log format scanning line by line
                            lines = f.readlines()
                            current_error = []
                            for line in reversed(lines):
                                if "ERROR" in line or "CRITICAL" in line:
                                    errors.append({"raw": line.strip()})
                                    if len(errors) >= max_entries:
                                        break

                except Exception as e:
                    logger.error(f"Error reading log file {filename}: {e}")

            if len(errors) >= max_entries:
                break

        return errors

    def generate_investigation_checklist(self, error_context: str = "") -> str:
        """Generates a Phase 1 checklist based on the systematic debugging skill."""
        checklist = """
### 🔍 Systematic Debugging: Phase 1 Checklist

**1. Read Error Messages Carefully**
- [ ] Have you read the FULL stack trace?
- [ ] What is the EXACT error message and code?
- [ ] Which file and line number is the origin?

**2. Reproduce Consistently**
- [ ] Can you trigger this reliably? (Steps: ________________)
- [ ] Does it happen in every environment?
- [ ] If intermittent, what are the common factors?

**3. Check Recent Changes**
- [ ] What changed recently in this area? (Code, Config, Deps)
- [ ] Have you checked the git diff?

**4. Trace Data Flow**
- [ ] What data is entering the failing component?
- [ ] Where does the "bad" value first appear?
- [ ] Are all component boundaries logging inputs/outputs?

**Current Context Analysis:**
"""
        if error_context:
            checklist += f"\n> {error_context}\n"

        return checklist

    def run_analysis(self, error_message: Optional[str] = None) -> Dict[str, Any]:
        """Main entry point for debugging analysis."""
        recent_commits = self.analyze_recent_changes()
        recent_errors = self.scan_logs()

        report = {
            "status": "success",
            "recent_changes": recent_commits,
            "recent_errors": recent_errors,
            "checklist": self.generate_investigation_checklist(error_message)
        }
        return report

def run(error_message: str = None):
    tool = SystematicDebuggingTool()
    return tool.run_analysis(error_message)

if __name__ == "__main__":
    import sys
    err = sys.argv[1] if len(sys.argv) > 1 else None
    print(json.dumps(run(err), indent=2, ensure_ascii=False))
