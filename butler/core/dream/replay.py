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

终止条件：策略选择空批次、无已录延续可揭示、或达到 K2 轮。
"""

from __future__ import annotations

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

    def revealed_ids(self) -> Set[str]:
        return set(self._revealed)

    def node(self, node_id: str) -> Node:
        if node_id not in self._revealed:
            raise KeyError(f"节点未揭示，策略不可见: {node_id}")
        return self._tree.nodes[node_id]

    def nodes(self) -> List[Node]:
        return [self._tree.nodes[nid] for nid in self._revealed]

    def is_leaf_in_view(self, node_id: str) -> bool:
        """在已揭示视图中是否为叶子（可能仍有未揭示子节点）。"""
        if node_id not in self._revealed:
            return False
        return all(cid not in self._revealed
                   for cid in self._tree.nodes[node_id].children)

    def eligible(self) -> List[str]:
        """视图内的 A(T) = {根} ∪ {已揭示叶子}。"""
        out = []
        for nid in self._revealed:
            if nid == self.root_id or self.is_leaf_in_view(nid):
                out.append(nid)
        return out

    def best_score(self) -> Optional[float]:
        scores = [n.score for n in self.nodes()
                  if not n.is_root and n.score is not None]
        return max(scores) if scores else None


@dataclass
class ReplayResult:
    """一次 (策略, 树) 回放的完整结果。"""

    policy_name: str
    tree_id: str
    value: float                      # 回放目标 V
    max_score: Optional[float]        # 发现质量
    n_attempts: int                   # N：揭示的非根节点数
    rounds: int                       # k★：完成的决策轮数
    revealed_ids: List[str]
    trajectory: List[Dict[str, Any]] = field(default_factory=list)

    def feedback_text(self) -> str:
        """给策略开发 agent 的文本反馈（回放轨迹 + 分数）。"""
        lines = [f"[{self.policy_name}] 树={self.tree_id} "
                 f"V={self.value:.4f} 最佳={self.max_score} "
                 f"尝试数={self.n_attempts} 轮数={self.rounds}"]
        for t in self.trajectory:
            lines.append(
                f"  第{t['round']}轮 选取={t['batch']} "
                f"揭示={t['revealed']} 得分={t['scores']}"
            )
        return "\n".join(lines)


def replay_policy(policy, tree: DiscoveryTree,
                  W: int, K2: int,
                  beta1: float = 0.1, beta2: float = 0.1,
                  seed: int = 0) -> ReplayResult:
    """在已录树上回放一个策略版本（从根开始，确定性揭示）。"""
    policy.reset()
    revealed: Set[str] = {"root"}
    trajectory: List[Dict[str, Any]] = []
    rounds = 0

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
        trajectory.append({"round": k, "batch": list(batch),
                           "revealed": newly, "scores": scores})
        if not newly:
            break  # 无已录延续可揭示：终止
        policy.observe([tree.nodes[nid] for nid in newly])

    view = ReplayView(tree, revealed)
    max_score = view.best_score()
    n_attempts = len(revealed) - 1  # N = 已揭示非根节点数

    # 论文公式 1
    quality = max_score if max_score is not None else 0.0
    value = quality - beta1 * n_attempts + beta2 * n_attempts / max(1, rounds)

    return ReplayResult(
        policy_name=getattr(policy, "name", "unknown"),
        tree_id=tree.tree_id,
        value=value,
        max_score=max_score,
        n_attempts=n_attempts,
        rounds=rounds,
        revealed_ids=sorted(revealed),
        trajectory=trajectory,
    )
