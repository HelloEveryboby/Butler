import os
import subprocess
import sys
import json
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

def handle_request(action, **kwargs):
    """
    Recalculates formulas in an Excel file using the relocated expert script.
    """
    entities = kwargs.get("entities", {})
    file_path = entities.get("file_path") or entities.get("path")
    timeout = 60

    if not file_path:
        return "请提供要重新计算的 Excel 文件路径。"

    if not os.path.exists(file_path):
        return f"错误：未找到文件 {file_path}"

    # Resolve the path to the recalc.py script in its new location
    # Since skills/ is in root, project_root is '.'
    project_root = os.getcwd()
    recalc_script = os.path.join(project_root, "package", "document", "xlsx_expert", "scripts", "recalc.py")

    if not os.path.exists(recalc_script):
        return f"错误：未在 {recalc_script} 找到重计算脚本"

    logger.info(f"正在为 {file_path} 重新计算公式...")

    try:
        # Run the script and capture its output
        result = subprocess.run(
            [sys.executable, recalc_script, file_path, str(timeout)],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(recalc_script)
        )

        # The script is expected to output JSON
        try:
            output_json = json.loads(result.stdout)
            if result.returncode != 0:
                return f"重计算失败: {output_json.get('message', result.stderr)}"
            return f"✅ Excel 重计算成功！详情: {output_json.get('message', '完成')}"
        except json.JSONDecodeError:
            if result.returncode == 0:
                return "✅ Excel 重计算成功！"
            else:
                return f"❌ 重计算失败：{result.stderr or result.stdout}"

    except Exception as e:
        logger.error(f"Error during Excel recalculation: {e}")
        return f"发生异常: {str(e)}"
