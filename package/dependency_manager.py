"""
依赖管理器 - 用于将 Python 第三方库安装到项目本地文件夹 (lib_external) 的工具。
支持从 requirements.txt 安装所有依赖，或安装指定的单个包。
此工具可实现项目的“绿色便携化”，避免污染全局 Python 环境。
"""
import os
import sys
import subprocess
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

def run(*args, **kwargs):
    """
    将依赖安装到 lib_external 文件夹。
    参数:
        command: 'install_all' 或 'install'
        package: 如果 command 是 'install'，则指定包名
    示例:
        run(command="install_all")
        run(command="install", package="requests")
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dir = os.path.join(project_root, "lib_external")

    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        logger.info(f"已创建或确认本地库目录: {target_dir}")

    # 支持位置参数和关键字参数
    command = kwargs.get('command')
    if not command and args:
        command = args[0]

    if command == "install_all":
        req_file = os.path.join(project_root, "requirements.txt")
        if not os.path.exists(req_file):
            return "错误: 在项目根目录未找到 requirements.txt 文件。"

        cmd = [sys.executable, "-m", "pip", "install", "-t", target_dir, "-r", req_file, "--upgrade"]
        logger.info(f"正在开始将 requirements.txt 中的所有依赖安装到 {target_dir}...")
    elif command == "install":
        pkg_name = kwargs.get('package')
        if not pkg_name and len(args) > 1:
            pkg_name = args[1]

        if not pkg_name:
            return "错误: 使用 'install' 命令时必须指定要安装的包名。"

        cmd = [sys.executable, "-m", "pip", "install", "-t", target_dir, pkg_name, "--upgrade"]
        logger.info(f"正在将包 '{pkg_name}' 安装到 {target_dir}...")
    else:
        return f"未知命令 '{command}'。支持的命令有: 'install_all', 'install'。"

    try:
        # 使用 Popen 以便可以实时记录日志（可选，这里简单使用 run）
        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode == 0:
            success_msg = f"依赖安装成功。库文件位于: {target_dir}\n请确保项目已配置为从该目录加载库。"
            logger.info(success_msg)
            return success_msg
        else:
            error_details = process.stderr if process.stderr else "未知错误（无 stderr 输出）"
            error_msg = f"pip 安装过程中出错 (返回码 {process.returncode}):\n{error_details}"
            logger.error(error_msg)
            return error_msg
    except Exception as e:
        error_msg = f"依赖管理器执行时发生异常: {str(e)}"
        logger.error(error_msg)
        return error_msg

if __name__ == "__main__":
    # 允许直接从命令行运行
    import sys as sys_module
    if len(sys_module.argv) > 1:
        cmd = sys_module.argv[1]
        if cmd == "install_all":
            print(run(command="install_all"))
        elif cmd == "install" and len(sys_module.argv) > 2:
            print(run(command="install", package=sys_module.argv[2]))
        else:
            print("用法: python dependency_manager.py install_all")
            print("用法: python dependency_manager.py install <package_name>")
    else:
        print("依赖管理器已就绪。")
        print("可用命令: install_all, install <package>")
