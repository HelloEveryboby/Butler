"""
dream_admin — Dream 技能管理入口。

供 LLM / 用户查询状态、触发做梦、调整探索策略参数。
所有函数返回可 JSON 序列化的 dict，便于技能层直接转述。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from butler.core.dream import AdaptivePolicy, Dreamer
from butler.core.dream import butler_adapter


def status() -> Dict[str, Any]:
    """Dream 状态：历史规模、最佳得分、当前策略、运行参数。"""
    settings = butler_adapter.load_settings()
    forest = butler_adapter.load_forest(settings)
    return {
        "enabled": settings.get("enabled", True),
        "forest": forest.summary(),
        "settings": {k: v for k, v in settings.items() if k != "enabled"},
    }


def trigger_dream(nlu_service=None) -> Dict[str, Any]:
    """手动触发一次做梦（离线策略改进），返回摘要。"""
    settings = butler_adapter.load_settings()
    forest = butler_adapter.load_forest(settings)
    if len(forest) == 0:
        return {"ok": False, "reason": "发现历史为空，无可回放的世界"}
    cfg = butler_adapter.config_from_settings(settings)
    dreamer = Dreamer(forest, W=cfg.W, K2=cfg.K2, M=cfg.M,
                      beta1=cfg.beta1, beta2=cfg.beta2,
                      developer=butler_adapter.make_developer(nlu_service, seed=cfg.seed))
    report = dreamer.dream(AdaptivePolicy(seed=cfg.seed))
    butler_adapter.save_forest(forest, settings)
    return {"ok": True, **report.summary()}


def get_policy(params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """查看（可选：应用给定参数后的）探索策略参数与语义说明。"""
    policy = AdaptivePolicy(**(params or {}))
    return {
        "policy": policy.to_dict(),
        "meaning": {
            "explore_weight": "开新分支（根）倾向 [0,1]",
            "refine_bias": "≥0 偏好细化高分分支；<0 偏好低分分支 [-1,1]",
            "batch_fill": "每决策轮并行额度使用率 (0,1]",
            "stop_threshold": "已揭示最佳得分达到即停",
        },
    }


def set_params(**params: Any) -> Dict[str, Any]:
    """校验并返回一组合法的策略参数（供写入配置/传入编排器）。"""
    policy = AdaptivePolicy()
    policy.set_params(params)
    return {"ok": True, "policy": policy.to_dict()}


if __name__ == "__main__":
    print(json.dumps(status(), ensure_ascii=False, indent=2, default=str))
