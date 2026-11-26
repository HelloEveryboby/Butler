# -*- coding: utf-8 -*-
"""Butler 统一入口 - 职责清晰的模式调度.

界面模式 (互斥, 默认 tui):
  tui       终端用户界面 (Textual)        — 默认
  gui       Tkinter 经典桌面界面
  web       pywebview 现代桌面界面
  headless  无头模式 (Butler 后台 + API, 无前台 UI)

服务 / 管理子命令:
  api       启动 FastAPI REST 网关 (原 start)
  cli       功能型命令行 (crawl/email/encrypt 等子命令)
  agent     数字员工管理 (list|run)
  package   包管理 (list|install)
  config    交互式配置 AI 服务商与密钥
  doctor    系统诊断自检

向后兼容 (隐藏, 带废弃提示):
  --tui / --legacy / --headless / --cli / start / legacy
"""
import sys


def main():
    argv = sys.argv[1:]

    # 无参数 → 默认 TUI
    if not argv:
        _launch_tui()
        return

    first = argv[0]

    # ── 帮助 ──
    if first in ("-h", "--help", "help"):
        _print_help()
        return

    # ── 向后兼容: --flags (带废弃提示) ──
    if first == "--tui":
        _warn_deprecated("--tui", "tui")
        _launch_tui()
        return
    if first == "--legacy":
        _warn_deprecated("--legacy", "gui 或 web")
        _launch_legacy("--skip-setup" in argv)
        return
    if first == "--headless":
        _warn_deprecated("--headless", "headless")
        _launch_headless(*_extract_host_port(argv[1:]))
        return
    if first == "--cli":
        _warn_deprecated("--cli", "cli")
        _launch_old_cli(argv[1:])
        return

    # ── 别名 ──
    if first == "start":
        # start 是 api 的友好别名 (对外文档与安装器统一推荐 butler start)
        _launch_api(*_extract_host_port(argv[1:]))
        return
    if first == "legacy":
        _warn_deprecated("legacy", "gui 或 web")
        _launch_legacy("--skip-setup" in argv)
        return

    # ── 子命令调度 ──
    mode = first
    rest = argv[1:]

    if mode == "tui":
        _launch_tui()
    elif mode == "gui":
        _launch_gui("--skip-setup" in rest)
    elif mode == "web":
        _launch_web()
    elif mode == "headless":
        _launch_headless(*_extract_host_port(rest))
    elif mode == "api":
        _launch_api(*_extract_host_port(rest))
    elif mode == "cli":
        _launch_old_cli(rest)
    elif mode == "agent":
        _launch_agent(rest)
    elif mode == "hybrid":
        _launch_hybrid(rest)
    elif mode == "package":
        _launch_package(rest)
    elif mode == "config":
        _launch_config(rest)
    elif mode == "init":
        _launch_init(rest)
    elif mode == "doctor":
        _launch_doctor()
    elif mode in ("download", "下载"):
        _launch_download(rest)
    else:
        print(f"未知参数: {first}\n")
        _print_help()
        sys.exit(2)


# ────────────────────────────────────────────────────────────
# 启动函数 - 每个职责单一, 互不耦合
# ────────────────────────────────────────────────────────────

def _launch_tui():
    """启动 Textual TUI 终端界面 (默认)."""
    from butler.tui.main import run_tui
    run_tui()


def _launch_gui(skip_setup: bool = False):
    """启动 Tkinter 经典桌面界面 (强制 --classic, 不回退 web)."""
    from butler.butler_app_enhanced import main as legacy_main
    sys.argv = ["butler", "--classic"]
    if skip_setup:
        sys.argv.append("--skip-setup")
    legacy_main()


def _launch_web():
    """启动 pywebview 现代桌面界面."""
    from frontend.program.modern_app import main as modern_main
    modern_main()


def _launch_legacy(skip_setup: bool = False):
    """向后兼容: 调用增强启动器 (先尝试 web, 失败回退 tkinter)."""
    from butler.butler_app_enhanced import main as legacy_main
    sys.argv = ["butler"]
    if skip_setup:
        sys.argv.append("--skip-setup")
    legacy_main()


def _launch_headless(port: int = 5001, host: str = "0.0.0.0"):
    """无头模式: Butler 后台 + REST API, 无前台 UI."""
    import os
    import time
    os.environ.setdefault("BUTLER_API_HOST", host)
    os.environ.setdefault("BUTLER_API_PORT", str(port))
    from butler.butler_app import Jarvis, USBScreen
    usb_screen = USBScreen(40, 8)
    jarvis = Jarvis(None, usb_screen, headless=True)
    jarvis.main()
    while jarvis.running:
        time.sleep(1)


def _launch_api(port: int = 5001, host: str = "0.0.0.0"):
    """启动 FastAPI REST 网关服务 (原 start 子命令)."""
    from butler.core.runtime import ButlerRuntime
    runtime = ButlerRuntime(host=host, port=port)
    try:
        runtime.start()
    except KeyboardInterrupt:
        print("\n正在关闭 Butler API 服务...")
        runtime.stop()


def _launch_old_cli(rest: list):
    """启动功能型 CLI (crawl/email/encrypt 等子命令)."""
    from butler_cli import main as cli_main
    sys.argv = ["butler"] + rest
    cli_main()


def _launch_agent(rest: list):
    """数字员工管理子命令 (list|run)."""
    import argparse
    p = argparse.ArgumentParser(prog="butler agent", description="数字员工管理")
    sub = p.add_subparsers(dest="subaction")
    sub.add_parser("list", help="列出所有可用员工角色")
    run_p = sub.add_parser("run", help="委派任务给员工")
    run_p.add_argument("role", help="员工角色名")
    run_p.add_argument("task", help="任务描述")
    args = p.parse_args(rest)

    from butler.cli import agent_cmd
    if args.subaction == "run":
        agent_cmd.run_agent_task(args.role, args.task)
    else:
        agent_cmd.list_agents()


def _launch_hybrid(rest: list):
    """混合语言模块（BHL）的构建/状态/调用."""
    from butler.cli.hybrid_cmd import run_hybrid

    sys.exit(run_hybrid(rest))


def _launch_package(rest: list):
    """包管理子命令 (list|install)."""
    import argparse
    p = argparse.ArgumentParser(prog="butler package", description="包管理")
    sub = p.add_subparsers(dest="subaction")
    sub.add_parser("list", help="列出已安装包")
    inst_p = sub.add_parser("install", help="安装本地包")
    inst_p.add_argument("path", help="包路径")
    args = p.parse_args(rest)

    from butler.cli import package_cmd
    if args.subaction == "install":
        package_cmd.install_package(args.path)
    else:
        package_cmd.list_packages()


def _launch_doctor():
    """系统诊断自检."""
    from butler.cli import doctor_cmd
    doctor_cmd.run_doctor()


def _launch_config(rest: list):
    """交互式配置 AI 服务商与密钥."""
    try:
        from butler.cli import config_cmd
    except ImportError as e:
        _friendly_import_error(e)
        return
    sub = rest[0] if rest else ""
    config_cmd.run_config(sub)


def _launch_init(rest: list):
    """首次配置向导 (3 分钟上手)."""
    try:
        from butler.cli.init_cmd import run_init
    except ImportError as e:
        _friendly_import_error(e)
        return
    run_init(skip_check="--skip-check" in rest)


def _friendly_import_error(e: ImportError):
    """依赖缺失时输出标准错误码块，而不是裸 traceback (参见 docs/dev/ERROR_CODES.md)。"""
    try:
        from butler.core.errors import format_error
        print(format_error("BTL-1002", detail=str(e)))
    except Exception:
        print(f"❌ [BTL-1002] 缺少 Python 依赖包: {e}\n   修复: python -m package.dependency_manager install_all")


def _launch_download(rest: list):
    """启动 Linux 风格 CLI / Rich TUI 资源下载器."""
    from downloader.cli import build_cli_parser, download_cli
    p = build_cli_parser()
    args = p.parse_args(rest)
    target_out = args.flag_output or args.pos_output
    download_cli(args.url, output_dir=target_out, daemon=args.daemon)


# ────────────────────────────────────────────────────────────
# 辅助
# ────────────────────────────────────────────────────────────

def _extract_host_port(args: list) -> tuple:
    """从参数列表提取 --host / --port (默认 0.0.0.0:5001)."""
    port, host = 5001, "0.0.0.0"
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        else:
            i += 1
    return port, host


def _warn_deprecated(old: str, new: str):
    """打印废弃提示到 stderr."""
    print(f"⚠️ [已废弃] '{old}' 将在未来版本移除, 请改用 '{new}'.", file=sys.stderr)


def _print_help():
    """打印清晰的职责分工帮助."""
    print("""Butler AI 助手 - 统一入口 (默认启动 TUI)

💡 常用五件事:
  butler init          首次配置向导 (3 分钟上手)
  butler start         启动核心服务
  butler doctor        系统体检 (带下一步建议)
  butler skills        浏览技能目录 (skills/CATALOG.md)
  butler config show   查看当前 AI 配置

用法 (以下均可用统一命令 butler 代替 python -m butler):

界面模式 (互斥, 默认 tui):
  butler               启动 TUI 终端界面 (默认)
  butler tui           终端界面 (Textual)
  butler gui           Tkinter 经典桌面界面
  butler web           pywebview 现代桌面界面
  butler headless      无头模式 (Butler 后台 + API, 无前台 UI)

服务 / 管理:
  butler api [--port 5001] [--host 0.0.0.0]
                                启动 FastAPI REST 网关 (别名: butler start)
  butler init [--skip-check]   首次配置向导 (服务商 + Key 校验 + 示例)
  butler cli [...]    功能型 CLI (crawl/email/encrypt/translate...)
  butler agent list   列出数字员工
  butler agent run <角色> <任务>
                                委派任务给员工
  butler hybrid status|build|call
                                混合语言模块（C/C++/Go/Rust）状态/构建/调用
  butler package list 列出已安装包
  butler package install <路径>
                                安装本地包
  butler config       交互式配置 AI 服务商与密钥
  butler config show  查看当前 AI 配置
  butler config check 配置健康检查 (重复键/缺失项)
  butler doctor       系统诊断自检

通用选项:
  --skip-setup                  跳过初始化向导 (仅 gui/legacy)
  --port, --host                API 端口与地址 (仅 api/headless)
  -h, --help                    显示本帮助

向后兼容 (已废弃, 将移除):
  --tui, --legacy, --headless, --cli, legacy
""")


if __name__ == "__main__":
    main()
