#!/usr/bin/env python3
"""
Butler 打包脚本 — 使用 PyInstaller 生成 .exe
支持: Windows / Linux / macOS

用法:
    python build.py              # 默认打包 TUI 版本
    python build.py --mode gui   # 打包 GUI 版本
    python build.py --mode tui   # 打包 TUI 版本
    python build.py --mode all   # 打包全部
    python build.py --clean      # 清理构建目录
"""

import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
SPEC_DIR = PROJECT_ROOT / "build_specs"


def check_pyinstaller():
    """检查并安装 PyInstaller"""
    try:
        import PyInstaller
        print(f"[OK] PyInstaller {PyInstaller.__version__}")
        return True
    except ImportError:
        print("[安装] PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        return True


def clean():
    """清理构建目录"""
    for d in [BUILD_DIR, DIST_DIR, SPEC_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"[清理] {d}")
    # 清理 .spec 文件
    for f in PROJECT_ROOT.glob("*.spec"):
        f.unlink()
        print(f"[清理] {f}")
    print("[完成] 清理完毕")


def collect_data_files():
    """收集需要打包的数据文件"""
    data_files = []

    # 技能目录
    skills_dir = PROJECT_ROOT / "skills"
    if skills_dir.exists():
        data_files.append((str(skills_dir), "skills"))

    # 配置目录
    config_dir = PROJECT_ROOT / "config"
    if config_dir.exists():
        data_files.append((str(config_dir), "config"))

    # 前端文件
    frontend_dir = PROJECT_ROOT / "frontend"
    if frontend_dir.exists():
        data_files.append((str(frontend_dir), "frontend"))

    # 包目录（翻译器等）
    package_dir = PROJECT_ROOT / "package"
    if package_dir.exists():
        data_files.append((str(package_dir), "package"))

    # .env.example
    env_example = PROJECT_ROOT / ".env.example"
    if env_example.exists():
        data_files.append((str(env_example), "."))

    return data_files


def collect_hidden_imports():
    """收集隐式导入的模块"""
    return [
        "butler",
        "butler.__main__",
        "butler.agent",
        "butler.agent.agent",
        "butler.agent.context",
        "butler.agent.executor",
        "butler.agent.planner",
        "butler.agent.verifier",
        "butler.core",
        "butler.cli",
        "butler.cli.main",
        "butler.tui",
        "package",
        "package.document",
        "package.document.translators",
        "package.file_system",
        "package.network",
        "package.vision",
        "package.core_utils",
        "flask",
        "PIL",
        "openai",
        "deepseek",
        "anthropic",
    ]


def build_tui():
    """打包 TUI 终端版本"""
    print("\n" + "=" * 50)
    print("打包 Butler TUI 版本")
    print("=" * 50)

    data_files = collect_data_files()
    hidden_imports = collect_hidden_imports()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "Butler",
        "--onedir",                    # 打包为目录（而非单文件，启动更快）
        "--console",                   # 控制台应用
        "--clean",
        "--noconfirm",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        f"--specpath={SPEC_DIR}",
    ]

    # 添加数据文件
    for src, dst in data_files:
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])

    # 添加隐式导入
    for mod in hidden_imports:
        cmd.extend(["--hidden-import", mod])

    # 入口文件
    cmd.append(str(PROJECT_ROOT / "butler" / "__main__.py"))

    print(f"[命令] {' '.join(cmd[:10])}...")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode == 0:
        print(f"\n[完成] TUI 版本打包成功: {DIST_DIR / 'Butler'}")
        print(f"[运行] {DIST_DIR / 'Butler' / 'Butler.exe'}")
    else:
        print("\n[失败] 打包失败，请检查错误信息")

    return result.returncode == 0


def build_gui():
    """打包 GUI 现代界面版本"""
    print("\n" + "=" * 50)
    print("打包 Butler GUI 版本")
    print("=" * 50)

    data_files = collect_data_files()
    hidden_imports = collect_hidden_imports() + [
        "frontend",
        "frontend.program",
        "frontend.program.modern_app",
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "Butler-GUI",
        "--onedir",
        "--console",                   # 保留控制台（日志输出）
        "--clean",
        "--noconfirm",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        f"--specpath={SPEC_DIR}",
    ]

    for src, dst in data_files:
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])

    for mod in hidden_imports:
        cmd.extend(["--hidden-import", mod])

    cmd.append(str(PROJECT_ROOT / "frontend" / "program" / "modern_app.py"))

    print(f"[命令] {' '.join(cmd[:10])}...")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode == 0:
        print(f"\n[完成] GUI 版本打包成功: {DIST_DIR / 'Butler-GUI'}")
    else:
        print("\n[失败] 打包失败")

    return result.returncode == 0


def build_launcher():
    """打包一个统一启动器（选择 TUI/GUI/CLI）"""
    print("\n" + "=" * 50)
    print("打包 Butler 统一启动器")
    print("=" * 50)

    # 创建启动器脚本
    launcher_py = PROJECT_ROOT / "_launcher.py"
    launcher_py.write_text(r'''#!/usr/bin/env python3
"""Butler 启动器 — 选择启动模式"""
import os
import sys
import subprocess

def main():
    print("=" * 40)
    print("  🤵 Butler — 本地优先智能管家")
    print("=" * 40)
    print()
    print("  选择启动模式:")
    print("    1. TUI 终端界面 (默认)")
    print("    2. GUI 现代界面")
    print("    3. CLI 命令行")
    print("    4. 翻译扩展构建")
    print("    0. 退出")
    print()

    choice = input("  请输入选项 [1]: ").strip() or "1"

    # 获取 exe 所在目录
    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    if choice == "1":
        import butler.__main__
    elif choice == "2":
        try:
            import frontend.program.modern_app
        except ImportError:
            print("[错误] GUI 模块未安装")
    elif choice == "3":
        args = input("  输入命令: ").strip()
        if args:
            import butler.cli.main
    elif choice == "4":
        print("  构建翻译扩展...")
        os.chdir(os.path.join(base_dir, "frontend", "translate"))
        subprocess.run([sys.executable, "-m", "pip", "install", "npm"], shell=True)
        subprocess.run(["npm", "run", "build"], shell=True)
    elif choice == "0":
        return
    else:
        print("  无效选项")

if __name__ == "__main__":
    main()
''')

    data_files = collect_data_files()
    hidden_imports = collect_hidden_imports() + [
        "frontend",
        "frontend.program",
        "frontend.program.modern_app",
    ]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "Butler-Launcher",
        "--onedir",
        "--console",
        "--clean",
        "--noconfirm",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        f"--specpath={SPEC_DIR}",
    ]

    for src, dst in data_files:
        cmd.extend(["--add-data", f"{src}{os.pathsep}{dst}"])

    for mod in hidden_imports:
        cmd.extend(["--hidden-import", mod])

    cmd.append(str(launcher_py))

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    # 清理临时启动器
    launcher_py.unlink(missing_ok=True)

    if result.returncode == 0:
        print(f"\n[完成] 启动器打包成功: {DIST_DIR / 'Butler-Launcher'}")
        print(f"[运行] 双击 {DIST_DIR / 'Butler-Launcher' / 'Butler-Launcher.exe'}")
    else:
        print("\n[失败] 打包失败")

    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Butler 打包工具")
    parser.add_argument("--mode", choices=["tui", "gui", "all", "launcher"], default="tui",
                        help="打包模式 (默认: tui)")
    parser.add_argument("--clean", action="store_true", help="清理构建目录")

    args = parser.parse_args()

    if args.clean:
        clean()
        return

    print("🤵 Butler 打包工具")
    print(f"项目目录: {PROJECT_ROOT}")
    print(f"Python: {sys.version}")

    check_pyinstaller()

    if args.mode == "tui":
        build_tui()
    elif args.mode == "gui":
        build_gui()
    elif args.mode == "launcher":
        build_launcher()
    elif args.mode == "all":
        build_tui()
        build_gui()
        build_launcher()


if __name__ == "__main__":
    main()
