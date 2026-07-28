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
