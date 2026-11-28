"""
Dream 网格规划 (Grid Planning) — 论文附录 B.2 "Required next-cycle grid planning"。

探索策略在每个新的在线 rollout 之前调用 ``plan_grid(context)``，显式决定本轮
"开几条独立分支 × 每条分支允许多少次细化"。这与主论文的发现树是兼容的：
网格只是发现树的一个受限子空间（根的多条分支 = 并行工作区，链式细化 =
在同一工作区内反复修复候选）。

规划只允许使用 prefix-safe 事实：
- 已完成的在线轮次摘要（分支数、细化数、尝试数、最佳分），
- 回放轨迹的结构上限（trace 支持的分支/细化数），
- 硬上限与 worker 数。

不得读取当前 episode 的结果，也不得依赖具体 cell id / 绝对分数目标。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class GridPlan:
    """下一轮在线网格：分支数 W' 与每条分支允许的细化次数 R。"""

    branch_count: int
    refine_count: int
    reason: str = ""

    def __post_init__(self):
        if self.branch_count < 1:
            raise ValueError("branch_count 必须 ≥ 1")
        if self.refine_count < 0:
            raise ValueError("refine_count 必须 ≥ 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_count": self.branch_count,
            "refine_count": self.refine_count,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GridPlan":
        return cls(
            branch_count=_as_int(data.get("branch_count"), 1),
            refine_count=_as_int(data.get("refine_count"), 0),
            reason=str(data.get("reason", "")),
        )


@dataclass
class GridPlanningContext:
    """``plan_grid`` 可见的上下文（全部是上一轮之前的统计）。"""

    history: List[Dict[str, Any]] = field(default_factory=list)
    fallback_branch_count: int = 1
    fallback_refine_count: int = 0
    hard_max_branch_count: int = 1
    hard_max_refine_count: int = 0
    worker_cap: int = 1
    trace_branch_count: Optional[int] = None
    trace_refine_count: Optional[int] = None
    latest_best_score: Optional[float] = None
    previous_best_score: Optional[float] = None
    stalled_rounds: int = 0

    @property
    def improving(self) -> bool:
        if self.latest_best_score is None or self.previous_best_score is None:
            return False
        return self.latest_best_score > self.previous_best_score


def clamp_plan(plan: GridPlan, context: GridPlanningContext) -> GridPlan:
    """把规划裁剪到硬上限内，并保留原始 reason。"""
    branch = max(1, min(plan.branch_count, max(1, context.hard_max_branch_count)))
    refine = max(0, min(plan.refine_count,
                          max(0, context.hard_max_refine_count)))
    if branch == plan.branch_count and refine == plan.refine_count:
        return plan
    return GridPlan(branch, refine,
                    (plan.reason + "；已按硬上限裁剪").strip("；"))


def fallback_plan(context: GridPlanningContext) -> GridPlan:
    """没有策略规划能力时的保守兜底。"""
    branch = max(1, min(context.fallback_branch_count,
                        context.hard_max_branch_count))
    refine = max(0, min(context.fallback_refine_count,
                        context.hard_max_refine_count))
    return GridPlan(branch, refine, "策略未提供 plan_grid，使用运行器兜底网格")
