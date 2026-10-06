"""
Dream 做梦阶段 (Dreaming) — 论文 §3 "Policy improvement and selection"。

历史 H_t 固定，探索策略经历 M 个版本的评估与修订：
    π⁰_t = π_t（当前策略）→ π¹_t → ... → π^(M-1)_t
每个版本在**每一棵**历史树上从根回放；policy-development agent
依据回放轨迹与分数（以及先前修订的反馈）修订策略代码/参数。
最终 π_{t+1} = argmax_m V_m，候选集包含当前策略，因此 V_{t+1} ≥ V_t
——所选策略在固定历史上的平均回放分数保证不退化。

注意（论文 §5.1 实证结论）：历史应当作为**可交互的回放模拟器**使用，
而不是蒸馏成高层语义提示词注入——显式方向性引导会过度约束搜索空间、
损害多样性探索。因此本模块的反馈一律以"轨迹 + 分数"结构化形式交给
策略开发 agent，不做语义总结式注入。
"""

from __future__ import annotations

import json
import random
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .discovery_tree import DiscoveryForest
from .policy import ExplorationPolicy
from .replay import ReplayResult, replay_policy


@dataclass
class PolicyEvaluation:
    """一个策略版本在固定历史上的平均回放分数。"""

    policy: ExplorationPolicy
    mean_value: float
    per_tree: List[ReplayResult] = field(default_factory=list)

    def feedback_text(self) -> str:
        head = (f"== 策略 {self.policy.name} 参数={self.policy.get_params()} "
                f"平均回放分 V={self.mean_value:.4f} ==")
        return "\n".join([head] + [r.feedback_text() for r in self.per_tree])


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

    def summary(self) -> Dict[str, Any]:
        return {
            "trees_used": self.trees_used,
            "revisions_made": self.revisions_made,
            "baseline_value": round(self.baseline_value, 4),
            "best_value": round(self.best_value, 4),
            "improved": self.improved,
            "best_policy": self.best_policy.to_dict(),
        }


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
            if key == "explore_weight":
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
            "请分析成功决策与反复出现的失败，修订策略参数以提升平均回放分 V。\n"
            f"{feedback}\n\n"
            f"当前策略参数 JSON：{json.dumps(current.get_params(), ensure_ascii=False)}\n"
            "可调参数：explore_weight[0,1]（开新分支倾向）、refine_bias[-1,1]"
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
                 developer: Optional[PolicyDeveloper] = None):
        if M < 1:
            raise ValueError("M 至少为 1（必须评估当前策略）")
        self.forest = forest
        self.W = W
        self.K2 = K2
        self.M = M
        self.beta1 = beta1
        self.beta2 = beta2
        self.developer = developer or ParametricDeveloper(seed=0)

    def evaluate(self, policy: ExplorationPolicy) -> PolicyEvaluation:
        """在固定历史上评估一个策略版本（每棵树都从根回放）。"""
        results = [
            replay_policy(policy, tree, self.W, self.K2,
                          self.beta1, self.beta2)
            for tree in self.forest.trees
        ]
        mean = (sum(r.value for r in results) / len(results)) if results else 0.0
        return PolicyEvaluation(policy=policy, mean_value=mean, per_tree=results)

    def dream(self, current: ExplorationPolicy) -> DreamReport:
        """执行一次离线策略改进（做梦）。"""
        if len(self.forest) == 0:
            raise RuntimeError("发现历史为空，无可回放的世界")

        evaluations: List[PolicyEvaluation] = []
        eval0 = self.evaluate(current.clone())
        evaluations.append(eval0)
        feedback = eval0.feedback_text()

        for m in range(self.M - 1):
            revised = self.developer.revise(current, feedback, m)
            ev = self.evaluate(revised)
            evaluations.append(ev)
            feedback += "\n\n" + ev.feedback_text()

        # argmax 选择：候选含当前策略 → best_value ≥ baseline_value
        best = max(evaluations, key=lambda e: e.mean_value)
        return DreamReport(
            evaluations=evaluations,
            best_policy=best.policy,
            best_value=best.mean_value,
            baseline_value=evaluations[0].mean_value,
            improved=best.mean_value > evaluations[0].mean_value,
            trees_used=len(self.forest),
            revisions_made=self.M - 1,
        )
