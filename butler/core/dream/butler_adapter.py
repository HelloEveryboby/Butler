"""
Dream × Butler 集成适配层。

职责：
- 从 Butler 配置（config.yaml → dream 段）加载运行参数；
- 提供 discovery agent / evaluator 的插件适配骨架（skill 流水线、verification 评分）；
- 为 DreamEngine（做梦引擎）挂接 RSI 做梦阶段（记忆整合之外的策略自改进）；
- 历史森林（discovery forest）持久化到 Butler 数据目录。

设计约束（论文 §3）：只修订探索策略；discovery agent、evaluator、
执行接口保持固定，避免自我改进回路失控。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .discovery_tree import DiscoveryForest
from .dreamer import LLMDeveloper, ParametricDeveloper
from .orchestrator import AttemptResult, DreamOrchestrator, DreamConfig
from .policy import AdaptivePolicy, ExplorationPolicy

logger = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "enabled": True,
    "data_dir": "data/dream",
    "K1": 10,
    "W": 4,
    "K2": 10,
    "M": 3,
    "beta1": 0.1,
    "beta2": 0.1,
    "dream_every": 1,
    "seed": 0,
}


def load_settings(config_loader=None) -> Dict[str, Any]:
    """合并 config.yaml 的 dream 段与默认值。"""
    settings = dict(DEFAULT_SETTINGS)
    loader = config_loader
    if loader is None:
        try:
            from package.core_utils.config_loader import config_loader as loader
        except Exception:  # noqa: BLE001
            loader = None
    if loader is not None:
        try:
            user = loader.get("dream") or {}
            if isinstance(user, dict):
                settings.update({k: v for k, v in user.items()
                                 if v is not None})
        except Exception as e:  # noqa: BLE001
            logger.warning("[Dream] 读取配置失败，使用默认值: %s", e)
    return settings


def config_from_settings(settings: Dict[str, Any]) -> DreamConfig:
    return DreamConfig(
        K1=int(settings.get("K1", 10)),
        W=int(settings.get("W", 4)),
        K2=int(settings.get("K2", 10)),
        M=int(settings.get("M", 3)),
        beta1=float(settings.get("beta1", 0.1)),
        beta2=float(settings.get("beta2", 0.1)),
        dream_every=int(settings.get("dream_every", 1)),
        seed=int(settings.get("seed", 0)),
    )


def forest_path(settings: Optional[Dict[str, Any]] = None) -> Path:
    settings = settings or load_settings()
    return Path(settings.get("data_dir", "data/dream")) / "forest.json"


def load_forest(settings: Optional[Dict[str, Any]] = None) -> DiscoveryForest:
    path = forest_path(settings)
    if path.exists():
        try:
            return DiscoveryForest.load(path)
        except Exception as e:  # noqa: BLE001
            logger.warning("[Dream] 历史加载失败，重建: %s", e)
    return DiscoveryForest()


def save_forest(forest: DiscoveryForest,
                settings: Optional[Dict[str, Any]] = None) -> None:
    try:
        forest.save(forest_path(settings))
    except Exception as e:  # noqa: BLE001
        logger.warning("[Dream] 历史保存失败: %s", e)


def make_developer(nlu_service=None, seed: int = 0):
    """构建 policy-development agent：优先 LLM，无 LLM 时参数化进化。"""
    parametric = ParametricDeveloper(seed=seed)
    ask = None
    if nlu_service is not None and hasattr(nlu_service, "ask_llm"):
        def ask(prompt: str) -> str:
            return nlu_service.ask_llm(prompt, [])
    if ask is None:
        return parametric
    return LLMDeveloper(ask_llm=ask, fallback=parametric)


class SkillAttemptAdapter:
    """discovery agent 适配骨架：把 CONTINUE 接到 Butler 的 skill 执行链。

    用法（示例）：
        adapter = SkillAttemptAdapter(
            generate=lambda ws: {"skill": "...", "params": {...}},   # 生成候选
            execute=lambda ws: run_skill(ws["skill"], ws["params"]), # 执行并评分
            score_of=lambda result: float(result["score"]),
        )
        orch = DreamOrchestrator(adapter.attempt, policy, ...)
    真实接入点：butler/core/skill_manager.py（执行）+ verification/（评分）。
    """

    def __init__(self,
                 generate: Callable[[Dict[str, Any]], Dict[str, Any]],
                 execute: Callable[[Dict[str, Any]], Any],
                 score_of: Callable[[Any], float],
                 diagnostics_of: Optional[Callable[[Any], Dict[str, Any]]] = None):
        self.generate = generate
        self.execute = execute
        self.score_of = score_of
        self.diagnostics_of = diagnostics_of or (lambda r: {})

    def attempt(self, parent_workspace: Dict[str, Any]) -> AttemptResult:
        ws = self.generate(parent_workspace)
        result = self.execute(ws)
        return AttemptResult(
            workspace=ws,
            score=float(self.score_of(result)),
            artifact=result,
            diagnostics=dict(self.diagnostics_of(result)),
        )


def build_orchestrator(attempt_fn: Callable[[Dict[str, Any]], AttemptResult],
                       policy: Optional[ExplorationPolicy] = None,
                       nlu_service=None,
                       settings: Optional[Dict[str, Any]] = None
                       ) -> DreamOrchestrator:
    """装配一个接入 Butler 的 Dream 编排器（自动加载历史森林）。"""
    settings = settings or load_settings()
    cfg = config_from_settings(settings)
    policy = policy or AdaptivePolicy(seed=cfg.seed)
    forest = load_forest(settings)
    return DreamOrchestrator(
        attempt_fn=attempt_fn,
        policy=policy,
        config=cfg,
        forest=forest,
        developer=make_developer(nlu_service, seed=cfg.seed),
    )


def install_dream_engine_hook(dream_engine,
                              attempt_fn_factory: Optional[Callable[[], Callable]] = None
                              ) -> None:
    """给 DreamEngine（做梦引擎）挂接 RSI 做梦阶段。

    DreamEngine.dream() 原有"记忆整合"流程保持不变；
    追加阶段在历史非空时执行策略自改进（离线回放），并落盘历史。
    attempt_fn_factory：延迟构造 discovery agent（无则只做策略回放，
    仍可从已有历史中改进策略）。
    """
    original = dream_engine.dream

    def dream_with_rsi(*args, **kwargs):
        result = original(*args, **kwargs)
        try:
            settings = load_settings()
            if not settings.get("enabled", True):
                return result
            forest = load_forest(settings)
            if len(forest) == 0:
                return result
            cfg = config_from_settings(settings)
            developer = make_developer(
                getattr(dream_engine, "jarvis", None) and
                getattr(dream_engine.jarvis, "nlu_service", None),
                seed=cfg.seed)
            orch = DreamOrchestrator(
                attempt_fn=(attempt_fn_factory() if attempt_fn_factory
                            else (lambda ws: AttemptResult(ws, 0.0))),
                policy=AdaptivePolicy(seed=cfg.seed),
                config=cfg, forest=forest, developer=developer)
            report = orch.dream_phase()
            if report is not None:
                save_forest(forest, settings)
                logger.info("[Dream] DreamEngine 挂接做梦完成: %s",
                            report.summary())
        except Exception as e:  # noqa: BLE001
            logger.warning("[Dream] DreamEngine 挂接阶段失败: %s", e)
        return result

    dream_engine.dream = dream_with_rsi
