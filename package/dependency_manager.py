"""
依赖管理器 - 用于管理项目本地依赖与多语言运行环境的工具。
支持将第三方库安装到 lib_external，以及设置便携式 Python, Go, Java, Rust 运行环境。
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
import logging
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(PROJECT_ROOT, "runtime")

def download_and_extract(url, target_subdir):
    """通用的下载与解压工具"""
    target_path = os.path.join(RUNTIME_DIR, target_subdir)
    os.makedirs(target_path, exist_ok=True)

    archive_path = os.path.join(target_path, "download.tmp")

    try:
        logger.info(f"正在从 {url} 下载...")
        urllib.request.urlretrieve(url, archive_path)

        logger.info(f"正在解压到 {target_path}...")
        if url.endswith(".zip"):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(target_path)
        elif url.endswith(".tar.gz") or url.endswith(".tgz"):
            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                tar_ref.extractall(target_path)

        os.remove(archive_path)

        # 优化目录结构（如果解压后只有一层同名文件夹，将其内容上移）
        items = os.listdir(target_path)
        if len(items) == 1:
            inner_dir = os.path.join(target_path, items[0])
            if os.path.isdir(inner_dir):
                for item in os.listdir(inner_dir):
                    shutil.move(os.path.join(inner_dir, item), target_path)
                os.rmdir(inner_dir)

        return True
    except Exception as e:
        logger.error(f"下载或解压失败: {e}")
        if os.path.exists(archive_path): os.remove(archive_path)
        return False

def setup_python():
    """下载并设置便携式 Python 运行环境"""
    system = platform.system()
    arch = platform.machine().lower()

    urls = {
        "Windows": "https://www.python.org/ftp/python/3.12.3/python-3.12.3-embed-amd64.zip",
        "Linux": "https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-3.12.3+20240415-x86_64-unknown-linux-gnu-install_only.tar.gz",
        "Darwin": "https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-3.12.3+20240415-aarch64-apple-darwin-install_only.tar.gz" if "arm" in arch else "https://github.com/indygreg/python-build-standalone/releases/download/20240415/cpython-3.12.3+20240415-x86_64-apple-darwin-install_only.tar.gz"
    }

    url = urls.get(system)
    if not url: return "错误: 暂不支持此系统的 Python 下载。"

    if download_and_extract(url, "python"):
        # Windows Embeddable 特殊处理: 启用 site-packages
        if system == "Windows":
            target_dir = os.path.join(RUNTIME_DIR, "python")
            pth_file = next((os.path.join(target_dir, f) for f in os.listdir(target_dir) if f.endswith("._pth")), None)
            if pth_file:
                with open(pth_file, "a") as f:
                    f.write("\nimport site\n..\n../lib_external\n")
        return "Python 运行环境设置成功。"
    return "Python 设置失败。"

def setup_go():
    """下载便携式 Go 运行环境"""
    system = platform.system().lower()
    arch = "amd64" # 简化处理，默认 x64
    ext = "zip" if system == "windows" else "tar.gz"

    url = f"https://go.dev/dl/go1.22.2.{system}-{arch}.{ext}"
    if download_and_extract(url, "go"):
        return "Go 环境设置成功。"
    return "Go 设置失败。"

def setup_java():
    """下载便携式 Java (JDK)"""
    system = platform.system()
    os_name = "windows" if system == "Windows" else ("linux" if system == "Linux" else "mac")
    ext = "zip" if system == "Windows" else "tar.gz"

    # 使用 Adoptium Temurin OpenJDK
    url = f"https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.10%2B7/OpenJDK17U-jdk_x64_{os_name}_hotspot_17.0.10_7.{ext}"
    if download_and_extract(url, "java"):
        return "Java JDK 设置成功。"
    return "Java 设置失败。"

def setup_rust():
    """下载便携式 Rust 工具链 (主要针对 Windows)"""
    if platform.system() != "Windows":
        return "提示: Linux/macOS 建议通过 'curl --proto =https --tlsv1.2 -sSf https://sh.rustup.rs | sh' 安装 Rust。"

    # Windows 下下载独立的 MinGW/GNU 工具链 (示例链接)
    url = "https://github.com/rust-lang/rust-installer/archive/refs/tags/v1.0.tar.gz" # 仅为示例
    # 实际上 Rust 较难完全绿色化，通常需要 rustup。这里仅作框架保留。
    return "Rust 自动安装尚在开发中，请手动安装 rustup。"

def run(*args, **kwargs):
    """
    执行依赖管理操作。
    """
    target_dir = os.path.join(PROJECT_ROOT, "lib_external")
    os.makedirs(target_dir, exist_ok=True)

    command = kwargs.get('command') or (args[0] if args else None)

    if command == "setup_python": return setup_python()
    elif command == "setup_go": return setup_go()
    elif command == "setup_java": return setup_java()
    elif command == "setup_polyglot":
        results = [setup_python(), setup_go(), setup_java()]
        return "\n".join(results)
    elif command == "install_all":
        req_file = os.path.join(PROJECT_ROOT, "requirements.txt")
        if not os.path.exists(req_file): return "错误: 未找到 requirements.txt。"
        cmd = [sys.executable, "-m", "pip", "install", "-t", target_dir, "-r", req_file, "--upgrade"]
        logger.info(f"正在安装 Python 依赖到 {target_dir}...")
    elif command == "install":
        pkg_name = kwargs.get('package') or (args[1] if len(args) > 1 else None)
        if not pkg_name: return "错误: 未指定包名。"
        cmd = [sys.executable, "-m", "pip", "install", "-t", target_dir, pkg_name, "--upgrade"]
        logger.info(f"正在安装包 '{pkg_name}'...")
    else:
        return f"未知命令 '{command}'。可用: setup_python, setup_go, setup_java, setup_polyglot, install_all, install"

    try:
        process = subprocess.run(cmd, capture_output=True, text=True)
        if process.returncode == 0:
            return f"操作成功完成。目标: {target_dir}"
        else:
            return f"出错: {process.stderr}"
    except Exception as e:
        return f"异常: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(run(command=sys.argv[1], package=sys.argv[2] if len(sys.argv) > 2 else None))
    else:
        print("用法: python -m package.dependency_manager <command> [args]")
