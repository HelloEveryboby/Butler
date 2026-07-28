"""
Butler 意图 handler 注册包。

导入此包会自动注册所有 LLM 意图 handler 到 intent_registry。
在 AgentLoop 初始化时导入此包即可激活所有意图。
"""

# 导入各 intent 模块以触发 @register_intent 装饰器注册
from butler.core.intents import (
    action_intents,  # noqa: F401
    cluster_intents,  # noqa: F401
    task_intents,  # noqa: F401
    team_intents,  # noqa: F401
    timemachine_intents,  # noqa: F401
    vault_intents,  # noqa: F401
    workflow_intents,  # noqa: F401
)

__all__ = [
    "task_intents",
    "vault_intents",
    "team_intents",
    "workflow_intents",
    "timemachine_intents",
    "cluster_intents",
    "action_intents",
]
