"""工作流意图 handler。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from butler.core.intent_dispatcher import register_intent

logger = logging.getLogger(__name__)


@register_intent("workflow_list", source="llm")
def handle_workflow_list(container, **kwargs) -> Any:
    """列出所有工作流。"""
    wf_engine = container.resolve("workflow_engine")
    return wf_engine.list_workflows()


@register_intent("workflow_create", source="llm")
def handle_workflow_create(container, entities: dict[str, Any], **kwargs) -> str:
    """创建一个新的 DAG 工作流。"""
    wf_engine = container.resolve("workflow_engine")
    nlu = container.resolve("nlu_service")

    steps = entities.get("steps")
    if isinstance(steps, str):
        gen_prompt = (
            "请将以下用户需求解析为 Butler DAG 工作流 JSON 结构。\n"
            "格式要求: list of objects with {id, intent, entities, depends_on: [list of ids]}\n\n"
            f"用户需求: {steps}"
        )
        steps_json = nlu.ask_llm(gen_prompt, use_habit=False)
        match = re.search(r"(\[.*\])", steps_json, re.DOTALL)
        if match:
            steps = json.loads(match.group(1))
        else:
            return "Error: 无法从 AI 响应中解析出工作流结构。"

    wf_id = wf_engine.create_workflow(entities.get("name", "AI 生成工作流"), steps)
    if entities.get("auto_start", True):
        wf_engine.execute_workflow(wf_id)
    return f"Workflow created: {wf_id}"
