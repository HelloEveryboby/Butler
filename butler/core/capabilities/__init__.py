"""核心能力注册表。

与 ``skills`` 明确分工：
  - 技能：可插拔、可热加载、第三方可提供的扩展
  - 能力：Butler 自带的五项核心生产力功能，直接调度 core 服务
"""

from __future__ import annotations

from . import builtin
from .registry import CapabilityRegistry, CapabilitySpec, capability_registry

builtin.register_builtin_capabilities()
register_builtin_capabilities = builtin.register_builtin_capabilities

__all__ = [
    "CapabilityRegistry",
    "CapabilitySpec",
    "capability_registry",
    "register_builtin_capabilities",
]
