"""密钥保管意图 handler。"""

from __future__ import annotations

from typing import Any

from butler.core.intent_dispatcher import register_intent


def _get_vault(container):
    """延迟导入 SecretVault 单例，避免循环依赖。"""
    from butler.core.secret_vault import secret_vault
    return secret_vault


@register_intent("vault_set", source="llm")
def handle_vault_set(container, entities: dict[str, Any], **kwargs) -> str:
    """安全存储一个密钥。"""
    vault = _get_vault(container)
    vault.set_secret(entities.get("key"), entities.get("value"))
    return f"Secret '{entities.get('key')}' stored securely."


@register_intent("vault_get", source="llm")
def handle_vault_get(container, entities: dict[str, Any], **kwargs) -> Any:
    """获取一个已存储的密钥。"""
    vault = _get_vault(container)
    return vault.get_secret(entities.get("key"))


@register_intent("vault_list", source="llm")
def handle_vault_list(container, **kwargs) -> Any:
    """列出所有已存储的密钥名。"""
    vault = _get_vault(container)
    return vault.list_secrets()
