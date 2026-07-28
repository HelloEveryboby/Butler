"""集群管理意图 handler。"""

from __future__ import annotations

from typing import Any

from butler.core.intent_dispatcher import register_intent


@register_intent("cluster_list", source="llm")
def handle_cluster_list(container, **kwargs) -> Any:
    """列出局域网内所有已发现的集群节点。"""
    from butler.core.cluster_manager import cluster_manager
    return cluster_manager.list_nodes()


@register_intent("cluster_execute", source="llm")
def handle_cluster_execute(container, entities: dict[str, Any], **kwargs) -> Any:
    """在指定远程节点上执行技能。"""
    from butler.core.cluster_manager import cluster_manager
    return cluster_manager.execute_remote(
        entities.get("node_id"),
        entities.get("skill_id"),
        entities.get("action", "run"),
        entities.get("payload", {}),
    )
