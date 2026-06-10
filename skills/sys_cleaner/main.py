import os
import json
import subprocess
import sys
import platform
import logging

logger = logging.getLogger("SysCleaner")

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
# Binary name depends on platform
BINARY_NAME = "cleaner_core.exe" if platform.system() == "Windows" else "cleaner_core"
CORE_EXE = os.path.join(SKILL_DIR, "core", BINARY_NAME)
BEFORE_JSON = os.path.join(SKILL_DIR, "before.json")
AFTER_JSON = os.path.join(SKILL_DIR, "after.json")
LOG_BLG = os.path.join(SKILL_DIR, "changes.blg")

def start_track(kwargs):
    """ 步骤 1：捕获安装前的低权限无害快照 """
    if os.path.exists(BEFORE_JSON): os.remove(BEFORE_JSON)

    logger.info(f"Starting track, executing: {CORE_EXE}")
    try:
        subprocess.run([CORE_EXE, "-mode", "scan", "-out", BEFORE_JSON], check=True)
        return {"status": "tracking_started"}
    except Exception as e:
        logger.error(f"Failed to start track: {e}")
        return {"status": "error", "message": str(e)}

def stop_track(kwargs):
    """ 步骤 2：捕获安装后快照并生成差异 Diff 矩阵 """
    if os.path.exists(AFTER_JSON): os.remove(AFTER_JSON)

    logger.info(f"Stopping track, executing: {CORE_EXE}")
    try:
        subprocess.run([CORE_EXE, "-mode", "scan", "-out", AFTER_JSON], check=True)

        # Diff engine logic
        if not os.path.exists(BEFORE_JSON) or not os.path.exists(AFTER_JSON):
            return {"status": "error", "message": "Snapshot files missing"}

        with open(BEFORE_JSON, 'r') as f: before = json.load(f)
        with open(AFTER_JSON, 'r') as f: after = json.load(f)

        reg_added = list(set(after.get("registry_keys", [])) - set(before.get("registry_keys", [])))
        file_added = list(set(after.get("files", [])) - set(before.get("files", [])))

        blg_data = {"reg_added": reg_added, "file_added": file_added}
        with open(LOG_BLG, 'w') as f: json.dump(blg_data, f, indent=4)

        return {
            "reg_added": len(reg_added),
            "file_added": len(file_added)
        }
    except Exception as e:
        logger.error(f"Failed to stop track: {e}")
        return {"status": "error", "message": str(e)}

def setup_elevation(kwargs):
    """ 一键设置免提权运行环境 (需要一次性授权) """
    system = platform.system()
    try:
        if system == "Windows":
            task_name = "ButlerSysCleaner"
            # 创建计划任务：使用最高权限运行，且不需要 UAC 确认
            cmd = f'schtasks /create /tn "{task_name}" /tr "\"{CORE_EXE}\" -mode delete -out \"{LOG_BLG}\"" /sc once /st 00:00 /rl highest /f'
            import ctypes
            # 使用 ShellExecuteW 触发一次 UAC 弹窗来创建任务
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f"/c {cmd}", None, 0)
            if int(ret) <= 32:
                return {"message": "❌ 设置失败：需要管理员权限来配置静默清理。"}
            return {"message": "✅ 静默提权已配置！今后清理将不再弹出 UAC。"}

        elif system == "Linux":
            # 创建 sudoers 免密配置
            sudoer_file = "/etc/sudoers.d/butler-syscleaner"
            line = f"{os.getlogin()} ALL=(ALL) NOPASSWD: {CORE_EXE}\n"
            cmd = f'echo "{line}" | sudo tee {sudoer_file}'
            subprocess.run(["sh", "-c", cmd], check=True)
            return {"message": "✅ Sudo 免密配置成功！"}

        elif system == "Darwin":
            return {"message": "⚠️ macOS 系统的安全机制限制较严，建议保持按需授权模式。"}

    except Exception as e:
        return {"message": f"设置失败: {str(e)}"}

def execute_clean(kwargs):
    """ 步骤 3：核心防御线。优先尝试静默提权 """
    if not os.path.exists(LOG_BLG):
        return {"message": "没有找到可清理的日志记录"}

    system = platform.system()
    try:
        if system == "Windows":
            task_name = "ButlerSysCleaner"
            # 尝试运行计划任务 (静默)
            result = subprocess.run(["schtasks", "/run", "/tn", task_name], capture_output=True)
            if result.returncode == 0:
                return {"message": "🚀 Butler 已通过静默通道完成强力清理！"}

            # 备选方案：回到传统的 UAC 弹窗
            import ctypes
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", CORE_EXE, f"-mode delete -out \"{LOG_BLG}\"", None, 1
            )
            if int(ret) <= 32:
                return {"message": "⚠️ 权限被拒绝：你取消了 UAC 授权。"}

        elif system == "Linux":
            # 尝试使用 sudo (如果 NOPASSWD 已配置则静默)
            subprocess.run(["sudo", CORE_EXE, "-mode", "delete", "-out", LOG_BLG], check=True)
            return {"message": "🚀 Butler 已完成强力清理！"}

        elif system == "Darwin":
            cmd = f'do shell script "{CORE_EXE} -mode delete -out \\"{LOG_BLG}\\"" with administrator privileges'
            subprocess.run(["osascript", "-e", cmd], check=True)
            return {"message": "🚀 授权成功：清理完成！"}

        else:
            return {"message": f"不支持的系统平台: {system}"}

        return {"message": "🚀 清理任务已执行。"}
    except Exception as e:
        logger.error(f"Execution clean error: {e}")
        return {"message": f"系统错误: {str(e)}"}

def handle_request(action, **kwargs):
    """Butler 技能入口"""
    if action == "start_track":
        return start_track(kwargs)
    elif action == "stop_track":
        return stop_track(kwargs)
    elif action == "execute_clean":
        return execute_clean(kwargs)
    elif action == "setup_elevation":
        return setup_elevation(kwargs)
    return {"error": f"Unknown action: {action}"}

if __name__ == '__main__':
    # 允许直接运行进行简单测试
    if len(sys.argv) > 1:
        print(handle_request(sys.argv[1]))
