# -*- coding: utf-8 -*-
import sqlite3
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from butler.agent.context import AgentContext
from butler.agent.planner import Planner
from butler.agent.executor import Executor
from butler.agent.verifier import Verifier
from butler.package_runtime.loader import PackageLoader

logger = logging.getLogger(__name__)

class Agent:
    """
    Butler v2.0 Alpha 的核心主管数字员工（Single Agent Supervisor）。
    统一驱动核心任务生命周期：Task（任务输入） -> Intent（意图抽取） -> Plan（规划分解） -> Execute（调度执行） -> Verify（校验核对） -> Report（汇总报告）。
    任务的详细执行状态将同步保存在 SQLite 数据库的 `tasks` 表中。
    """
    def __init__(self, role: str = "supervisor", db_path: str = None, use_mock: bool = None):
        self.role = role

        if db_path is None:
            current_dir = Path(__file__).resolve().parent
            self.db_path = current_dir.parent / "data" / "system_data" / "long_memory.db"
        else:
            self.db_path = Path(db_path)

        self.planner = Planner(use_mock=use_mock)
        self.loader = PackageLoader(db_path=str(self.db_path))
        self.executor = Executor(package_loader=self.loader)
        self.verifier = Verifier()

    def _update_task_db(self, task_id: str, status: str, input_str: str, output_str: Optional[str] = None):
        """
        在 SQLite tasks 数据表中持久化、更新并保存任务状态及最终运行报告。
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO tasks (id, agent, status, input, output) VALUES (?, ?, ?, ?, ?)",
                    (task_id, self.role, status, input_str, output_str)
                )
            conn.close()
        except Exception as e:
            logger.error(f"在 SQLite 数据库中同步更新任务状态失败: {e}")

    def run_task(self, task_input: str) -> Dict[str, Any]:
        """
        同步启动、执行并驱动一轮完整的数字员工任务循环。
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        context = AgentContext(task_id, task_input)

        logger.info(f"[{self.role}] 正在初始化并启动任务 '{task_id}': {task_input}")
        self._update_task_db(task_id, "running", task_input)

        # 1. 任务规划阶段
        print(f"\n--- 【1】规划分解阶段: {task_input} ---")
        try:
            steps = self.planner.create_plan(task_input)
            context.plan_steps = steps
            print(f"成功生成有序规划（共 {len(steps)} 个子步骤）:")
            for s in steps:
                print(f"  - 步骤 {s.get('id')}: {s.get('action')} ({s.get('description')})")
        except Exception as e:
            logger.error(f"规划器运行失败: {e}")
            self._update_task_db(task_id, "failed", task_input, f"规划器运行异常: {e}")
            return {"task_id": task_id, "status": "failed", "error": str(e)}

        # 2. 调度执行及成果核对验证阶段
        print("\n--- 【2】调度执行与成果核对验证阶段 ---")
        overall_success = True
        for index, step in enumerate(steps):
            step_id = step.get("id")
            action = step.get("action")
            print(f"正在调起并执行步骤 {step_id}: {action}...")

            # 执行步骤
            res = self.executor.execute_step(step, context.execution_results)
            context.execution_results[step_id] = res

            # 核对结果
            verified = self.verifier.verify_step(step, res)
            if not verified:
                print(f"  ❌ 步骤 {step_id} 的产出未通过系统自动审查校验！")
                overall_success = False
                break

            print(f"  ✓ 步骤 {step_id} 执行并通过核对。")

        # 3. 最终汇总报告输出阶段
        print("\n--- 【3】汇总报告生成与输出阶段 ---")
        if overall_success:
            # 取最后一项步骤的输出报告，作为最终聚合输出
            last_step_id = steps[-1].get("id") if steps else None
            last_result = context.execution_results.get(last_step_id, {}) if last_step_id else {}
            final_output = last_result.get("result") or "任务已成功执行完成。"

            context.status = "completed"
            context.final_report = str(final_output)
            print(f"🏆 任务已完美执行成功！最终汇报如下:\n{final_output}")
            self._update_task_db(task_id, "completed", task_input, str(final_output))
        else:
            context.status = "failed"
            context.final_report = "步骤流转执行因结果未通过核对校验而中断。"
            print("❌ 任务执行失败！")
            self._update_task_db(task_id, "failed", task_input, "步骤流转执行因结果未通过核对校验而中断。")

        return {
            "task_id": task_id,
            "status": context.status,
            "plan": context.plan_steps,
            "results": context.execution_results,
            "report": context.final_report
        }

    def list_tasks(self) -> List[Dict[str, Any]]:
        """
        在 SQLite 数据库中检索并读取历史任务归档记录。
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT id, agent, status, input, output, created_at FROM tasks ORDER BY created_at DESC")
            rows = cursor.fetchall()
            conn.close()
            return [
                {
                    "id": r[0],
                    "agent": r[1],
                    "status": r[2],
                    "input": r[3],
                    "output": r[4],
                    "created_at": r[5]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"拉取 SQLite 历史任务归档失败: {e}")
            return []
