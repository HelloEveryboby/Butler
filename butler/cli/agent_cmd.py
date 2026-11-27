import argparse
import json
import time

from butler.agent.agent import Agent
from butler.package_runtime.loader import PackageLoader


def list_agents():
    """
    列出所有可用的数字员工角色（Agent Character）。
    """
    loader = PackageLoader()
    packages = loader.registry.list_packages()

    print("\n==============================================")
    print("            可用的 Butler 数字员工角色        ")
    print("==============================================")
    found_agents = []
    for p in packages:
        manifest = loader.get_manifest(p['name'])
        if manifest and manifest.type == "agent":
            found_agents.append((p['name'], p['version'], manifest))

    if not found_agents:
        # 兜底显示内置的主管员工
        print("🤖 角色: supervisor         | 角色定义: 主管员工 (系统内置)")
    else:
        for name, version, manifest in found_agents:
            print(f"🤖 角色: {name:<18} | 版本: {version:<8} | 员工定义: {manifest.type}")
            print(f"   - 声明系统权限: {', '.join(manifest.permissions) or '无'}")
            print(f"   - 脚本入口: {manifest.entry}")
    print("==============================================\n")

def run_agent_task(
    agent_role: str,
    task_input: str,
    session_id: str | None = None,
    resume: bool = False,
):
    """
    指派并运行某个指定角色的数字员工任务。

    走的是 AgentRuntime 的原生工具调用循环（LLM 自主决定调用哪些工具/技能）。
    session_id/resume 用于断点续跑（checkpoint 落盘到 data/agent_sessions）。
    """
    print(f"[*] 正在指派任务至数字员工角色 [{agent_role}]: '{task_input}'")
    agent = Agent(role=agent_role)
    res = agent.run_task(task_input, session_id=session_id, resume=resume)

    print(f"\n[*] 任务 {res['task_id']} 最终状态: {res['status']}（{res['turns']} 轮，{res['stop_reason']}）")

    plan = res.get("plan") or []
    if plan:
        print("[*] 工具调用链:")
        for index, step in enumerate(plan, 1):
            args = json.dumps(step.get("arguments") or {}, ensure_ascii=False, default=str)
            print(f"    {index}. {step.get('tool')} {args[:160]}")

    if res["report"]:
        print(f"[*] 数字员工工作成果汇报:\n{res['report']}")


def _format_interval(seconds: int) -> str:
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60), ("s", 1)):
        if seconds % size == 0:
            return f"{seconds // size}{unit}"
    return f"{seconds}s"


def run_schedule(argv: list[str]) -> int:
    """`butler agent schedule` — 管理主动代理的周期任务。"""
    from butler.core.agent_scheduler import AgentScheduler

    parser = argparse.ArgumentParser(prog="butler agent schedule", description="主动代理定时任务")
    sub = parser.add_subparsers(dest="action")

    add_p = sub.add_parser("add", help="新增周期任务")
    add_p.add_argument("prompt", help="交给 Agent 的任务描述")
    add_p.add_argument("--every", required=True, help="间隔，如 30m / 2h / 1d")
    add_p.add_argument("--name", help="任务名")

    sub.add_parser("list", help="列出任务")

    remove_p = sub.add_parser("remove", help="删除任务")
    remove_p.add_argument("id")

    for action in ("enable", "disable"):
        switch = sub.add_parser(action, help=f"{action} 任务")
        switch.add_argument("id")

    run_p = sub.add_parser("run", help="立即执行一次")
    run_p.add_argument("id")

    daemon_p = sub.add_parser("daemon", help="前台运行调度循环")
    daemon_p.add_argument("--poll", type=float, default=30.0, help="轮询间隔秒数")

    args = parser.parse_args(argv)
    scheduler = AgentScheduler()

    if args.action == "add":
        try:
            job = scheduler.add(args.prompt, args.every, name=args.name)
        except ValueError as exc:
            print(f"添加失败: {exc}")
            return 2
        print(f"已添加任务 {job['id']}（每 {_format_interval(job['interval_seconds'])}）")
        return 0

    if args.action == "remove":
        print("已删除" if scheduler.remove(args.id) else "任务不存在")
        return 0

    if args.action in ("enable", "disable"):
        ok = scheduler.set_enabled(args.id, args.action == "enable")
        print("已更新" if ok else "任务不存在")
        return 0

    if args.action == "run":
        job = next((j for j in scheduler.list_jobs() if j["id"] == args.id), None)
        if not job:
            print("任务不存在")
            return 1
        result = scheduler.run_job(job)
        print(f"[{result['status']}] {result['output']}")
        return 0

    if args.action == "daemon":
        print(f"主动代理调度器启动，每 {args.poll:.0f}s 轮询；Ctrl+C 退出")
        scheduler.start(poll_seconds=args.poll)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop()
            print("已停止")
        return 0

    jobs = scheduler.list_jobs()
    if not jobs:
        print("还没有定时任务。用 butler agent schedule add \"任务\" --every 30m 创建。")
        return 0
    print(f"{'ID':<14}{'间隔':<8}{'状态':<6}{'下次执行':<22}任务")
    for job in jobs:
        nxt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(job["next_run"]))
        state = "启用" if job["enabled"] else "暂停"
        print(f"{job['id']:<14}{_format_interval(job['interval_seconds']):<8}{state:<6}{nxt:<22}{job['prompt'][:50]}")
    return 0
