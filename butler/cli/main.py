# -*- coding: utf-8 -*-
import sys
import argparse
from butler.core.runtime import ButlerRuntime
from butler.cli import agent_cmd, doctor_cmd

def run_cli():
    # Automatically execute database migrations
    try:
        from butler.core.db_migrations import run_all_migrations
        run_all_migrations()
    except Exception as e:
        pass

    parser = argparse.ArgumentParser(
        description="Butler v2.0 MVP - 数字员工操作系统控制中心"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用的命令选项")

    # 1. start
    subparsers.add_parser("start", help="启动 Butler 运行时服务")

    # 2. agent
    agent_parser = subparsers.add_parser("agent", help="管理并指派任务给数字员工")
    agent_sub = agent_parser.add_subparsers(dest="subaction", help="操作")
    agent_sub.add_parser("list", help="列出可用的数字员工角色")
    run_sub = agent_sub.add_parser("run", help="委派具体任务")
    # Support running agent run <role> <task> OR agent run <task>
    run_sub.add_argument("role_or_task", help="角色名称或具体任务描述")
    run_sub.add_argument("task", nargs="?", default=None, help="具体任务描述（可选）")

    # 3. tool
    tool_parser = subparsers.add_parser("tool", help="管理及查看系统工具")
    tool_sub = tool_parser.add_subparsers(dest="subaction", help="对工具的操作")
    tool_sub.add_parser("list", help="列出所有可用的工具")

    # 4. doctor
    subparsers.add_parser("doctor", help="对运行层执行全面体检诊断自检")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.command == "start":
        runtime = ButlerRuntime()
        runtime.start()

    elif args.command == "agent":
        if args.subaction == "list" or not args.subaction:
            agent_cmd.list_agents()
        elif args.subaction == "run":
            # If second argument is not provided, first is the task, and role is supervisor
            if args.task is None:
                role = "supervisor"
                task = args.role_or_task
            else:
                role = args.role_or_task
                task = args.task
            agent_cmd.run_agent_task(role, task)

    elif args.command == "tool":
        if args.subaction == "list" or not args.subaction:
            runtime = ButlerRuntime()
            runtime.load_tools()
            print("可用的工具列表:")
            for tool_name, tool_instance in runtime.tools.items():
                print(f"  - {tool_name}: {tool_instance.__class__.__name__}")

    elif args.command == "doctor":
        doctor_cmd.run_doctor()
