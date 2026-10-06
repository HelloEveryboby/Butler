"""
Dream 编排器 (Orchestrator) — 论文 §3 / Figure 1。

外层迭代 t = 1, 2, ...：
1. 在线探索：部署策略 π_t 引导 discovery agent 完成一次 rollout（≤ K1 决策轮），
   产出发现树 T_t（每节点=一次 CONTINUE 尝试的结果），追加到历史 H_t。
2. 离线做梦：在固定 H_t 上评估并修订策略（M 个版本），选出 π_{t+1}。
3. 重部署：π_{t+1} 上线驱动下一次发现，历史持续扩张 → 自我改进闭环。

在线与离线共用同一套基于树的决策接口，区别只在延续动作的观测来源：
在线产生新结果，回放揭示已录结果。
只有探索策略被更新；discovery agent、evaluator、执行接口保持固定。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .discovery_tree import DiscoveryForest, DiscoveryTree, Node
from .dreamer import DreamReport, Dreamer, PolicyDeveloper, ParametricDeveloper
from .policy import ExplorationPolicy
from .replay import ReplayView

logger = logging.getLogger(__name__)


@dataclass
class AttemptResult:
    """一次 CONTINUE 的结果：新工作区 + 生成物 + 诊断 + 得分。"""

    workspace: Dict[str, Any]
    score: float
    artifact: Any = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DreamConfig:
    """Dream 运行参数（论文实验的对应符号）。"""

    K1: int = 10            # 在线 rollout 最大决策轮数
    W: int = 4              # 并行 worker 数（批次上限）
    K2: int = 10            # 回放最大决策轮数
    M: int = 3              # 每次做梦评估的策略版本数（含当前策略）
    beta1: float = 0.1      # 执行代价惩罚系数
    beta2: float = 0.1      # 并行度奖励系数
    dream_every: int = 1    # 每隔多少个在线轮次触发一次做梦
    seed: int = 0


class DreamOrchestrator:
    """Dream 主循环。

    attempt_fn: Callable[[Dict[str, Any]], AttemptResult]
        discovery agent 的插件接口——给定父节点工作区，生成并评估一个新候选。
        Butler 集成时替换为真实实现（skill 流水线 / LLM 规划 + verification 评分）。
    """

    def __init__(self,
                 attempt_fn: Callable[[Dict[str, Any]], AttemptResult],
                 policy: ExplorationPolicy,
                 config: Optional[DreamConfig] = None,
                 forest: Optional[DiscoveryForest] = None,
                 developer: Optional[PolicyDeveloper] = None):
        self.attempt_fn = attempt_fn
        self.policy = policy
        self.config = config or DreamConfig()
        self.forest = forest or DiscoveryForest()
        self.developer = developer or ParametricDeveloper(seed=self.config.seed)
        self.rounds_done = 0
        self.last_dream_report: Optional[DreamReport] = None
        self.history: List[Dict[str, Any]] = []   # 外层迭代日志

    # ── 在线阶段 ──

    def online_rollout(self,
                       root_workspace: Optional[Dict[str, Any]] = None,
                       budget: Optional[int] = None) -> DiscoveryTree:
        """一次在线 rollout：≤ K1 决策轮，每轮批量 CONTINUE（≤ W 并行）。

        budget：可选的生成-评估请求总预算（覆盖 K1 轮限制的额外约束）。
        """
        cfg = self.config
        tree = DiscoveryTree(root_workspace=root_workspace or {})
        attempts = 0

        for k in range(cfg.K1):
            view = ReplayView(tree, set(tree.nodes))  # 在线：全部节点已知
            batch = self.policy.select_batch(view, cfg.W, k)
            if not batch:
                break

            newly: List[Node] = []
            for vid in batch:
                if budget is not None and attempts >= budget:
                    break
                parent = tree.nodes.get(vid)
                if parent is None:
                    continue
                try:
                    res = self.attempt_fn(dict(parent.workspace))
                except Exception as e:
                    logger.warning("[Dream] attempt_fn 异常: %s", e)
                    continue
                node = tree.add_child(vid, res.workspace, res.artifact,
                                      res.diagnostics, res.score)
                newly.append(node)
                attempts += 1

            if not newly:
                break
            self.policy.observe(newly)

        logger.info("[Dream] 在线 rollout 完成: 尝试=%d 最佳=%s",
                    tree.non_root_count(), tree.best_score())
        return tree

    # ── 离线阶段（做梦） ──

    def dream_phase(self) -> Optional[DreamReport]:
        """在当前历史上做梦：评估+修订策略，选出并重部署最优版本。"""
        if len(self.forest) == 0:
            logger.warning("[Dream] 历史为空，跳过做梦")
            return None
        dreamer = Dreamer(self.forest,
                          W=self.config.W, K2=self.config.K2,
                          M=self.config.M,
                          beta1=self.config.beta1, beta2=self.config.beta2,
                          developer=self.developer)
        report = dreamer.dream(self.policy)
        # 重部署：argmax 选择（含当前策略 → 保证不退化）
        self.policy = report.best_policy
        self.last_dream_report = report
        logger.info("[Dream] 做梦完成: baseline=%.4f → best=%.4f (improved=%s)",
                    report.baseline_value, report.best_value, report.improved)
        return report

    # ── 外层主循环 ──

    def run(self, rounds: int,
            root_workspace: Optional[Dict[str, Any]] = None,
            budget_per_round: Optional[int] = None) -> Dict[str, Any]:
        """执行 rounds 个外层迭代（在线探索 ⟲ 做梦）。"""
        for t in range(rounds):
            tree = self.online_rollout(root_workspace=root_workspace,
                                       budget=budget_per_round)
            self.forest.append(tree)
            self.rounds_done += 1

            entry: Dict[str, Any] = {
                "round": self.rounds_done,
                "tree_id": tree.tree_id,
                "attempts": tree.non_root_count(),
                "best_score": tree.best_score(),
            }
            if self.rounds_done % max(1, self.config.dream_every) == 0:
                report = self.dream_phase()
                if report is not None:
                    entry["dream"] = report.summary()
            self.history.append(entry)

        return self.summary()

    def summary(self) -> Dict[str, Any]:
        out = self.forest.summary()
        out.update({
            "rounds_done": self.rounds_done,
            "policy": self.policy.to_dict(),
            "history": self.history,
        })
        return out
