# -*- coding: utf-8 -*-
from butler.agent.planner import Planner
from butler.agent.executor import Executor
from butler.agent.verifier import Verifier

class Agent:
    def __init__(self, planner=None, executor=None, verifier=None):
        self.planner = planner or Planner()
        self.executor = executor or Executor()
        self.verifier = verifier or Verifier()

    def run(self, task):
        print("Intent")
        plan = self.planner.create(task)

        print("Plan")
        result = self.executor.execute(plan)

        print("Execute")
        verified = self.verifier.check(result)

        print("Verify")
        if verified:
            print("Complete")
        return verified

    def run_task(self, task_input: str):
        res = self.run(task_input)
        return {
            "status": "completed" if res else "failed",
            "report": "任务已成功执行完成。" if res else "步骤流转执行因结果未通过核对校验而中断。"
        }
