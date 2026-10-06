"""
Dream: Recursive Self-Improvement through Evolving Worlds（Butler 实现）。

论文映射（Zheng et al., Google/UMD/DeepMind）：
- 发现树 DiscoveryTree/DiscoveryForest      ← 论文 §3 "Discovery trees"
- 回放模拟器 ReplayView/replay_policy        ← 论文 §2 / §3 "Offline evaluation"
- 做梦 Dreamer/PolicyDeveloper               ← 论文 §3 "Policy improvement"
- 编排 DreamOrchestrator                  ← 论文 Figure 1 外层循环

核心思想：累积的发现历史是已实现搜索空间的回放模拟器；在回放中
"做梦"（零执行成本地评估成千上万个替代策略）→ 选出不退化的改进策略
→ 重部署在线探索 → 历史扩张 → 自我强化闭环。
"""

from .discovery_tree import DiscoveryForest, DiscoveryTree, Node
from .dreamer import (Dreamer, DreamReport, LLMDeveloper, ParametricDeveloper,
                      PolicyDeveloper, PolicyEvaluation)
from .orchestrator import AttemptResult, DreamOrchestrator, DreamConfig
from .policy import (AdaptivePolicy, ExplorationPolicy, ParallelRefinePolicy,
                     RandomPolicy)
from .replay import ReplayResult, ReplayView, replay_policy

__all__ = [
    "Node", "DiscoveryTree", "DiscoveryForest",
    "ExplorationPolicy", "ParallelRefinePolicy", "AdaptivePolicy", "RandomPolicy",
    "ReplayView", "ReplayResult", "replay_policy",
    "PolicyDeveloper", "ParametricDeveloper", "LLMDeveloper",
    "PolicyEvaluation", "Dreamer", "DreamReport",
    "AttemptResult", "DreamConfig", "DreamOrchestrator",
]
