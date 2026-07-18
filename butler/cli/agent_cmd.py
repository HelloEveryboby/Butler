# -*- coding: utf-8 -*-
from butler.package_runtime.loader import PackageLoader
from butler.agent.agent import Agent

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

def run_agent_task(agent_role: str, task_input: str):
    """
    指派并运行某个指定角色的数字员工任务。
    """
    print(f"[*] 正在指派任务至数字员工角色 [{agent_role}]: '{task_input}'")
    agent = Agent(role=agent_role)
    res = agent.run_task(task_input)
    print(f"\n[*] 任务运行最终状态: {res['status']}")
    if res['report']:
        print(f"[*] 数字员工工作成果汇报:\n{res['report']}")
