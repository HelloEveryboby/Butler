"""时光机意图 handler。"""

from __future__ import annotations

import time
from typing import Any

from butler.core.intent_dispatcher import register_intent


@register_intent("timemachine_query", source="llm")
def handle_timemachine_query(container, entities: dict[str, Any], **kwargs) -> Any:
    """查询指定时间点的系统快照。"""
    from butler.core.time_machine import time_machine
    ts = float(entities.get("timestamp", time.time()))
    return time_machine.get_snapshot_at(ts)


@register_intent("timemachine_range", source="llm")
def handle_timemachine_range(container, entities: dict[str, Any], **kwargs) -> Any:
    """查询时间范围内的系统快照。"""
    from butler.core.time_machine import time_machine
    return time_machine.get_range(
        float(entities.get("start")),
        float(entities.get("end")),
        entities.get("category"),
    )
