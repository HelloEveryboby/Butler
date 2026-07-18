# -*- coding: utf-8 -*-
import sys
import argparse
from butler.cli import doctor_cmd, package_cmd, agent_cmd
from butler.core.runtime import ButlerRuntime
from butler.core.db_migrations import run_all_migrations

def run_cli():
    # 自愈自初始化机制：在任何 CLI 命令执行前，自动检测并补全 SQLite 数据表迁移，防止冷启动表不存在错误
    try:
        run_all_migrations()
    except Exception as e:
        print(f"⚠️ [警告] 自动执行数据库表迁移失败: {e}")

    parser = argparse.ArgumentParser(
        description="Butler v2.0 Alpha 命令行终端 - 数字员工操作系统控制中心"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用的命令选项")

    # 1. start
    start_parser = subparsers.add_parser("start", help="启动 Butler 核心运行时服务及 REST API 高安全网关")
    start_parser.add_argument("--port", type=int, default=5001, help="API 网关绑定的端口（默认为 5001）")
    start_parser.add_argument("--host", default="0.0.0.0", help="绑定的主机地址（默认为 0.0.0.0）")

    # 2. package
    package_parser = subparsers.add_parser("package", help="管理扩展的 AI 技能和数字员工包")
    pkg_sub = package_parser.add_subparsers(dest="subaction", help="对技能包的操作")
    pkg_sub.add_parser("list", help="列出当前所有已安装、已激活的包记录")
    install_sub = pkg_sub.add_parser("install", help="从本地加载并安装一个全新的技能包")
    install_sub.add_argument("path", help="包含有效 manifest.json 文件的本地文件夹路径")

    # 3. agent
    agent_parser = subparsers.add_parser("agent", help="管理并指派具体任务给数字员工（AI Employees）")
    agent_sub = agent_parser.add_subparsers(dest="subaction", help="对员工的操作")
    agent_sub.add_parser("list", help="列出当前系统所有可用的数字员工角色")
    run_sub = agent_sub.add_parser("run", help="委派一个具体任务给选定的数字员工角色")
    run_sub.add_argument("role", help="选定的员工名称/角色（例如: demo-agent）")
    run_sub.add_argument("task", help="委派的具体需求任务描述（例如: '读取紧急报价并整理汇报'）")

    # 4. doctor
    subparsers.add_parser("doctor", help="对整个运行层、数据库和包依赖执行一键全面体检诊断自检")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.command == "start":
        print(f"🚀 正在拉起并初始化 Butler v2.0 Alpha 核心运行时，绑定地址: {args.host}:{args.port}...")
        runtime = ButlerRuntime(host=args.host, port=args.port)
        try:
            runtime.start()
        except KeyboardInterrupt:
            print("\n正在优雅关闭并停止 Butler 核心运行时...")
            runtime.stop()
            print("Butler 核心服务已成功停止退出。")

    elif args.command == "package":
        if args.subaction == "list" or not args.subaction:
            package_cmd.list_packages()
        elif args.subaction == "install":
            package_cmd.install_package(args.path)

    elif args.command == "agent":
        if args.subaction == "list" or not args.subaction:
            agent_cmd.list_agents()
        elif args.subaction == "run":
            agent_cmd.run_agent_task(args.role, args.task)

    elif args.command == "doctor":
        doctor_cmd.run_doctor()
