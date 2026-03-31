import os
import subprocess
import sys
import json
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)


def run(file_path: str, timeout: int = 60):
    """
    Recalculates formulas in an Excel file using the relocated expert script.

    Args:
        file_path (str): Path to the Excel file.
        timeout (int): Timeout in seconds for the recalculation.

    Returns:
        dict: The result of the recalculation process.
    """
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    # Resolve the path to the recalc.py script in its new location
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    recalc_script = os.path.join(
        project_root, "package", "document", "xlsx_expert", "scripts", "recalc.py"
    )

    if not os.path.exists(recalc_script):
        return {
            "status": "error",
            "message": f"Recalculation script not found at {recalc_script}",
        }

    logger.info(f"Recalculating formulas for: {file_path}")

    try:
        # Run the script and capture its output
        result = subprocess.run(
            [sys.executable, recalc_script, file_path, str(timeout)],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(recalc_script),
        )

        # The script is expected to output JSON
        try:
            output_json = json.loads(result.stdout)
            if result.returncode != 0:
                output_json["status"] = "error"
                output_json["stderr"] = result.stderr
            return output_json
        except json.JSONDecodeError:
            if result.returncode == 0:
                return {"status": "success", "raw_output": result.stdout}
            else:
                return {
                    "status": "error",
                    "message": "Failed to parse recalculation output",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }

    except Exception as e:
        logger.error(f"Error during Excel recalculation: {e}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(run(sys.argv[1]))
    else:
        print("Usage: python xlsx_recalc_tool.py <file_path>")
