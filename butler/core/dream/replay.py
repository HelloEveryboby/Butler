"""
Dream 回放模拟器 (Replay Simulator) — 论文 §2 / §3 "Offline evaluation"。

核心洞察：累积的发现历史就是已实现搜索空间的经验证据模型。
在历史树上"做梦"（回放）时，状态转移是确定性的——揭示所选节点**已录**的子节点，
无需重新调用 discovery agent / evaluator，因此单次昂贵的在线运行可以支撑
成千上万次零执行成本的离线策略评估。

回放目标（论文公式 1）：
    V = max_v s_v          （发现质量）
        − β1 · N           （执行代价：轨迹代表的生成-评估请求数）
        + β2 · N / max{1, k★}（并行度奖励：每决策轮平均尝试数）

同时记录论文附录 B.2 的评估曲线：
- attainment AUC：用少量 probe 达到历史天花板的比例（越高越好）；
- parallel penalty：effective_sequential_rounds / N（串行≈1，满批≈1/W）；
- pareto reward = AUC − λ · parallel_penalty。

终止条件：策略选择空批次、无已录延续可揭示、或达到 K2 轮。
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .discovery_tree import DiscoveryTree, Node


class ReplayView:
    """已揭示子树的只读视图：策略只能看到这里的内容。"""

    def __init__(self, tree: DiscoveryTree, revealed: Set[str]):
        self._tree = tree
        self._revealed = revealed

    @property
    def root_id(self) -> str:
        return "root"

    @property
    def baseline_score(self) -> Optional[float]:
        return self._tree.baseline_score

    def revealed_ids(self) -> Set[str]:
        return set(self._revealed)

    def node(self, node_id: str) -> Node:
        if node_id not in self._revealed:
            raise KeyError(f"节点未揭示，策略不可见: {node_id}")
        return self._sanitized(self._tree.nodes[node_id])

    def _sanitized(self, node: Node) -> Node:
        """隐藏未揭示子节点 id，保证策略只能看到已揭示前缀。"""
        view = copy.copy(node)
        view.children = [cid for cid in node.children if cid in self._revealed]
        return view

    def nodes(self) -> List[Node]:
        return [self.node(nid) for nid in sorted(self._revealed)]

    def is_leaf_in_view(self, node_id: str) -> bool:
        """在已揭示视图中是否为叶子（可能仍有未揭示子节点）。"""
        if node_id not in self._revealed:
            return False
        return all(cid not in self._revealed
                   for cid in self._tree.nodes[node_id].children)

    def eligible(self) -> List[str]:
        """视图内的 A(T) = {根} ∪ {已揭示叶子}。"""
        out = []
        for nid in sorted(self._revealed):
            if nid == self.root_id or self.is_leaf_in_view(nid):
                out.append(nid)
        return out

    def best_score(self) -> Optional[float]:
        scores = [n.score for n in self.nodes()
                  if not n.is_root and n.score is not None]
        return max(scores) if scores else None

    # ── 分支（网格）视图 ──

    def opened_branch_ids(self) -> List[str]:
        """已揭示的根分支（工作区）id，按揭示集合稳定排序。"""
        return [nid for nid in sorted(self._revealed)
                if nid != self.root_id
                and self._tree.nodes[nid].parent_id == self.root_id]

    def branch_of(self, node_id: str) -> Optional[str]:
        if node_id not in self._revealed:
            return None
        root = self._tree.branch_root(node_id)
        return root if root in self._revealed else None

    def branch_nodes(self, branch_id: str) -> List[Node]:
        """该分支已揭示的有序轨迹；未揭示节点不会出现。"""
        return [self._sanitized(n) for n in self._tree.branch_trajectory(branch_id)
                if n.id in self._revealed]

    def leaf_of_branch(self, branch_id: str) -> Optional[str]:
        nodes = self.branch_nodes(branch_id)
        if not nodes:
            return None
        for node in reversed(nodes):
            if self.is_leaf_in_view(node.id):
                return node.id
        return None

    def local_depth(self, node_id: str) -> int:
        """分支内深度：根分支=1，其子节点=2……"""
        node = self.node(node_id)
        return max(0, node.depth - 1)

    def grid_support(self) -> Dict[str, int]:
        """回放世界支持的分支/细化上限（当前已揭示部分）。"""
        branches = self.opened_branch_ids()
        max_attempts = 0
        for bid in branches:
            max_attempts = max(max_attempts, len(self.branch_nodes(bid)))
        return {"branch_count": max(1, len(branches)),
                "refine_count": max(0, max_attempts - 1)}


@dataclass
class ReplayResult:
    """一次 (策略, 树) 回放的完整结果。"""

    policy_name: str
    tree_id: str
    value: float                      # 回放目标 V（公式 1）
    max_score: Optional[float]        # 发现质量
    n_attempts: int                   # N：揭示的非根节点数
    rounds: int                       # k★：完成的决策轮数
    revealed_ids: List[str]
    trajectory: List[Dict[str, Any]] = field(default_factory=list)
    best_curve: List[float] = field(default_factory=list)
    effective_rounds: int = 0
    parallel_penalty: float = 0.0
    attainment_auc: float = 0.0
    pareto_reward: float = 0.0

    def feedback_text(self) -> str:
        """给策略开发 agent 的文本反馈（回放轨迹 + 分数 + 并行度）。"""
        lines = [f"[{self.policy_name}] 树={self.tree_id} "
                 f"V={self.value:.4f} 最佳={self.max_score} "
                 f"尝试数={self.n_attempts} 轮数={self.rounds} "
                 f"AUC={self.attainment_auc:.3f} "
                 f"并行惩罚={self.parallel_penalty:.3f}"]
        for t in self.trajectory:
            lines.append(
                f"  第{t['round']}轮 选取={t['batch']} "
                f"揭示={t['revealed']} 得分={t['scores']}"
            )
        return "\n".join(lines)


def _attainment_auc(best_curve: List[float], ceiling: Optional[float]) -> float:
    """归一化 attainment 曲线下面积：早达标接近 1，晚达标/未达标更低。"""
    if not best_curve or ceiling is None or ceiling <= 0:
        return 0.0
    values = [max(0.0, min(float(s), float(ceiling))) / float(ceiling)
              for s in best_curve]
    return sum(values) / len(values)


def replay_policy(policy, tree: DiscoveryTree,
                  W: int, K2: int,
                  beta1: float = 0.1, beta2: float = 0.1,
                  seed: int = 0,
                  lambda_parallel: float = 0.1) -> ReplayResult:
    """在已录树上回放一个策略版本（从根开始，确定性揭示）。"""
    policy.reset()
    revealed: Set[str] = {"root"}
    trajectory: List[Dict[str, Any]] = []
    best_curve: List[float] = []
    rounds = 0
    effective_rounds = 0

    for k in range(K2):
        view = ReplayView(tree, revealed)
        batch = policy.select_batch(view, W, k)
        if not batch:
            break  # C = ∅：策略主动终止

        newly: List[str] = []
        scores: List[Optional[float]] = []
        for vid in batch:
            if vid not in revealed:
                continue
            # 确定性揭示 Child(v;T)：下一个未揭示的已录子节点
            # （非根=唯一子节点；根=逐个揭示分支，对应"开新分支"）
            child = tree.next_unrevealed_child(vid, revealed)
            if child is not None and child.id not in revealed:
                revealed.add(child.id)
                newly.append(child.id)
                scores.append(child.score)
        rounds += 1
        if newly:
            effective_rounds += math.ceil(len(newly) / max(1, W))
        trajectory.append({"round": k, "batch": list(batch),
                           "revealed": newly, "scores": scores})
        view_after = ReplayView(tree, revealed)
        best = view_after.best_score()
        if newly and best is not None:
            best_curve.append(best)
        if not newly:
            break  # 无已录延续可揭示：终止
        policy.observe([tree.nodes[nid] for nid in newly])

    view = ReplayView(tree, revealed)
    max_score = view.best_score()
    n_attempts = len(revealed) - 1  # N = 已揭示非根节点数

    # 论文公式 1
    quality = max_score if max_score is not None else 0.0
    value = quality - beta1 * n_attempts + beta2 * n_attempts / max(1, rounds)

    # 论文附录 B.2：attainment / parallel penalty / pareto reward
    penalty = effective_rounds / max(1, n_attempts)
    auc = _attainment_auc(best_curve, tree.best_score())
    pareto = auc - lambda_parallel * penalty

    return ReplayResult(
        policy_name=getattr(policy, "name", "unknown"),
        tree_id=tree.tree_id,
        value=value,
        max_score=max_score,
        n_attempts=n_attempts,
        rounds=rounds,
        revealed_ids=sorted(revealed),
        trajectory=trajectory,
        best_curve=best_curve,
        effective_rounds=effective_rounds,
        parallel_penalty=penalty,
        attainment_auc=auc,
        pareto_reward=pareto,
    )
