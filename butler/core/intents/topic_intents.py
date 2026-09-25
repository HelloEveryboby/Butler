# -*- coding: utf-8 -*-
"""话题管理意图 handler（配合 butler/core/topic_manager.py）。

支持的说法（由动词识别引擎归一）：
  - "回到刚才的话题 / 我们说回之前那个"     → topic.recall
  - "我们聊过哪些话题 / 显示话题列表"       → topic.list
  - "把这个话题先存档 / 当前话题挂起一下"   → topic.save
  - "换个话题 / 开始一个新话题"             → topic.switch
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from butler.core.intent_dispatcher import register_intent
from butler.core.topic_manager import topic_manager


@register_intent("topic.recall", requires_entities=False)
def handle_topic_recall(entities: Optional[Dict[str, Any]] = None,
                        jarvis_app=None, **kwargs) -> str:
    """回到之前的话题并恢复其状态。"""
    query = (entities or {}).get("query", "")
    result = topic_manager.resume(str(query))
    if result.get("status") != "ok":
        return result.get("message", "没有找到可恢复的话题。")
    return f"已回到话题「{result['topic']}」：\n{result['snapshot']}"


@register_intent("topic.list", requires_entities=False)
def handle_topic_list(entities: Optional[Dict[str, Any]] = None,
                      jarvis_app=None, **kwargs) -> str:
    """列出最近的话题。"""
    items = topic_manager.list_topics(limit=8)
    if not items:
        return "目前还没有任何话题记录。"
    lines = []
    for t in items:
        mark = "● 当前" if t["status"] == "active" else "○ 已存档"
        lines.append(f"{mark} {t['id']}: {t['title']}")
    return "最近话题（说「回到XX」可恢复）：\n" + "\n".join(lines)


@register_intent("topic.save", requires_entities=False)
def handle_topic_save(entities: Optional[Dict[str, Any]] = None,
                      jarvis_app=None, **kwargs) -> str:
    """把当前话题挂起存档。"""
    topic = topic_manager.suspend_current()
    if topic is None:
        return "当前没有进行中的话题。"
    return f"已存档话题「{topic.title}」，说「回到{topic.title}」可随时恢复。"


@register_intent("topic.switch", requires_entities=False)
def handle_topic_switch(entities: Optional[Dict[str, Any]] = None,
                        jarvis_app=None, **kwargs) -> str:
    """切换到一个新话题。"""
    query = (entities or {}).get("query", "")
    event = topic_manager.observe(f"换个话题 {query}".strip())
    return event.get("message", "好的，我们聊点别的。")
