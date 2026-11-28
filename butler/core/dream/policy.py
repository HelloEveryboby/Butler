"""
Dream 探索策略 (Exploration Policy) — 论文 §3 与附录 B.2。

- 策略是"可执行代码"：每个决策轮从可继续节点集合选择批次 C ⊆ A(T;W)，|C| ≤ W；
  选择空批次 C = ∅ 即终止探索。
- 策略只观察"已揭示的子树 + 合法动作信息"，不观察未揭示节点的结果（回放约束）。
- 每个在线 rollout 前，策略通过 ``plan_grid(context)`` 显式规划本轮
  "分支数 × 每条分支的细化次数"（论文附录 B.2 的 next-cycle grid planning）。
- 做梦阶段只修订策略代码/参数；底层 discovery agent、evaluator、执行接口保持固定。

本模块提供：
- ParallelRefinePolicy：论文初始人工策略（多工作区并行细化）。
- AdaptivePolicy：参数化策略（网格 + beta 调度 + 失败分类），做梦阶段可修订。
- RandomPolicy：均匀随机基线（对照实验）。
"""

from __future__ import annotations

import copy
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .grid import (GridPlan, GridPlanningContext, clamp_plan, fallback_plan)
from .signals import (is_hard_failure, is_repairable_failure,
                      successful_anchor)


class ExplorationPolicy(ABC):
    """探索策略基类。所有状态必须可 reset()，保证回放确定性。"""

    name: str = "base"

    def __init__(self, seed: int = 0):
        self.seed = seed
        self._rng = random.Random(seed)
        self._active_plan: Optional[GridPlan] = None

    # ── 核心接口 ──

    @abstractmethod
    def select_batch(self, view, W: int, round_idx: int) -> List[str]:
        """从 view.eligible() 中选择一批可继续节点（≤ W 个）。

        返回空列表表示终止 rollout / replay。
        """

    def observe(self, revealed_nodes) -> None:
        """观察一轮中新揭示节点的结果（在线与回放统一回调）。"""

    def reset(self) -> None:
        """复位内部状态与随机源（每次回放从根开始前调用）。"""
        self._rng = random.Random(self.seed)

    # ── 网格规划（附录 B.2） ──

    def plan_grid(self, context: GridPlanningContext) -> GridPlan:
        """默认兜底：使用运行器提供的保守网格。"""
        return fallback_plan(context)

    def apply_plan(self, plan: GridPlan) -> None:
        """把本轮规划固定到策略上（在线与回放使用同一套选择逻辑）。"""
        self._active_plan = plan

    @property
    def active_plan(self) -> Optional[GridPlan]:
        return self._active_plan

    # ── 参数化修订接口（做梦调参 / LLM 策略开发） ──

    def get_params(self) -> Dict[str, Any]:
        return {"seed": self.seed}

    def set_params(self, params: Dict[str, Any]) -> None:
        for k, v in (params or {}).items():
            if k in self.get_params():
                setattr(self, k, v)
        self.reset()

    def clone(self) -> "ExplorationPolicy":
        return copy.deepcopy(self)

    def to_dict(self) -> dict:
        return {"name": self.name, "params": self.get_params()}


class ParallelRefinePolicy(ExplorationPolicy):
    """论文初始策略：多工作区并行细化。

    优先续细化得分最高的分支末端；并行额度未用满时由根开新分支。
    """

    name = "parallel_refine"

    def select_batch(self, view, W: int, round_idx: int) -> List[str]:
        eligible = view.eligible()
        if not eligible:
            return []
        leaves = [v for v in eligible if v != view.root_id]
        # 各分支末端按得分降序细化
        leaves.sort(key=lambda v: (view.node(v).score
                                   if view.node(v).score is not None
                                   else float("-inf")), reverse=True)
        batch = leaves[: max(0, W)]
        if len(batch) < W and view.root_id in eligible:
            batch.append(view.root_id)  # 额度剩余 → 开新分支
        return batch


class AdaptivePolicy(ParallelRefinePolicy):
    """参数化可修订策略：做梦阶段搜索的策略空间。

    参数：
    - beta [0.1,1]：探索耐心。高 beta = 更宽/更深/更弱剪枝；
      低 beta = 更少 probe、更早停滞停止、更强剪枝（附录 B.2）。
    - branch_count：每轮打开的独立分支（工作区）数；0 = 由 plan_grid 自适应。
    - refine_count：每条分支在首次尝试后允许的细化次数；-1 = 自适应。
    - explore_weight [0,1]：无网格规划时的开新分支倾向（兼容旧行为）。
    - refine_bias [-1,1]：≥0 偏好细化高分分支（利用）；<0 偏好低分分支（探索）。
    - batch_fill (0,1]：每个决策轮使用并行额度的比例。
    - stop_threshold：已揭示最佳得分达到即停（空批次终止）。
    """

    name = "adaptive"

    def __init__(self, seed: int = 0,
                 beta: float = 0.6,
                 branch_count: int = 0,
                 refine_count: int = -1,
                 explore_weight: float = 0.3,
                 refine_bias: float = 0.5,
                 batch_fill: float = 1.0,
                 stop_threshold: float = float("inf")):
        super().__init__(seed=seed)
        self.beta = beta
        self.branch_count = branch_count
        self.refine_count = refine_count
        self.explore_weight = explore_weight
        self.refine_bias = refine_bias
        self.batch_fill = batch_fill
        self.stop_threshold = stop_threshold

    def get_params(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "beta": self.beta,
            "branch_count": self.branch_count,
            "refine_count": self.refine_count,
            "explore_weight": self.explore_weight,
            "refine_bias": self.refine_bias,
            "batch_fill": self.batch_fill,
            "stop_threshold": self.stop_threshold,
        }

    def set_params(self, params: Dict[str, Any]) -> None:
        super().set_params(self._normalize(params))
        self._active_plan = None

    @staticmethod
    def _normalize(params: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(params or {})
        if "beta" in out:
            out["beta"] = max(0.1, min(1.0, float(out["beta"])))
        if "branch_count" in out:
            out["branch_count"] = max(0, min(64, int(round(float(out["branch_count"])))))
        if "refine_count" in out:
            out["refine_count"] = max(-1, min(64, int(round(float(out["refine_count"])))))
        if "explore_weight" in out:
            out["explore_weight"] = max(0.0, min(1.0, float(out["explore_weight"])))
        if "refine_bias" in out:
            out["refine_bias"] = max(-1.0, min(1.0, float(out["refine_bias"])))
        if "batch_fill" in out:
            out["batch_fill"] = max(0.1, min(1.0, float(out["batch_fill"])))
        return out

    # ── 网格规划 ──

    def plan_grid(self, context: GridPlanningContext) -> GridPlan:
        """依据 beta 与上一轮趋势给出本轮网格，并显式说明理由。"""
        adjust = 0
        trend = "历史不足"
        if context.stalled_rounds >= 2:
            adjust = 1
            trend = "连续 %d 轮停滞，增加探索宽度与耐心" % context.stalled_rounds
        elif context.improving:
            adjust = -1
            trend = "上一轮仍有提升，节省计算并收紧搜索"

        if self.beta >= 0.75:
            adjust += 1
        elif self.beta <= 0.35:
            adjust -= 1

        if self.branch_count > 0:
            branch = self.branch_count
            branch_reason = "显式 branch_count"
        else:
            branch = max(1, context.fallback_branch_count + adjust)
            branch_reason = "自适应 branch_count"

        if self.refine_count >= 0:
            refine = self.refine_count
            refine_reason = "显式 refine_count"
        else:
            refine = max(0, context.fallback_refine_count + adjust)
            refine_reason = "自适应 refine_count"

        plan = GridPlan(
            branch_count=branch,
            refine_count=refine,
            reason=(f"beta={self.beta:.2f}；{trend}；{branch_reason}；"
                    f"{refine_reason}"),
        )
        return clamp_plan(plan, context)

    # ── 批次选择 ──

    def select_batch(self, view, W: int, round_idx: int) -> List[str]:
        if self._active_plan is not None:
            return self._grid_select(view, W, round_idx, self._active_plan)
        return self._legacy_select(view, W, round_idx)

    def _legacy_select(self, view, W: int, round_idx: int) -> List[str]:
        """未规划网格时的兼容行为（旧版 AdaptivePolicy）。"""
        eligible = view.eligible()
        if not eligible:
            return []
        if view.best_score() is not None and view.best_score() >= self.stop_threshold:
            return []  # 达标即停（C = ∅ 终止）

        n = max(1, int(round(W * self.batch_fill)))
        n = min(n, W, len(eligible))

        leaves = [v for v in eligible if v != view.root_id]
        def sort_key(v):
            s = view.node(v).score
            s = 0.0 if s is None else s
            return self.refine_bias * s + self._rng.random() * 1e-6
        leaves.sort(key=sort_key, reverse=True)

        batch: List[str] = list(leaves[:n])
        if len(batch) < n and view.root_id in eligible:
            if self._rng.random() < max(0.0, min(1.0, self.explore_weight)) or not batch:
                batch.append(view.root_id)
        return batch[:n]

    def _grid_select(self, view, W: int, round_idx: int,
                     plan: GridPlan) -> List[str]:
        if view.best_score() is not None and view.best_score() >= self.stop_threshold:
            return []

        cap = max(1, min(W, int(round(W * self.batch_fill))))
        opened = view.opened_branch_ids()
        roots_needed = max(0, plan.branch_count - len(opened))
        batch: List[str] = [view.root_id] * min(roots_needed, cap)

        remaining = cap - len(batch)
        if remaining <= 0:
            return batch

        candidates = []
        for bid in opened:
            leaf_id = view.leaf_of_branch(bid)
            if leaf_id is None:
                continue
            local_depth = view.local_depth(leaf_id)
            if local_depth >= plan.refine_count:
                continue  # 该分支已用完细化额度
            node = view.node(leaf_id)
            traj = view.branch_nodes(bid)
            if is_hard_failure(node) and successful_anchor(traj) is None:
                continue
            score = node.score if node.score is not None else float("-inf")
            prev = traj[-2].score if len(traj) >= 2 else None
            progress = ((score - prev) if (prev is not None and
                                           score != float("-inf")) else 0.0)
            # beta 高 → 更愿意给浅层/未充分探索的分支机会
            explore_bonus = self.beta * (1.0 - local_depth / max(1, plan.refine_count))
            priority = (self.refine_bias * score
                        + (1.0 - abs(self.refine_bias)) * progress
                        + explore_bonus)
            if is_repairable_failure(node):
                priority -= (1.0 - self.beta) * max(1.0, abs(score))
            candidates.append((priority, local_depth, leaf_id,
                               is_repairable_failure(node)))

        candidates.sort(key=lambda x: (x[0], -x[1]), reverse=True)
        recovery_used = False
        for _prio, _depth, leaf_id, repairable in candidates:
            if repairable:
                if recovery_used:
                    continue
                recovery_used = True
            batch.append(leaf_id)
            if len(batch) >= cap:
                break
        return batch[:W]


class RandomPolicy(ExplorationPolicy):
    """均匀随机基线（对照实验用）。"""

    name = "random"

    def select_batch(self, view, W: int, round_idx: int) -> List[str]:
        eligible = view.eligible()
        if not eligible:
            return []
        n = min(W, len(eligible))
        return self._rng.sample(eligible, n)


POLICY_REGISTRY = {
    "parallel_refine": ParallelRefinePolicy,
    "adaptive": AdaptivePolicy,
    "random": RandomPolicy,
}


def policy_from_dict(data: Dict[str, Any]) -> ExplorationPolicy:
    """从持久化的 {name, params} 恢复策略（未知类型回退为 AdaptivePolicy）。"""
    name = (data or {}).get("name", "adaptive")
    params = dict((data or {}).get("params", {}) or {})
    cls = POLICY_REGISTRY.get(name, AdaptivePolicy)
    seed = int(params.pop("seed", 0) or 0)
    allowed = cls(seed=seed).get_params()
    filtered = {k: v for k, v in params.items() if k in allowed and k != "seed"}
    policy = cls(seed=seed)
    if filtered:
        policy.set_params(filtered)
    return policy
