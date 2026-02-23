"""
依赖管理器 - 用于管理项目本地依赖与 Python 运行环境的工具。
支持将第三方库安装到 lib_external，以及设置便携式 Python (runtime)。
此工具可实现项目的“完全绿色便携化”。
"""
import os
import sys
import subprocess
import urllib.request
import zipfile
import tarfile
import platform
import shutil
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

def setup_runtime(target_dir):
    """下载并设置便携式 Python 运行环境"""
    os.makedirs(target_dir, exist_ok=True)
    system = platform.system()
    arch = platform.machine().lower()

    logger.info(f"正在为 {system} ({arch}) 准备便携式 Python 环境...")

    # 定义下载链接 (示例使用 3.12.3)
    urls = {
        "Windows": "https://www.python.org/ftp/python/3.12.3/python-3.12.3-embed-amd64.zip",
        "Linux": "https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-3.12.3+20240415-x86_64-unknown-linux-gnu-install_only.tar.gz",
        "Darwin": "https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-3.12.3+20240415-aarch64-apple-darwin-install_only.tar.gz" if "arm" in arch else "https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-3.12.3+20240415-x86_64-apple-darwin-install_only.tar.gz"
    }

    url = urls.get(system)
    if not url:
        return f"错误: 暂不支持为系统 {system} 自动下载便携版 Python。"

    archive_path = os.path.join(target_dir, "python_runtime.archive")

    try:
        logger.info(f"正在从 {url} 下载...")
        urllib.request.urlretrieve(url, archive_path)

        logger.info("正在解压运行环境...")
        if url.endswith(".zip"):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
            # Windows Embeddable 特殊处理: 启用 site-packages
            pth_file = None
            for f in os.listdir(target_dir):
                if f.endswith("._pth"):
                    pth_file = os.path.join(target_dir, f)
                    break
            if pth_file:
                with open(pth_file, "a") as f:
                    # 允许加载 site-packages 并将项目根目录加入路径
                    f.write("\nimport site\n")
                    f.write("..\n")
                    f.write("../lib_external\n")
        else:
            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                tar_ref.extractall(target_dir)
            # 移动内容到根部 (针对 python-build-standalone 的结构)
            inner_dir = os.path.join(target_dir, "python")
            if os.path.exists(inner_dir):
                for item in os.listdir(inner_dir):
                    shutil.move(os.path.join(inner_dir, item), target_dir)
                os.rmdir(inner_dir)

        os.remove(archive_path)
        logger.info("便携式运行环境设置完成。")
        return "便携式运行环境设置成功。"
    except Exception as e:
        logger.error(f"设置运行环境时出错: {e}")
        return f"错误: {e}"

def run(*args, **kwargs):
    """
    执行依赖管理操作。
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    target_dir = os.path.join(project_root, "lib_external")

    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)

    command = kwargs.get('command')
    if not command and args:
        command = args[0]

    if command == "setup_runtime":
        runtime_dir = os.path.join(project_root, "runtime")
        return setup_runtime(runtime_dir)
    elif command == "install_all":
        req_file = os.path.join(project_root, "requirements.txt")
        if not os.path.exists(req_file):
            return "错误: 未找到 requirements.txt。"

        cmd = [sys.executable, "-m", "pip", "install", "-t", target_dir, "-r", req_file, "--upgrade"]
        logger.info(f"正在安装所有依赖到 {target_dir}...")
    elif command == "install":
        pkg_name = kwargs.get('package')
        if not pkg_name and len(args) > 1:
            pkg_name = args[1]

        if not pkg_name:
            return "错误: 未指定包名。"

        cmd = [sys.executable, "-m", "pip", "install", "-t", target_dir, pkg_name, "--upgrade"]
        logger.info(f"正在安装包 '{pkg_name}'...")
    else:
        return f"未知命令 '{command}'。"

    try:
        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode == 0:
            return f"操作成功完成。目标: {target_dir}"
        else:
            return f"出错: {process.stderr}"
    except Exception as e:
        return f"异常: {str(e)}"

if __name__ == "__main__":
    import sys as sys_module
    if len(sys_module.argv) > 1:
        cmd = sys_module.argv[1]
        if cmd == "install_all":
            print(run(command="install_all"))
        elif cmd == "install" and len(sys_module.argv) > 2:
            print(run(command="install", package=sys_module.argv[2]))
        elif cmd == "setup_runtime":
            print(run(command="setup_runtime"))
        else:
            print("用法: python -m package.dependency_manager setup_runtime|install_all|install <pkg>")
    else:
        print("可用命令: setup_runtime, install_all, install <package>")
