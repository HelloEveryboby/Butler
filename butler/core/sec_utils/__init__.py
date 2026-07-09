import os
import subprocess
import json
import logging
import datetime
import base64

logger = logging.getLogger("SecUtils")

class SecUtils:
    @staticmethod
    def check_dependency(tool_name):
        """Check if tool exists in PATH."""
        try:
            # Use 'which' on Linux/macOS and 'where' on Windows
            cmd = ["where"] if os.name == 'nt' else ["which"]
            cmd.append(tool_name)
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def get_proxy_env(proxy_url=None):
        """Get environment variables for proxy."""
        if not proxy_url:
            return {}
        return {
            "HTTP_PROXY": proxy_url,
            "HTTPS_PROXY": proxy_url,
            "http_proxy": proxy_url,
            "https_proxy": proxy_url
        }

    @staticmethod
    def run_safe_command(cmd, env=None, timeout=300):
        """Execute command safely with timeout and env injection."""
        try:
            # Merge with existing environment
            full_env = os.environ.copy()
            if env:
                full_env.update(env)

            result = subprocess.run(
                cmd,
                env=full_env,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False # Avoid shell injection
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def decode_jwt_part(part):
        """Helper to decode JWT base64 parts."""
        try:
            # Add padding if needed
            padding = '=' * (4 - len(part) % 4)
            return base64.b64decode(part + padding).decode('utf-8')
        except Exception:
            return part

    @staticmethod
    def generate_markdown_report(title, findings, business_impact, recommendations):
        """Generate structured Markdown report."""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report = f"# {title}\n\n"
        report += f"**Time**: {now}\n\n"

        report += "## 1. Findings\n"
        for finding in findings:
            report += f"### {finding['name']}\n"
            report += f"- **Severity**: {finding['severity']}\n"
            report += f"- **Description**: {finding['description']}\n"
            if finding.get('evidence'):
                report += f"- **Evidence**: `{finding['evidence']}`\n"
            report += "\n"

        report += "## 2. Business Impact\n"
        report += f"{business_impact}\n\n"

        report += "## 3. Recommendations\n"
        for rec in recommendations:
            report += f"- {rec}\n"

        return report
