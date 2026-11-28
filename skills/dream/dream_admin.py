"""
dream_admin — Dream 技能管理入口。

供 LLM / 用户查询状态、触发做梦、扫描 beta、查看/调整已部署探索策略。
所有函数返回可 JSON 序列化的 dict，便于技能层直接转述。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from butler.core.dream import Dreamer
from butler.core.dream import butler_adapter


def status() -> Dict[str, Any]:
    """Dream 状态：历史规模、最佳得分、已部署策略、运行参数。"""
    settings = butler_adapter.load_settings()
    forest = butler_adapter.load_forest(settings)
    policy = butler_adapter.load_policy(settings)
    return {
        "enabled": settings.get("enabled", True),
        "forest": forest.summary(),
        "policy": policy.to_dict(),
        "settings": {k: v for k, v in settings.items() if k != "enabled"},
    }


def trigger_dream(nlu_service=None) -> Dict[str, Any]:
    """手动触发一次做梦（离线策略改进），并持久化重部署策略。"""
    settings = butler_adapter.load_settings()
    forest = butler_adapter.load_forest(settings)
    if len(forest) == 0:
        return {"ok": False, "reason": "发现历史为空，无可回放的世界"}
    cfg = butler_adapter.config_from_settings(settings)
    policy = butler_adapter.load_policy(settings)
    dreamer = Dreamer(forest, W=cfg.W, K2=cfg.K2, M=cfg.M,
                      beta1=cfg.beta1, beta2=cfg.beta2,
                      developer=butler_adapter.make_developer(
                          nlu_service, seed=cfg.seed),
                      betas=cfg.betas,
                      lambda_parallel=cfg.lambda_parallel,
                      objective=cfg.objective,
                      K1=cfg.K1)
    report = dreamer.dream(policy)
    butler_adapter.save_forest(forest, settings)
    butler_adapter.save_policy(report.best_policy, settings)
    return {"ok": True, **report.summary()}


def get_policy(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """查看（可选：应用给定参数后的）探索策略参数与语义说明。"""
    policy = butler_adapter.load_policy()
    if params:
        policy.set_params(params)
    return {
        "policy": policy.to_dict(),
        "meaning": {
            "beta": "探索耐心 [0.1,1]：高=更宽/更深/更弱剪枝",
            "branch_count": "本轮并行分支数；0=自适应",
            "refine_count": "每条分支细化次数；-1=自适应",
            "explore_weight": "无网格时的开新分支倾向 [0,1]",
            "refine_bias": "≥0 偏好细化高分分支；<0 偏好低分分支 [-1,1]",
            "batch_fill": "每决策轮并行额度使用率 (0,1]",
            "stop_threshold": "已揭示最佳得分达到即停",
        },
    }


def set_params(persist: bool = True, **params: Any) -> Dict[str, Any]:
    """校验并应用策略参数；默认写入 data/dream/policy.json。"""
    policy = butler_adapter.load_policy()
    policy.set_params(params)
    if persist:
        butler_adapter.save_policy(policy)
    return {"ok": True, "persisted": persist, "policy": policy.to_dict()}


def sweep_beta() -> Dict[str, Any]:
    """在固定历史上按配置的 beta 网格扫描，返回 Pareto 前沿。"""
    settings = butler_adapter.load_settings()
    forest = butler_adapter.load_forest(settings)
    if len(forest) == 0:
        return {"ok": False, "reason": "发现历史为空，无可回放的世界"}
    cfg = butler_adapter.config_from_settings(settings)
    dreamer = Dreamer(forest, W=cfg.W, K2=cfg.K2, M=1,
                      beta1=cfg.beta1, beta2=cfg.beta2,
                      betas=cfg.betas,
                      lambda_parallel=cfg.lambda_parallel,
                      objective=cfg.objective,
                      K1=cfg.K1)
    sweep = dreamer.sweep_beta(butler_adapter.load_policy(settings))
    return {"ok": True, **sweep.to_dict()}


def plan_preview() -> Dict[str, Any]:
    """预览下一轮在线网格规划（不执行任何发现请求）。"""
    settings = butler_adapter.load_settings()
    forest = butler_adapter.load_forest(settings)
    cfg = butler_adapter.config_from_settings(settings)
    dreamer = Dreamer(forest, W=cfg.W, K2=cfg.K2, M=1,
                      beta1=cfg.beta1, beta2=cfg.beta2,
                      betas=cfg.betas, K1=cfg.K1)
    policy = butler_adapter.load_policy(settings)
    plan = policy.plan_grid(dreamer.grid_context())
    return {"ok": True, "plan": plan.to_dict()}


if __name__ == "__main__":
    print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
