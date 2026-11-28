"""
Dream: Recursive Self-Improvement through Evolving Worlds（Butler 实现）。

论文映射（Zheng et al., Google/UMD/DeepMind）：
- 发现树 DiscoveryTree/DiscoveryForest      ← 论文 §3 "Discovery trees"
- 回放模拟器 ReplayView/replay_policy        ← 论文 §2 / §3 "Offline evaluation"
- 网格规划 GridPlan/GridPlanningContext      ← 论文附录 B.2 "Grid planning"
- beta 扫描 / Pareto BetaSweep                ← 论文附录 B.2 "Replay objective"
- 观察信号 signals（失败分类/成功锚点）      ← 论文附录 B.2 "Failure interpretation"
- 做梦 Dreamer/PolicyDeveloper               ← 论文 §3 "Policy improvement"
- 编排 DreamOrchestrator                     ← 论文 Figure 1 外层循环

核心思想：累积的发现历史是已实现搜索空间的回放模拟器；在回放中
"做梦"（零执行成本地评估成千上万个替代策略）→ 选出不退化的改进策略
→ 重部署在线探索 → 历史扩张 → 自我强化闭环。
"""

from .discovery_tree import DiscoveryForest, DiscoveryTree, Node
from .dreamer import (BetaSweep, BetaSweepPoint, Dreamer, DreamReport,
                      LLMDeveloper, ParametricDeveloper, PolicyDeveloper,
                      PolicyEvaluation)
from .grid import GridPlan, GridPlanningContext, clamp_plan, fallback_plan
from .orchestrator import AttemptResult, DreamConfig, DreamOrchestrator
from .policy import (AdaptivePolicy, ExplorationPolicy, ParallelRefinePolicy,
                     RandomPolicy, policy_from_dict)
from .replay import ReplayResult, ReplayView, replay_policy
from .signals import (branch_failed_hard, branch_promising, is_hard_failure,
                      is_repairable_failure, is_successful_observation,
                      probe_improved_vs_baseline, probe_improved_vs_parent,
                      successful_anchor)

__all__ = [
    "Node", "DiscoveryTree", "DiscoveryForest",
    "GridPlan", "GridPlanningContext", "clamp_plan", "fallback_plan",
    "ExplorationPolicy", "ParallelRefinePolicy", "AdaptivePolicy", "RandomPolicy",
    "policy_from_dict",
    "ReplayView", "ReplayResult", "replay_policy",
    "PolicyDeveloper", "ParametricDeveloper", "LLMDeveloper",
    "PolicyEvaluation", "BetaSweep", "BetaSweepPoint", "Dreamer", "DreamReport",
    "AttemptResult", "DreamConfig", "DreamOrchestrator",
    "is_successful_observation", "is_repairable_failure", "is_hard_failure",
    "successful_anchor", "branch_promising", "branch_failed_hard",
    "probe_improved_vs_parent", "probe_improved_vs_baseline",
]
