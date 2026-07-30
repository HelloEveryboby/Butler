# -*- coding: utf-8 -*-
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Butler AI 助手 - 命令行终端 (TUI) 和 API 控制中心",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m butler                  # 启动 TUI (默认)
  python -m butler --tui            # 启动 TUI
  python -m butler --legacy         # 启动经典 Tkinter 界面
  python -m butler --headless       # 无头模式 (API only)
  python -m butler start --port 5001  # 仅启动 API 服务
  python -m butler agent list       # 列出数字员工
  python -m butler package list     # 列出已安装包
  python -m butler doctor           # 系统诊断
        """
    )

    parser.add_argument("--tui", action="store_true", help="启动 TUI 终端界面 (默认)")
    parser.add_argument("--legacy", action="store_true", help="启动经典 Tkinter GUI 界面")
    parser.add_argument("--headless", action="store_true", help="无头模式 (仅 API 服务)")
    parser.add_argument("--cli", action="store_true", help="使用旧版 CLI 命令行模式")
    parser.add_argument("--skip-setup", action="store_true", help="跳过初始化向导")

    # Positional arguments for v2.0 CLI
    parser.add_argument("command", nargs="?", default=None,
                        choices=["start", "agent", "package", "doctor", "tui", "legacy"],
                        help="CLI 子命令")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="子命令参数")

    if len(sys.argv) == 1:
        # No arguments: launch TUI
        _launch_tui(headless=False)
        return

    args = parser.parse_args()

    # Determine mode
    if args.headless:
        _launch_tui(headless=True)
    elif args.legacy or args.command == "legacy":
        _launch_legacy(args.skip_setup)
    elif args.cli:
        _launch_old_cli()
    elif args.command in ("start", "agent", "package", "doctor"):
        _launch_v2_cli(args.command, args.args)
    elif args.command == "tui" or args.tui:
        _launch_tui(headless=False)
    else:
        parser.print_help()


def _launch_tui(headless: bool = False):
    """启动 TUI 终端界面."""
    from butler.tui.main import run_tui
    # 注入 headless 模式到环境
    if headless:
        import os
        os.environ["BUTLER_HEADLESS"] = "1"
    run_tui()


def _launch_legacy(skip_setup: bool = False):
    """启动经典 Tkinter 界面."""
    from butler.butler_app_enhanced import main as legacy_main
    sys.argv = ["butler"]
    if skip_setup:
        sys.argv.append("--skip-setup")
    legacy_main()


def _launch_old_cli():
    """启动旧版 CLI 模式."""
    from butler_cli import main as cli_main
    cli_main()


def _launch_v2_cli(command: str, args: list):
    """启动 v2.0 CLI 命令."""
    from butler.cli.main import run_cli
    # 重建 sys.argv 为 v2.0 CLI 格式
    import sys
    new_argv = ["butler"] + [command] + (args or [])
    sys.argv = new_argv
    run_cli()


if __name__ == "__main__":
    main()
