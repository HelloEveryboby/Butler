"""团队协作意图 handler。"""

from __future__ import annotations

from typing import Any

from butler.core.intent_dispatcher import register_intent


@register_intent("spawn_teammate", source="llm")
def handle_spawn_teammate(container, entities: dict[str, Any], **kwargs) -> str:
    """生成一个新的协作队友。"""
    team_mgr = container.resolve("team_manager")
    return team_mgr.spawn_teammate(
        entities.get("name"),
        entities.get("role"),
        entities.get("prompt"),
    )


@register_intent("list_teammates", source="llm")
def handle_list_teammates(container, **kwargs) -> str:
    """列出所有协作队友。"""
    team_mgr = container.resolve("team_manager")
    return team_mgr.list_teammates()


@register_intent("send_message", source="llm")
def handle_send_message(container, entities: dict[str, Any], **kwargs) -> str:
    """向指定队友发送消息。"""
    from butler.core.message_bus import message_bus
    return message_bus.send(
        "lead",
        entities.get("to"),
        entities.get("content"),
        entities.get("msg_type", "message"),
    )


@register_intent("read_inbox", source="llm")
def handle_read_inbox(container, **kwargs) -> Any:
    """读取收件箱中的消息。"""
    from butler.core.message_bus import message_bus
    return message_bus.read_inbox("lead")
