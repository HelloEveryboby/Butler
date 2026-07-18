# -*- coding: utf-8 -*-
from butler.agent.agent import Agent

def list_agents():
    print("\n==============================================")
    print("            可用的 Butler 数字员工角色        ")
    print("==============================================")
    print("🤖 角色: supervisor         | 角色定义: 主管员工 (系统内置)")
    print("==============================================\n")

def run_agent_task(agent_role: str, task_input: str):
    print("Thinking...\n")
    print("Plan created\n")
    print("Executing tools...\n")
    agent = Agent()
    res = agent.run_task(task_input)
    print("\nCompleted\n")
    print("Report generated")
