"""
Dream 做梦阶段 (Dreaming) — 论文 §3 "Policy improvement and selection"。

历史 H_t 固定，探索策略经历 M 个版本的评估与修订：
    π⁰_t = π_t（当前策略）→ π¹_t → ... → π^(M-1)_t
每个版本在**每一棵**历史树上从根回放；policy-development agent
依据回放轨迹与分数（以及先前修订的反馈）逐版修订策略参数/网格。
最终 π_{t+1} = argmax_m score_m，候选集包含当前策略，因此选择结果
在固定历史上的评估分保证不退化。

论文附录 B.2 的 beta 扫描：
- 每个候选版本在一组 beta 上回放（beta 固定于单次回放，不随观测变化）；
- 用 pareto.reward = attainment AUC − λ · parallel_penalty 评价；
- 择优选出的 beta 会烘焙进该版本，作为下一轮在线探索的固定值。

注意（论文 §5.1 实证结论）：历史应当作为**可交互的回放模拟器**使用，
而不是蒸馏成高层语义提示词注入——显式方向性引导会过度约束搜索空间、
损害多样性探索。因此本模块的反馈一律以"轨迹 + 分数"结构化形式交给
策略开发 agent，不做语义总结式注入。
"""

from __future__ import annotations

import json
import math
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .discovery_tree import DiscoveryForest
from .grid import GridPlanningContext
from .policy import ExplorationPolicy
from .replay import ReplayResult, replay_policy


@dataclass
class PolicyEvaluation:
    """一个策略版本在固定历史上的平均回放评估。"""

    policy: ExplorationPolicy
    mean_value: float
    per_tree: List[ReplayResult] = field(default_factory=list)
    mean_pareto: float = 0.0
    mean_attainment_auc: float = 0.0
    mean_parallel_penalty: float = 0.0
    selection_score: float = 0.0
    beta: Optional[float] = None

    def feedback_text(self) -> str:
        head = (f"== 策略 {self.policy.name} 参数={self.policy.get_params()} "
                f"beta={self.beta} 平均回放分 V={self.mean_value:.4f} "
                f"Pareto={self.mean_pareto:.4f} "
                f"AUC={self.mean_attainment_auc:.3f} "
                f"并行惩罚={self.mean_parallel_penalty:.3f} ==")
        return "\n".join([head] + [r.feedback_text() for r in self.per_tree])


@dataclass
class BetaSweepPoint:
    beta: float
    mean_value: float
    mean_pareto: float
    mean_parallel_penalty: float
    mean_attainment_auc: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beta": round(self.beta, 3),
            "value": round(self.mean_value, 4),
            "pareto": round(self.mean_pareto, 4),
            "parallel_penalty": round(self.mean_parallel_penalty, 4),
            "attainment_auc": round(self.mean_attainment_auc, 4),
        }


@dataclass
class BetaSweep:
    points: List[BetaSweepPoint]
    best: PolicyEvaluation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_beta": self.best.beta,
            "best_score": round(self.best.selection_score, 4),
            "points": [p.to_dict() for p in self.points],
        }


@dataclass
class DreamReport:
    """一次做梦（离线策略改进）的结果报告。"""

    evaluations: List[PolicyEvaluation]
    best_policy: ExplorationPolicy
    best_value: float
    baseline_value: float          # 当前策略 π_t 的平均回放分
    improved: bool                 # 是否优于当前策略（严格提升）
    trees_used: int
    revisions_made: int
    objective: str = "value"
    beta_sweep: Optional[BetaSweep] = None

    def summary(self) -> Dict[str, Any]:
        best = max(self.evaluations,
                   key=lambda ev: ev.selection_score) if self.evaluations else None
        out = {
            "trees_used": self.trees_used,
            "revisions_made": self.revisions_made,
            "objective": self.objective,
            "baseline_value": round(self.baseline_value, 4),
            "best_value": round(self.best_value, 4),
            "best_pareto": round(best.mean_pareto, 4) if best else 0.0,
            "improved": self.improved,
            "best_policy": self.best_policy.to_dict(),
            "best_beta": best.beta if best else None,
        }
        if self.beta_sweep is not None:
            out["beta_sweep"] = self.beta_sweep.to_dict()
        return out


class PolicyDeveloper(ABC):
    """policy-development agent：依据回放反馈修订策略。"""

    @abstractmethod
    def revise(self, current: ExplorationPolicy,
               feedback: str, revision_idx: int) -> ExplorationPolicy:
        """返回一个修订后的策略版本（不得修改原策略对象）。"""


class ParametricDeveloper(PolicyDeveloper):
    """无 LLM 回退：对策略参数做进化式扰动（确定性随机源）。

    适用于离线/无 LLM 环境，保证做梦链路始终可用；
    有 LLM 时可换 LLMDeveloper 获得"修订策略代码"的完整能力。
    """

    def __init__(self, seed: int = 0, step_scale: float = 0.3):
        self.seed = seed
        self.step_scale = step_scale
        self._rng = random.Random(seed)

    def revise(self, current: ExplorationPolicy,
               feedback: str, revision_idx: int) -> ExplorationPolicy:
        new = current.clone()
        params = new.get_params()
        proposals: Dict[str, Any] = {}
        for key, val in params.items():
            if key == "seed" or not isinstance(val, (int, float)):
                continue
            if key == "stop_threshold" and val == float("inf"):
                continue  # 不主动收紧停止条件（避免策略空间塌缩）
            noise = self._rng.gauss(0.0, self.step_scale)
            if key == "beta":
                proposals[key] = max(0.1, min(1.0, val + noise * 0.2))
            elif key == "branch_count":
                proposals[key] = max(0, min(16, int(round(val + noise * 2))))
            elif key == "refine_count":
                proposals[key] = max(-1, min(16, int(round(val + noise * 2))))
            elif key == "explore_weight":
                proposals[key] = max(0.0, min(1.0, val + noise * 0.5))
            elif key == "refine_bias":
                proposals[key] = max(-1.0, min(1.0, val + noise * 0.5))
            elif key == "batch_fill":
                proposals[key] = max(0.1, min(1.0, val + noise * 0.3))
            else:
                proposals[key] = val + noise * max(1e-3, abs(val) * 0.2)
        new.set_params(proposals)
        return new


class LLMDeveloper(PolicyDeveloper):
    """LLM 策略开发 agent：以回放轨迹+分数为反馈修订策略参数。

    ask_llm: Callable[[str], str]，对接 Butler 的 nlu_service.ask_llm
    （或任意 LLM 调用）；解析失败自动回退为参数扰动（ParametricDeveloper）。
    """

    def __init__(self, ask_llm: Callable[[str], str],
                 fallback: Optional[PolicyDeveloper] = None):
        self.ask_llm = ask_llm
        self.fallback = fallback or ParametricDeveloper(seed=42)

    def revise(self, current: ExplorationPolicy,
               feedback: str, revision_idx: int) -> ExplorationPolicy:
        prompt = (
            "你是 Dream 的策略开发 agent（policy-development agent）。\n"
            "下面是一个探索策略在历史发现树上的回放轨迹与得分。\n"
            "请分析成功决策与反复出现的失败，修订策略参数以提升平均回放分 V "
            "与 Pareto 目标（AUC − λ·并行惩罚）。\n"
            f"{feedback}\n\n"
            f"当前策略参数 JSON：{json.dumps(current.get_params(), ensure_ascii=False)}\n"
            "可调参数：beta[0.1,1]（探索耐心：高=更宽/更深/更弱剪枝）、"
            "branch_count（本轮分支数，0=自适应）、"
            "refine_count（每分支细化次数，-1=自适应）、"
            "explore_weight[0,1]（开新分支倾向）、refine_bias[-1,1]"
            "（正=偏好高分分支，负=偏好低分分支）、batch_fill(0,1]（并行额度使用率）、"
            "stop_threshold（达标即停）。\n"
            "只输出修订后的参数 JSON，不要解释。"
        )
        try:
            raw = self.ask_llm(prompt)
            m = re.search(r"\{.*\}", raw or "", re.S)
            if not m:
                raise ValueError("LLM 输出不含 JSON")
            new = current.clone()
            new.set_params(json.loads(m.group(0)))
            return new
        except Exception:
            return self.fallback.revise(current, feedback, revision_idx)


class Dreamer:
    """做梦阶段编排：M 版评估 → 修订 → argmax 选择（含当前策略，单调不退化）。"""

    def __init__(self, forest: DiscoveryForest,
                 W: int = 4, K2: int = 10, M: int = 3,
                 beta1: float = 0.1, beta2: float = 0.1,
                 developer: Optional[PolicyDeveloper] = None,
                 betas: Optional[List[float]] = None,
                 lambda_parallel: float = 0.1,
                 objective: str = "value",
                 K1: int = 10):
        if M < 1:
            raise ValueError("M 至少为 1（必须评估当前策略）")
        if objective not in ("value", "pareto"):
            raise ValueError("objective 必须是 value 或 pareto")
        self.forest = forest
        self.W = W
        self.K2 = K2
        self.M = M
        self.K1 = K1
        self.beta1 = beta1
        self.beta2 = beta2
        self.developer = developer or ParametricDeveloper(seed=0)
        self.betas = [float(b) for b in (betas or [])]
        self.lambda_parallel = lambda_parallel
        self.objective = objective

    # ── 规划上下文（与在线共享 prefix-safe 统计） ──

    def grid_context(self) -> GridPlanningContext:
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
        fallback_branch = max(1, min(self.W, self.K1))
        return GridPlanningContext(
            history=[{"tree_id": t.tree_id,
                      "attempts": t.non_root_count(),
                      "best_score": t.best_score(),
                      "grid": dict(t.grid)} for t in self.forest.trees],
            fallback_branch_count=fallback_branch,
            fallback_refine_count=max(0, math.ceil(self.K1 / fallback_branch) - 1),
            hard_max_branch_count=max(1, self.W),
            hard_max_refine_count=max(1, self.K1),
            worker_cap=self.W,
            latest_best_score=latest,
            previous_best_score=previous,
            stalled_rounds=stalled,
        )

    # ── 评估 ──

    def _score(self, evaluation: PolicyEvaluation) -> float:
        return (evaluation.mean_pareto if self.objective == "pareto"
                else evaluation.mean_value)

    def evaluate(self, policy: ExplorationPolicy,
                 beta: Optional[float] = None) -> PolicyEvaluation:
        """在固定历史上评估一个策略版本（每棵树都从根回放）。"""
        candidate = policy.clone()
        if beta is not None and hasattr(candidate, "beta"):
            candidate.beta = float(beta)
        plan = candidate.plan_grid(self.grid_context())
        candidate.apply_plan(plan)

        results = [
            replay_policy(candidate, tree, self.W, self.K2,
                          self.beta1, self.beta2,
                          lambda_parallel=self.lambda_parallel)
            for tree in self.forest.trees
        ]
        n = len(results) or 1
        evaluation = PolicyEvaluation(
            policy=candidate,
            mean_value=sum(r.value for r in results) / n,
            per_tree=results,
            mean_pareto=sum(r.pareto_reward for r in results) / n,
            mean_attainment_auc=sum(r.attainment_auc for r in results) / n,
            mean_parallel_penalty=sum(r.parallel_penalty for r in results) / n,
            beta=getattr(candidate, "beta", beta),
        )
        evaluation.selection_score = self._score(evaluation)
        return evaluation

    def sweep_beta(self, policy: ExplorationPolicy) -> BetaSweep:
        """在固定 beta 网格上扫描（附录 B.2），返回最优 beta 与完整前沿。"""
        betas = self.betas or [float(getattr(policy, "beta", 0.6))]
        evaluations = [self.evaluate(policy, beta) for beta in betas]
        points = [BetaSweepPoint(
            beta=ev.beta if ev.beta is not None else float("nan"),
            mean_value=ev.mean_value,
            mean_pareto=ev.mean_pareto,
            mean_parallel_penalty=ev.mean_parallel_penalty,
            mean_attainment_auc=ev.mean_attainment_auc,
        ) for ev in evaluations]
        best = max(evaluations, key=lambda ev: ev.selection_score)
        return BetaSweep(points=points, best=best)

    def _evaluate_version(self, policy: ExplorationPolicy) -> PolicyEvaluation:
        if self.betas:
            return self.sweep_beta(policy).best
        return self.evaluate(policy)

    # ── 做梦 ──

    def dream(self, current: ExplorationPolicy) -> DreamReport:
        """执行一次离线策略改进（做梦）。"""
        if len(self.forest) == 0:
            raise RuntimeError("发现历史为空，无可回放的世界")

        eval0 = self._evaluate_version(current)
        evaluations: List[PolicyEvaluation] = [eval0]
        feedback = eval0.feedback_text()

        base = current
        for m in range(self.M - 1):
            revised = self.developer.revise(base, feedback, m)
            ev = self._evaluate_version(revised)
            evaluations.append(ev)
            feedback += "\n\n" + ev.feedback_text()
            base = revised

        # argmax 选择：候选含当前策略 → 评估分不退化
        best = max(evaluations, key=lambda e: e.selection_score)
        beta_sweep = self.sweep_beta(best.policy) if self.betas else None
        return DreamReport(
            evaluations=evaluations,
            best_policy=best.policy,
            best_value=best.mean_value,
            baseline_value=eval0.mean_value,
            improved=best.selection_score > eval0.selection_score,
            trees_used=len(self.forest),
            revisions_made=self.M - 1,
            objective=self.objective,
            beta_sweep=beta_sweep,
        )
