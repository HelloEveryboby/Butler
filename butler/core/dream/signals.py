"""
Dream 观察信号 (Observation Signals) — 论文附录 B.2 "failure interpretation"。

回放与在线 rollout 共用同一套节点观察字段。这里把论文里的前缀信号
（successful anchor、parent→child gain、失败可修复性）固化成纯函数，
供探索策略在不看未揭示结果的前提下排序候选。

失败分类原则（论文 B.2）：
- 编译/形状/掩码/正确性等实现层错误通常可修复，不能据此关闭整条分支；
- 环境缺失、依赖缺失、资源上限、权限等属于硬失败，继续细化大概率浪费额度；
- 单次失败不覆盖该分支历史成功锚点；后续成功会重新打开分支。
"""

from __future__ import annotations

from typing import Iterable, Optional

# 可修复的实现层失败：只降低优先级，不永久关闭分支。
REPAIRABLE_FAIL_CLASSES = frozenset({
    "compile_error",
    "compile_other",
    "runtime_error",
    "shape_error",
    "mask_error",
    "layout_error",
    "correctness",
    "assertion",
    "test_failure",
    "output_mismatch",
})

# 硬失败：环境/依赖/资源/权限问题，重试同一分支通常无意义。
HARD_FAIL_CLASSES = frozenset({
    "env_missing",
    "environment",
    "dependency",
    "resource_limit",
    "permission",
    "timeout",
    "oom",
})

SUCCESS_FAIL_CLASSES = frozenset({"", "ok", "none", None})


def is_successful_observation(node) -> bool:
    """论文成功语义：已评估且无 error、fail_class 为 ok。

    ``valid == False`` 本身不构成失败（某些任务不提供 valid 字段）。
    """
    if node is None or not getattr(node, "evaluated", True):
        return False
    if getattr(node, "error", None):
        return False
    fail_class = getattr(node, "fail_class", None)
    return fail_class in SUCCESS_FAIL_CLASSES


def is_repairable_failure(node) -> bool:
    if node is None or is_successful_observation(node):
        return False
    fail_class = getattr(node, "fail_class", None)
    if fail_class in REPAIRABLE_FAIL_CLASSES:
        return True
    # 有 error 文本但没有明确硬失败分类：默认按可修复处理，
    # 避免一次实现失误让分支永久饿死。
    return fail_class not in HARD_FAIL_CLASSES


def is_hard_failure(node) -> bool:
    if node is None or is_successful_observation(node):
        return False
    return getattr(node, "fail_class", None) in HARD_FAIL_CLASSES


def successful_anchor(nodes: Iterable) -> Optional[float]:
    """分支历史中成功评估的最高分（没有则 None）。"""
    scores = [n.score for n in nodes
              if n is not None and n.score is not None
              and is_successful_observation(n)]
    return max(scores) if scores else None


def probe_improved_vs_parent(node, parent) -> bool:
    if node is None or parent is None:
        return False
    if node.score is None or parent.score is None:
        return False
    return node.score > parent.score


def probe_improved_vs_baseline(node, baseline_score: Optional[float]) -> bool:
    if node is None or node.score is None or baseline_score is None:
        return False
    return node.score > baseline_score


def branch_promising(nodes: Iterable, baseline_score: Optional[float] = None) -> bool:
    """分支是否值得继续：有成功锚点且未低于基线。"""
    anchor = successful_anchor(nodes)
    if anchor is None:
        return False
    if baseline_score is None:
        return True
    return anchor >= baseline_score


def branch_failed_hard(nodes: Iterable) -> bool:
    """分支是否累积到硬失败（最近一次为硬失败且没有成功记录）。"""
    ordered = [n for n in nodes if n is not None]
    if not ordered:
        return False
    if successful_anchor(ordered) is not None:
        return False
    return is_hard_failure(ordered[-1])
