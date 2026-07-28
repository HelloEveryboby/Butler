"""任务管理意图 handler。从 _autonomous_agent_loop 的 if-elif 链中抽离。"""

from __future__ import annotations

from typing import Any

from butler.core.intent_dispatcher import register_intent


@register_intent("task_create", source="llm")
def handle_task_create(container, entities: dict[str, Any], **kwargs) -> str:
    """创建一个持久化业务任务。"""
    task_mgr = container.resolve("task_manager")
    subject = entities.get("subject", "未命名任务")
    description = entities.get("description", "")
    return task_mgr.create_business_task(subject, description)


@register_intent("task_update", source="llm")
def handle_task_update(container, entities: dict[str, Any], **kwargs) -> str:
    """更新任务状态或依赖关系。"""
    task_mgr = container.resolve("task_manager")
    return task_mgr.update_business_task(
        int(entities.get("task_id", 0)),
        entities.get("status"),
        entities.get("add_blocked_by"),
        entities.get("remove_blocked_by"),
    )


@register_intent("task_list", source="llm")
def handle_task_list(container, **kwargs) -> Any:
    """列出所有持久化业务任务。"""
    task_mgr = container.resolve("task_manager")
    return task_mgr.list_business_tasks()


@register_intent("claim_task", source="llm")
def handle_claim_task(container, entities: dict[str, Any], **kwargs) -> str:
    """认领一个业务任务。"""
    task_mgr = container.resolve("task_manager")
    return task_mgr.claim_business_task(int(entities.get("task_id", 0)), "lead")
