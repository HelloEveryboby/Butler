# -*- coding: utf-8 -*-
"""``butler dream`` — 做梦引擎（记忆整合 + RSI 策略自改进）管理命令。"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, List, Optional

from butler.core.dream import butler_adapter


def _emit(obj: Dict[str, Any]) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _status() -> Dict[str, Any]:
    settings = butler_adapter.load_settings()
    forest = butler_adapter.load_forest(settings)
    return {
        "enabled": settings.get("enabled", True),
        "forest": forest.summary(),
        "policy": butler_adapter.load_policy(settings).to_dict(),
        "policy_file": str(butler_adapter.policy_path(settings)),
        "settings": {k: v for k, v in settings.items() if k != "enabled"},
    }


def _run(force: bool) -> Dict[str, Any]:
    from butler.core.dream_engine import DreamEngine

    engine = DreamEngine(None)
    if not force and not engine.should_dream():
        return {"ok": False,
                "reason": "未到做梦时间（24h 冷却），可使用 --force 强制触发"}
    summary = engine.dream(force=force)
    if summary is None:
        forest = butler_adapter.load_forest()
        reason = ("发现历史为空：先执行在线探索产生 forest.json" if len(forest) == 0
                  else "本次未产生策略自改进报告（详情见日志）")
        return {"ok": False, "reason": reason}
    return {"ok": True, "dream": summary}


def _parse_value(raw: str):
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _params(pairs: Optional[List[str]]) -> Dict[str, Any]:
    settings = butler_adapter.load_settings()
    policy = butler_adapter.load_policy(settings)
    if not pairs:
        return {"ok": True, "policy": policy.to_dict(),
                "path": str(butler_adapter.policy_path(settings))}

    params: Dict[str, Any] = {}
    for item in pairs:
        key, sep, raw = item.partition("=")
        if not sep:
            return {"ok": False, "reason": f"参数格式应为 K=V: {item}"}
        params[key.strip()] = _parse_value(raw.strip())
    policy.set_params(params)
    butler_adapter.save_policy(policy, settings)
    return {"ok": True, "policy": policy.to_dict(),
            "path": str(butler_adapter.policy_path(settings))}


def run_dream_cli(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="butler dream", description="Dream 做梦引擎管理")
    sub = parser.add_subparsers(dest="action")
    sub.add_parser("status", help="查看做梦状态（默认）")
    run_p = sub.add_parser("run", help="触发一次做梦（记忆整合 + 策略自改进）")
    run_p.add_argument("--force", action="store_true", help="忽略 24h 冷却")
    params_p = sub.add_parser("params", help="查看/修改探索策略参数")
    params_p.add_argument("--set", nargs="+", default=None, metavar="K=V",
                          help="如 explore_weight=0.4 batch_fill=0.8")
    args = parser.parse_args(argv)

    action = args.action or "status"
    if action == "run":
        result = _run(args.force)
        _emit(result)
        return 0 if result.get("ok") else 1
    if action == "params":
        _emit(_params(args.set))
        return 0
    _emit(_status())
    return 0
