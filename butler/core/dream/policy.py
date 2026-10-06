"""
Dream 探索策略 (Exploration Policy) — 论文 §3。

- 策略是"可执行代码"：每个决策轮从可继续节点集合选择批次 C ⊆ A(T;W)，|C| ≤ W；
  选择空批次 C = ∅ 即终止探索。
- 策略只观察"已揭示的子树 + 合法动作信息"，不观察未揭示节点的结果（回放约束）。
- 做梦阶段只修订策略代码/参数；底层 discovery agent、evaluator、执行接口保持固定。

本模块提供三个策略：
- ParallelRefinePolicy：论文使用的初始人工策略（多工作区并行细化）。
- AdaptivePolicy：参数化策略，做梦阶段对其参数做程序化修订（无 LLM 回退路径）。
- RandomPolicy：均匀随机基线（用于对照实验）。
"""

from __future__ import annotations

import copy
import random
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ExplorationPolicy(ABC):
    """探索策略基类。所有状态必须可 reset()，保证回放确定性。"""

    name: str = "base"

    def __init__(self, seed: int = 0):
        self.seed = seed
        self._rng = random.Random(seed)

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
    - explore_weight [0,1]：开新分支（根）的倾向权重。
    - refine_bias   [-1,1]：≥0 偏好细化高分分支（利用）；<0 偏好低分分支（探索）。
    - batch_fill   (0,1]：每个决策轮使用并行额度的比例（并行度 vs 代价的权衡）。
    - stop_threshold: 已揭示最佳得分达到即停（空批次终止）。
    """

    name = "adaptive"

    def __init__(self, seed: int = 0,
                 explore_weight: float = 0.3,
                 refine_bias: float = 0.5,
                 batch_fill: float = 1.0,
                 stop_threshold: float = float("inf")):
        super().__init__(seed=seed)
        self.explore_weight = explore_weight
        self.refine_bias = refine_bias
        self.batch_fill = batch_fill
        self.stop_threshold = stop_threshold

    def get_params(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "explore_weight": self.explore_weight,
            "refine_bias": self.refine_bias,
            "batch_fill": self.batch_fill,
            "stop_threshold": self.stop_threshold,
        }

    def select_batch(self, view, W: int, round_idx: int) -> List[str]:
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
            # explore_weight 决定根分支（新探索）挤进批次的优先程度
            if self._rng.random() < max(0.0, min(1.0, self.explore_weight)) or not batch:
                batch.append(view.root_id)
        return batch[:n]


class RandomPolicy(ExplorationPolicy):
    """均匀随机基线（对照实验用）。"""

    name = "random"

    def select_batch(self, view, W: int, round_idx: int) -> List[str]:
        eligible = view.eligible()
        if not eligible:
            return []
        n = min(W, len(eligible))
        return self._rng.sample(eligible, n)
