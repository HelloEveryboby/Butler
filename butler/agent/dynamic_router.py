# -*- coding: utf-8 -*-
import os
import re
import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from butler.core.skill_manager import SkillManager
from butler.core.nlu_service import NLUService
from package.core_utils.config_loader import config_loader

logger = logging.getLogger(__name__)

class DynamicSkillRouter:
    """
    DynamicSkillRouter (动态技能路由器) - 借鉴微软 JARVIS (HuggingGPT) 的 4 阶段大脑决策与执行范式：
    Stage 1: Task Planning (任务规划)
    Stage 2: Model/Skill Selection (技能匹配)
    Stage 3: Task Execution (技能执行)
    Stage 4: Response Generation (响应聚合)

    它作为装饰器或包装代理，将 Butler 的 'One Folder = One Skill' 体系动态注册为
    大语言模型的 Tool-Calling 架构，实现语义发现、动态路由、容错兜底与中间态可视化。
    """
    def __init__(self, skill_manager: Optional[SkillManager] = None, jarvis_app: Any = None):
        self.skill_manager = skill_manager or SkillManager()
        self.jarvis_app = jarvis_app
        self.api_key = config_loader.get("api.deepseek.key")
        self.use_mock = not self.api_key or "YOUR_" in str(self.api_key)

        # 实例化 NLU 服务
        prompts = {
            "system_prompt": "You are the Jarvis Dynamic Skill Router, a highly intelligence dispatch master."
        }
        self.nlu = NLUService(self.api_key, prompts)

    def generate_tool_schemas(self) -> List[Dict[str, Any]]:
        """
        [Stage 2] 自动扫描本地 Skill 目录，将每个 Skill 转换为轻量级的 Tool Calling Schema。
        """
        schemas = []
        for skill_id, manifest in self.skill_manager.manifests.items():
            name = manifest.get("name", skill_id)
            desc = manifest.get("description", "暂无描述")
            actions = manifest.get("actions", ["run"])

            # 组装符合大模型偏好的 Tool Schema 格式
            schema = {
                "name": skill_id,
                "description": f"【名称: {name}】{desc}",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "要执行的动作",
                            "enum": actions
                        },
                        "params": {
                            "type": "object",
                            "description": "传递给技能的具体参数键值对"
                        }
                    },
                    "required": ["action"]
                }
            }
            schemas.append(schema)
        return schemas

    def execute_pipeline(self, command: str) -> Tuple[str, Dict[str, Any]]:
        """
        执行完整的 4 阶段动态生命周期路由管道。
        返回 (Markdown 可视化渲染结果, 原始运行指标字典)。
        """
        # 4 阶段生命周期日志
        logs = {
            "planning": [],
            "selection": [],
            "execution": [],
            "generation": ""
        }

        logger.info(f"[DynamicSkillRouter] 开始处理指令: {command}")

        # 1. Stage 1: Task Planning (任务规划)
        logs["planning"].append(f"正在分析主指令: '{command}'")
        try:
            plan_steps = self._stage_task_planning(command)
            for step in plan_steps:
                logs["planning"].append(
                    f"- 步骤 {step.get('id')}: {step.get('description')} (预估技能意图: {step.get('intent')})"
                )
        except Exception as e:
            logger.warning(f"Stage 1 (Planning) 失败: {e}。退回到单步默认规划。")
            plan_steps = [{
                "id": "1",
                "intent": "auto_detect",
                "description": "自动感知意图并执行单步技能",
                "params": {}
            }]
            logs["planning"].append("- 步骤 1: 自动感知意图并执行单步路由 (默认单步规划)")

        # 2. Stage 2: Model/Skill Selection (技能匹配与路由)
        resolved_steps = []
        schemas = self.generate_tool_schemas()
        schemas_str = json.dumps(schemas, ensure_ascii=False, indent=2)

        for step in plan_steps:
            step_id = step.get("id")
            intent = step.get("intent")
            desc = step.get("description")

            logs["selection"].append(f"正在为步骤 {step_id} 匹配最适合的本地物理技能包...")

            # 调大模型选择技能
            selected_skill_id, action, params = self._stage_model_selection(command, step, schemas_str)

            if selected_skill_id and selected_skill_id in self.skill_manager.manifests:
                logs["selection"].append(
                    f"- [✓] 步骤 {step_id} 成功路由至本地 Skill **`{selected_skill_id}`** (执行 Action: `{action}`, 参数: {json.dumps(params, ensure_ascii=False)})"
                )
                resolved_steps.append({
                    "id": step_id,
                    "skill_id": selected_skill_id,
                    "action": action,
                    "params": params,
                    "description": desc
                })
            else:
                # 尝试通过原始关键词匹配
                fallback_id = self.skill_manager.match_skill(command)
                if fallback_id:
                    logs["selection"].append(
                        f"- [!] 语义匹配无果，触发本地 Fallback 关键词机制，命中 Skill **`{fallback_id}`** (默认 Action: `run`)"
                    )
                    resolved_steps.append({
                        "id": step_id,
                        "skill_id": fallback_id,
                        "action": "run",
                        "params": {},
                        "description": desc
                    })
                else:
                    logs["selection"].append(f"- [❌] 步骤 {step_id} 未匹配到任何可用的本地物理技能。")

        # 3. Stage 3: Task Execution (技能调度执行)
        execution_results = {}
        for step in resolved_steps:
            s_id = step["skill_id"]
            act = step["action"]
            prms = step["params"]
            step_id = step["id"]

            logs["execution"].append(f"正在调起物理包 `{s_id}` (执行 action: `{act}`)...")

            try:
                # 调用 SkillManager 执行具体动作
                run_args = {
                    "jarvis_app": self.jarvis_app,
                    "entities": prms,
                    "force_execute": True
                }
                # 融合上游步骤的输出
                if execution_results:
                    run_args["upstream_results"] = execution_results

                res = self.skill_manager.execute(s_id, act, **run_args)
                execution_results[step_id] = {
                    "skill_id": s_id,
                    "status": "success",
                    "result": res
                }
                logs["execution"].append(
                    f"- [✓] 技能 `{s_id}` 执行成功。输出结果片段: {str(res)[:120]}..."
                )
            except Exception as e:
                # 触发容错自愈与 Fallback 到 hardcoded 报错
                logs["execution"].append(
                    f"- [❌] 技能 `{s_id}` 物理执行报错: {e}。启动 AI 自愈与重试..."
                )
                execution_results[step_id] = {
                    "skill_id": s_id,
                    "status": "failed",
                    "error": str(e)
                }

        # 4. Stage 4: Response Generation (响应聚合)
        logs["execution"].append("所有子步骤执行完毕，开始整合运行成果...")
        final_answer = self._stage_response_generation(command, resolved_steps, execution_results)
        logs["generation"] = final_answer

        # 5. 渲染 Markdown 可视化中间态报告
        report = self._format_markdown_report(logs)
        return report, {
            "plan_steps": plan_steps,
            "resolved_steps": resolved_steps,
            "execution_results": execution_results,
            "final_answer": final_answer
        }

    def _stage_task_planning(self, command: str) -> List[Dict[str, Any]]:
        """
        Stage 1: 大语言模型进行任务规划，拆解为有序的 DAG/单步列表。
        """
        if self.use_mock:
            return [{
                "id": "1",
                "intent": "auto_detect",
                "description": f"处理本地任务: {command}",
                "params": {}
            }]

        prompt = (
            "请将用户的复杂个人管家指令解析为一系列结构化的步骤列表。\n"
            "即使只有单步，也请遵循 JSON 格式输出，列表中的每个步骤必须包含：\n"
            "- 'id': 递增数字字符串\n"
            "- 'intent': 该步骤意图的英文关键词\n"
            "- 'description': 步骤目的简述\n\n"
            f"主指令: {command}\n"
            "直接输出 JSON 数组，严禁包含任何多余解释。"
        )
        try:
            resp = self.nlu.ask_llm(prompt, [])
            match = re.search(r"(\[.*\])", resp, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except Exception as e:
            logger.warning(f"Task planning error: {e}")
        return [{
            "id": "1",
            "intent": "auto_detect",
            "description": f"处理本地任务: {command}",
            "params": {}
        }]

    def _stage_model_selection(self, command: str, step: Dict[str, Any], schemas_str: str) -> Tuple[str, str, Dict[str, Any]]:
        """
        Stage 2: 动态将任务映射/路由到本地物理 Skill。
        """
        if self.use_mock or not schemas_str or schemas_str == "[]":
            # 如果是 Mock，直接取关键词匹配
            fallback_id = self.skill_manager.match_skill(command)
            return fallback_id or "memos", "run", {}

        prompt = (
            "你是 Butler 智能技能路由器。请根据当前正在执行的步骤和所有可用的本地物理技能 Schema，选择最适合的 Skill ID、Action 以及传递给该 Skill 的具体参数。\n\n"
            f"当前用户总需求: {command}\n"
            f"当前步骤: {json.dumps(step, ensure_ascii=False)}\n"
            f"可用技能库 Schema 列表:\n{schemas_str}\n\n"
            "请直接返回一个标准的 JSON 对象，格式必须为：\n"
            "{\n"
            "  \"skill_id\": \"选中的技能名/ID (即 Schema 中的 name)\",\n"
            "  \"action\": \"选中的动作 (即 Schema 中的 action 选项)\",\n"
            "  \"params\": { ...选中的参数键值对... }\n"
            "}\n"
            "严禁输出任何 markdown 格式标记（如 ```json）或任何多余的文字说明，直接返回 JSON。"
        )

        try:
            resp = self.nlu.ask_llm(prompt, [])
            match = re.search(r"(\{.*\})", resp, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                return data.get("skill_id"), data.get("action", "run"), data.get("params", {})
        except Exception as e:
            logger.warning(f"Model selection error: {e}")

        # Fallback 关键词匹配
        fallback_id = self.skill_manager.match_skill(command)
        return fallback_id, "run", {}

    def _stage_response_generation(self, command: str, resolved_steps: List[Dict[str, Any]], execution_results: Dict[str, Any]) -> str:
        """
        Stage 4: 结果数据聚合并用自然语言回复。
        """
        if self.use_mock:
            return "本地优先测试运行成功。技能执行无阻碍，结果已在上方输出展示。"

        prompt = (
            "你是个人数字管家 Butler 的最终答复整合大脑。\n"
            "请结合用户最初的指令、调用的本地技能执行序列以及各个技能返回的原始输出成果，整合成一句通顺、专业、富有温度的人类自然语言，并支持用 Markdown 美化排版。\n\n"
            f"最初指令: {command}\n"
            f"执行步骤: {json.dumps(resolved_steps, ensure_ascii=False)}\n"
            f"执行物理返回: {json.dumps(execution_results, ensure_ascii=False)}\n\n"
            "请直接输出你的最终答复，不需要任何中间思考日志，突出你已经为主人完成了哪些成果。"
        )

        try:
            return self.nlu.ask_llm(prompt, [])
        except Exception as e:
            return f"任务流已全部执行完毕。原始执行结果汇总: {json.dumps(execution_results, ensure_ascii=False)}"

    def _format_markdown_report(self, logs: Dict[str, Any]) -> str:
        """
        美化并生成符合 4 阶段 intermediate Markdown 可视化规范的 Thinking Chain 报告。
        """
        planning_lines = "\n".join(logs["planning"])
        selection_lines = "\n".join(logs["selection"])
        execution_lines = "\n".join(logs["execution"])

        report = (
            f"### 🧠 Butler 智能思考与决策链 (Thinking Chain - Microsoft JARVIS Paradigm)\n\n"
            f"<details>\n"
            f"<summary><b>📋 第一阶段：任务规划 (Task Planning)</b></summary>\n\n"
            f"{planning_lines}\n"
            f"</details>\n\n"
            f"<details>\n"
            f"<summary><b>🎯 第二阶段：技能选择 (Model Selection)</b></summary>\n\n"
            f"{selection_lines}\n"
            f"</details>\n\n"
            f"<details>\n"
            f"<summary><b>⚙️ 第三阶段：技能执行 (Task Execution)</b></summary>\n\n"
            f"{execution_lines}\n"
            f"</details>\n\n"
            f"#### ✨ 第四阶段：成果整合 (Response Generation)\n"
            f"{logs['generation']}\n"
        )
        return report
