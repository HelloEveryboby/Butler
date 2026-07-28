"""
Butler 服务容器引导模块。

将 Jarvis.__init__ 中的手动服务实例化链替换为声明式 AppContainer 注册。
所有服务通过工厂函数延迟创建，依赖关系由容器按拓扑序解析。
"""

from __future__ import annotations

import logging
import os
import secrets as _secrets
from typing import TYPE_CHECKING

from butler.core.container import AppContainer, ServiceSpec

if TYPE_CHECKING:
    from butler.butler_app import Jarvis

logger = logging.getLogger(__name__)


def build_container(app: Jarvis, config_loader, prompts: dict) -> AppContainer:
    """
    构建并返回包含所有 Butler 服务的 AppContainer。

    参数:
        app: Jarvis 实例（用于回注需要 UI 回调的服务）
        config_loader: 配置加载器实例
        prompts: prompts.json 内容
    """
    specs = {
        "app": ServiceSpec(lambda c: app, singleton=True, lazy=False),
        "config": ServiceSpec(lambda c: config_loader._config, singleton=True, lazy=False),
        "prompts": ServiceSpec(lambda c: prompts, singleton=True, lazy=False),
        "logger": ServiceSpec(lambda c: app.logger, singleton=True, lazy=False),
        "resource_manager": ServiceSpec(lambda c: app.resource_manager, singleton=True, lazy=False),

        # 记忆引擎
        "long_memory": ServiceSpec(lambda c: app.long_memory, singleton=True, lazy=False),

        # NLU
        "nlu_service": ServiceSpec(
            lambda c: _create_nlu_service(c, config_loader, prompts),
            singleton=True,
            lazy=False,
        ),

        # 语音服务
        "voice_service": ServiceSpec(lambda c: app.voice_service, singleton=True, lazy=False),

        # 技能管理
        "skill_manager": ServiceSpec(
            lambda c: _create_skill_manager(c), singleton=True, lazy=False
        ),

        # 本地 NLU
        "local_nlu": ServiceSpec(
            lambda c: _create_local_nlu(c), singleton=True, lazy=False
        ),

        # 任务管理
        "task_manager": ServiceSpec(
            lambda c: _resolve_task_manager(), singleton=True, lazy=False
        ),

        # 消息总线
        "message_bus": ServiceSpec(
            lambda c: _resolve_message_bus(), singleton=True, lazy=False
        ),

        # 团队管理
        "team_manager": ServiceSpec(lambda c: app.team_manager, singleton=True, lazy=False),

        # 工作流引擎
        "workflow_engine": ServiceSpec(lambda c: app.workflow_engine, singleton=True, lazy=False),

        # KAIROS 套件
        "dream_engine": ServiceSpec(lambda c: app.dream_engine, singleton=True, lazy=False),
        "proactive_agent": ServiceSpec(lambda c: app.proactive_agent, singleton=True, lazy=False),
        "focus_mode": ServiceSpec(lambda c: app.focus_mode, singleton=True, lazy=False),
        "self_healing": ServiceSpec(lambda c: app.self_healing, singleton=True, lazy=False),

        # Runner Server
        "runner_server": ServiceSpec(lambda c: app.runner_server, singleton=True, lazy=False),

        # Secret Vault
        "secret_vault": ServiceSpec(lambda c: _resolve_secret_vault(), singleton=True, lazy=False),
    }

    container = AppContainer(specs)
    logger.debug(f"AppContainer 已构建，注册服务: {container.registered_names}")
    return container


def _create_nlu_service(container: AppContainer, config_loader, prompts: dict):
    """创建 NLU 服务实例。"""
    from butler.core.nlu_service import NLUService

    api_key = config_loader.get("api.deepseek.key")
    return NLUService(api_key, prompts)


def _create_skill_manager(container: AppContainer):
    """创建并加载技能管理器。"""
    from butler.core.skill_manager import SkillManager

    mgr = SkillManager()
    mgr.load_skills()
    mgr.start_monitoring()
    return mgr


def _create_local_nlu(container: AppContainer):
    """创建本地 NLU 实例。"""
    from butler.core.local_nlu import LocalNLU

    return LocalNLU(container.resolve("skill_manager"))


def _resolve_task_manager():
    """获取 task_manager 单例。"""
    from butler.core.task_manager import task_manager

    return task_manager


def _resolve_message_bus():
    """获取 message_bus 单例。"""
    from butler.core.message_bus import message_bus

    return message_bus


def _resolve_secret_vault():
    """获取并初始化 SecretVault 单例。"""
    from butler.core.secret_vault import secret_vault

    if not secret_vault.initialize():
        master_pwd = os.getenv("BUTLER_MASTER_PASSWORD")
        if master_pwd:
            secret_vault.initialize(master_pwd)
    return secret_vault


def get_secure_runner_token(vault) -> str:
    """从 SecretVault 或环境变量获取 Runner token，无配置时生成安全临时 token。"""
    token = None
    if vault and getattr(vault, "_master_key", None):
        token = vault.get_secret("runner_token")

    if not token:
        token = os.getenv("BUTLER_RUNNER_TOKEN")

    if not token or token == "BUTLER_TOKEN_PLACEHOLDER":
        token = _secrets.token_hex(32)
        logger.warning(
            "[Security] Runner token 未配置，已自动生成临时 token。"
            "建议通过 'butler vault set runner_token' 持久化设置。"
        )
    return token


def get_secure_api_token(vault) -> str:
    """从 SecretVault 或环境变量获取 API Gateway token，无配置时生成安全临时 token。"""
    token = None
    if vault and getattr(vault, "_master_key", None):
        token = vault.get_secret("rest_api_bearer_token")

    if not token:
        token = os.getenv("BUTLER_API_TOKEN")

    if not token or token == "BUTLER_TOKEN_PLACEHOLDER":
        token = _secrets.token_hex(32)
        logger.warning(
            "[Security] API token 未配置，已自动生成临时 token。"
            "建议设置环境变量 BUTLER_API_TOKEN 或通过 SecretVault 持久化。"
        )
    return token
