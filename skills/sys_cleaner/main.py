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

def execute_clean(kwargs):
    """ 步骤 3：核心防御线。动态向系统请求特权授权 """
    if not os.path.exists(LOG_BLG):
        return {"message": "没有找到可清理的日志记录"}

    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            # 触发 UAC 提权
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", CORE_EXE, f"-mode delete -out \"{LOG_BLG}\"", None, 1
            )
            if int(ret) <= 32:
                return {"message": "⚠️ 权限被拒绝：你取消了 UAC 授权，未执行任何物理修改。"}

        elif system == "Darwin":
            # macOS: 使用 osascript 触发授权弹窗
            cmd = f'do shell script "{CORE_EXE} -mode delete -out \\"{LOG_BLG}\\"" with administrator privileges'
            subprocess.run(["osascript", "-e", cmd], check=True)

        elif system == "Linux":
            # Linux: 尝试 pkexec (Polkit)，如果不存在则回退到 sudo (命令行模式)
            try:
                subprocess.run(["pkexec", CORE_EXE, "-mode", "delete", "-out", LOG_BLG], check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                # 如果 pkexec 不存在或失败，尝试 sudo
                subprocess.run(["sudo", CORE_EXE, "-mode", "delete", "-out", LOG_BLG], check=True)

        else:
            return {"message": f"不支持的系统平台: {system}"}

        return {"message": "🚀 授权成功：Butler 已在独立特权进程中完成强力清理！"}
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
    return {"error": f"Unknown action: {action}"}

if __name__ == '__main__':
    # 允许直接运行进行简单测试
    if len(sys.argv) > 1:
        print(handle_request(sys.argv[1]))
