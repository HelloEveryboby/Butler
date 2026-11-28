"""
Dream 编排器 (Orchestrator) — 论文 §3 / Figure 1。

外层迭代 t = 1, 2, ...：
1. 在线探索：策略先 ``plan_grid`` 显式规划本轮网格，再引导 discovery agent
   完成一次 rollout（≤ K1 决策轮，W 并行 worker），产出发现树 T_t，
   追加到历史 H_t。
2. 离线做梦：在固定 H_t 上评估并修订策略（M 个版本），选出 π_{t+1}。
3. 重部署：π_{t+1} 上线驱动下一次发现，历史持续扩张 → 自我改进闭环。

在线与离线共用同一套基于树的决策接口，区别只在延续动作的观测来源：
在线产生新结果，回放揭示已录结果。
只有探索策略被更新；discovery agent、evaluator、执行接口保持固定。
"""

from __future__ import annotations

import json
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .discovery_tree import DiscoveryForest, DiscoveryTree, Node
from .dreamer import DreamReport, Dreamer, ParametricDeveloper, PolicyDeveloper
from .grid import GridPlan, GridPlanningContext
from .policy import ExplorationPolicy, policy_from_dict
from .replay import ReplayView

logger = logging.getLogger(__name__)


@dataclass
class AttemptResult:
    """一次 CONTINUE 的结果：新工作区 + 生成物 + 诊断 + 得分 + 观察信号。"""

    workspace: Dict[str, Any]
    score: float
    artifact: Any = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    evaluated: bool = True
    valid: Optional[bool] = None
    fail_class: Optional[str] = None
    error: Optional[str] = None
    n_valid: Optional[int] = None
    n_total: Optional[int] = None


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
    betas: List[float] = field(default_factory=lambda: [0.4, 0.6, 0.8])
    lambda_parallel: float = 0.1   # Pareto 目标里的并行惩罚系数
    objective: str = "value"       # value（公式 1）| pareto（附录 B.2）
    max_workers: int = 0           # 0 = 使用 W；1 = 串行


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
                 developer: Optional[PolicyDeveloper] = None,
                 state_path: Optional[Path] = None):
        self.attempt_fn = attempt_fn
        self.policy = policy
        self.config = config or DreamConfig()
        self.forest = forest or DiscoveryForest()
        self.developer = developer or ParametricDeveloper(seed=self.config.seed)
        self.rounds_done = 0
        self.last_dream_report: Optional[DreamReport] = None
        self.last_plan: Optional[GridPlan] = None
        self.history: List[Dict[str, Any]] = []   # 外层迭代日志
        self.state_path = Path(state_path) if state_path else None

    # ── 在线阶段 ──

    def _grid_context(self) -> GridPlanningContext:
        """只使用已完成轮次的摘要（prefix-safe）构造规划上下文。"""
        cfg = self.config
        workers = max(1, cfg.max_workers or cfg.W)
        fallback_branch = max(1, min(cfg.W, cfg.K1))
        fallback_refine = max(0, math.ceil(cfg.K1 / fallback_branch) - 1)

        summaries = [t.best_score() for t in self.forest.trees]
        latest = summaries[-1] if summaries else None
        previous = summaries[-2] if len(summaries) >= 2 else None
        stalled = 0
        for i in range(len(summaries) - 1, 0, -1):
            if summaries[i] is None or summaries[i - 1] is None:
                stalled += 1
            elif summaries[i] > summaries[i - 1]:
                break
            else:
                stalled += 1

        last_grid = self.forest.trees[-1].grid if self.forest.trees else {}
        return GridPlanningContext(
            history=[{"tree_id": t.tree_id,
                      "attempts": t.non_root_count(),
                      "best_score": t.best_score(),
                      "grid": dict(t.grid)} for t in self.forest.trees],
            fallback_branch_count=fallback_branch,
            fallback_refine_count=fallback_refine,
            hard_max_branch_count=max(1, cfg.W),
            hard_max_refine_count=max(1, cfg.K1),
            worker_cap=workers,
            trace_branch_count=last_grid.get("branch_count"),
            trace_refine_count=last_grid.get("refine_count"),
            latest_best_score=latest,
            previous_best_score=previous,
            stalled_rounds=stalled,
        )

    def _plan_for_rollout(self) -> GridPlan:
        context = self._grid_context()
        plan = self.policy.plan_grid(context)
        self.policy.apply_plan(plan)
        self.last_plan = plan
        return plan

    def _execute_batch(self, batch: List[str],
                       tree: DiscoveryTree,
                       budget: Optional[int]) -> List[tuple]:
        """并行执行一批 CONTINUE，返回 [(node_id, AttemptResult|None)]。"""
        cfg = self.config
        max_workers = max(1, cfg.max_workers or cfg.W)
        jobs: List[tuple] = []
        for vid in batch:
            if budget is not None and len(jobs) >= budget:
                break
            parent = tree.nodes.get(vid)
            if parent is None:
                continue
            jobs.append((vid, dict(parent.workspace)))
        if not jobs:
            return []

        if len(jobs) == 1 or max_workers == 1:
            out = []
            for vid, workspace in jobs:
                try:
                    out.append((vid, self.attempt_fn(workspace)))
                except Exception as e:  # noqa: BLE001
                    logger.warning("[Dream] attempt_fn 异常: %s", e)
                    out.append((vid, None))
            return out

        out = []
        with ThreadPoolExecutor(max_workers=min(max_workers, len(jobs))) as ex:
            futures = [(vid, ex.submit(self.attempt_fn, workspace))
                       for vid, workspace in jobs]
            for vid, future in futures:
                try:
                    out.append((vid, future.result()))
                except Exception as e:  # noqa: BLE001
                    logger.warning("[Dream] attempt_fn 并行异常: %s", e)
                    out.append((vid, None))
        return out

    def online_rollout(self,
                       root_workspace: Optional[Dict[str, Any]] = None,
                       budget: Optional[int] = None,
                       baseline_score: Optional[float] = None) -> DiscoveryTree:
        """一次在线 rollout：先规划网格，再 ≤ K1 决策轮批量 CONTINUE（≤ W 并行）。

        budget：可选的生成-评估请求总预算（覆盖 K1 轮限制的额外约束）。
        """
        cfg = self.config
        plan = self._plan_for_rollout()
        tree = DiscoveryTree(root_workspace=root_workspace or {},
                             baseline_score=baseline_score)
        tree.grid = plan.to_dict()
        attempts = 0

        for k in range(cfg.K1):
            if budget is not None and attempts >= budget:
                break
            view = ReplayView(tree, set(tree.nodes))  # 在线：全部节点已知
            batch = self.policy.select_batch(view, cfg.W, k)
            if not batch:
                break

            remaining = None if budget is None else max(0, budget - attempts)
            results = self._execute_batch(batch, tree, remaining)
            newly: List[Node] = []
            for vid, res in results:
                if res is None:
                    continue
                node = tree.add_child(
                    vid, res.workspace, res.artifact, res.diagnostics,
                    res.score, evaluated=res.evaluated, valid=res.valid,
                    fail_class=res.fail_class, error=res.error,
                    n_valid=res.n_valid, n_total=res.n_total)
                newly.append(node)
                attempts += 1
            if not newly:
                break
            self.policy.observe(newly)

        logger.info("[Dream] 在线 rollout 完成: 网格=%s 尝试=%d 最佳=%s",
                    plan.to_dict(), tree.non_root_count(), tree.best_score())
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
                          developer=self.developer,
                          betas=self.config.betas,
                          lambda_parallel=self.config.lambda_parallel,
                          objective=self.config.objective,
                          K1=self.config.K1)
        report = dreamer.dream(self.policy)
        # 重部署：argmax 选择（含当前策略 → 保证不退化）
        self.policy = report.best_policy
        self.last_dream_report = report
        self.save_policy()
        logger.info("[Dream] 做梦完成: baseline=%.4f → best=%.4f (improved=%s)",
                    report.baseline_value, report.best_value, report.improved)
        return report

    # ── 状态持久化（跨轮重部署） ──

    def save_policy(self) -> None:
        if self.state_path is None:
            return
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            tmp.write_text(json.dumps(self.policy.to_dict(), ensure_ascii=False),
                           encoding="utf-8")
            tmp.replace(self.state_path)
        except Exception as e:  # noqa: BLE001
            logger.warning("[Dream] 策略保存失败: %s", e)

    def load_policy(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.policy = policy_from_dict(data)
        except Exception as e:  # noqa: BLE001
            logger.warning("[Dream] 策略加载失败: %s", e)

    # ── 外层主循环 ──

    def run(self, rounds: int,
            root_workspace: Optional[Dict[str, Any]] = None,
            budget_per_round: Optional[int] = None,
            baseline_score: Optional[float] = None) -> Dict[str, Any]:
        """执行 rounds 个外层迭代（在线探索 ⟲ 做梦）。"""
        for t in range(rounds):
            tree = self.online_rollout(root_workspace=root_workspace,
                                       budget=budget_per_round,
                                       baseline_score=baseline_score)
            self.forest.append(tree)
            self.rounds_done += 1

            entry: Dict[str, Any] = {
                "round": self.rounds_done,
                "tree_id": tree.tree_id,
                "attempts": tree.non_root_count(),
                "best_score": tree.best_score(),
                "grid": dict(tree.grid),
            }
            if self.rounds_done % max(1, self.config.dream_every) == 0:
                report = self.dream_phase()
                if report is not None:
                    entry["dream"] = report.summary()
            self.history.append(entry)
        self.save_policy()
        return self.summary()

    def summary(self) -> Dict[str, Any]:
        out = self.forest.summary()
        out.update({
            "rounds_done": self.rounds_done,
            "policy": self.policy.to_dict(),
            "last_plan": self.last_plan.to_dict() if self.last_plan else None,
            "history": self.history,
        })
        return out
