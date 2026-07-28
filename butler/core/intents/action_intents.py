"""动作桥接与上下文管理意图 handler。"""

from __future__ import annotations

from typing import Any

from butler.core.intent_dispatcher import register_intent


@register_intent("call_api", source="llm")
def handle_call_api(container, entities: dict[str, Any], **kwargs) -> Any:
    """调用外部 API。"""
    from butler.core.action_bridge import action_bridge

    return action_bridge.call_api(
        url=entities.get("url"),
        method=entities.get("method", "POST"),
        data=entities.get("data"),
        headers=entities.get("headers"),
    )


@register_intent("trigger_webhook", source="llm")
def handle_trigger_webhook(container, entities: dict[str, Any], **kwargs) -> Any:
    """触发一个已注册的 webhook。"""
    from butler.core.action_bridge import action_bridge

    return action_bridge.trigger_webhook(
        name=entities.get("name"),
        payload=entities.get("payload"),
        config=entities.get("config", {}),
    )


@register_intent("skill_install", source="llm")
def handle_skill_install(container, entities: dict[str, Any], **kwargs) -> Any:
    """安装一个新技能。"""
    skill_manager = container.resolve("skill_manager")
    return skill_manager.execute(
        "manage_skills", "install", entities=entities, jarvis_app=container.resolve("app")
    )


@register_intent("skill_import", source="llm")
def handle_skill_import(container, entities: dict[str, Any], **kwargs) -> Any:
    """导入一个外部技能包。"""
    skill_manager = container.resolve("skill_manager")
    return skill_manager.execute(
        "manage_skills", "import", entities=entities, jarvis_app=container.resolve("app")
    )


@register_intent("compress", source="llm")
def handle_compress(container, entities: dict[str, Any], **kwargs) -> str:
    """压缩对话上下文以释放 token 空间。"""
    nlu_service = container.resolve("nlu_service")
    messages = entities.get("messages", [])
    nlu_service.compress_history(messages)
    return "Context compressed."


@register_intent("xlsx_expert", source="llm")
def handle_xlsx_expert(container, entities: dict[str, Any], **kwargs) -> Any:
    """使用代码解释器处理 Excel 相关任务。"""
    app = container.resolve("app")
    command = entities.get("command", "")
    app._execute_with_llm_interpreter(command)
    return "xlsx_expert via interpreter"


@register_intent("pdf_assistant", source="llm")
def handle_pdf_assistant(container, entities: dict[str, Any], **kwargs) -> Any:
    """使用代码解释器处理 PDF 相关任务。"""
    app = container.resolve("app")
    command = entities.get("command", "")
    app._execute_with_llm_interpreter(command)
    return "pdf_assistant via interpreter"
