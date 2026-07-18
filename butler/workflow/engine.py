# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any, Optional
from butler.workflow.parser import WorkflowParser
from butler.workflow.state import WorkflowState
from butler.package_runtime.loader import PackageLoader
from butler.agent.executor import Executor

logger = logging.getLogger(__name__)

class WorkflowEngine:
    """
    负责依次解析、调用并运行轻量级 YAML 自动化工作流。
    工作流中声明的步骤可以直接匹配已安装的技能，或优雅降级到拟真 Mock。
    """
    def __init__(self, loader: Optional[PackageLoader] = None):
        self.loader = loader or PackageLoader()
        self.executor = Executor(package_loader=self.loader)

    def execute_workflow(self, yaml_str: str) -> Dict[str, Any]:
        """
        解析并运行一段用 YAML 定义的自动化任务工作流。
        """
        try:
            wf_data = WorkflowParser.parse_string(yaml_str)
        except Exception as e:
            return {"status": "FAILED", "error": f"工作流语法解析错误: {e}"}

        name = wf_data["name"]
        steps = wf_data["steps"]

        logger.info(f"开始运行自动化工作流: {name}")
        state = WorkflowState(name, steps)
        state.start()

        previous_results = {}

        for idx, step in enumerate(steps):
            # 解析单步定义模式
            # 例如: - skill: { name: email-reader }
            skill_info = step.get("skill")
            if not skill_info or not isinstance(skill_info, dict):
                state.fail_step(idx, f"不合法的步骤配置 schema: {step}")
                break

            skill_name = skill_info.get("name")
            if not skill_name:
                state.fail_step(idx, "步骤配置中缺少 skill name。")
                break

            print(f"工作流 [{name}] 正在执行步骤 {idx+1}/{len(steps)}: {skill_name}")

            # 为执行器构建单步标准调用参数
            step_dict = {
                "id": str(idx + 1),
                "action": skill_name,
                "input": skill_info.get("input", {})
            }

            # 如果不是第一步，且没有显式指定入参源，默认将前一步的产出传入当前步骤
            if idx > 0 and "source_step" not in step_dict["input"]:
                step_dict["input"]["source_step"] = str(idx)

            try:
                # 调用统一 Executor 执行该动作
                res = self.executor.execute_step(step_dict, previous_results)

                if res.get("status") == "failed":
                    state.fail_step(idx, res.get("error", "未知的执行异常。"))
                    break

                output_val = res.get("result") or res
                state.complete_step(idx, output_val)
                previous_results[str(idx + 1)] = res

            except Exception as ex:
                state.fail_step(idx, str(ex))
                break

        print(f"工作流 [{name}] 运行结束，最终状态为: {state.status}")

        # 获取最末一步的输出成果
        final_out = state.step_outputs.get(len(steps) - 1) if state.status == "SUCCESS" else None

        return {
            "workflow_name": name,
            "status": state.status,
            "step_outputs": state.step_outputs,
            "errors": state.errors,
            "final_output": final_out
        }
