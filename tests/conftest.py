"""
Butler 测试共享 fixture。
提供 mock container、mock LLM、临时数据库等基础设施。
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db_path(tmp_path):
    """提供临时 SQLite 数据库路径。"""
    return tmp_path / "test_butler.db"


@pytest.fixture
def mock_nlu_service():
    """模拟 NLUService，不调用真实 LLM API。"""
    service = MagicMock()
    service.ask_llm.return_value = "模拟回复"
    service.extract_intent.return_value = {"intent": "unknown", "entities": {}}
    service.estimate_tokens.return_value = 100
    service.compress_history.return_value = []
    return service


@pytest.fixture
def mock_container():
    """模拟 AppContainer，提供 resolve 接口。"""
    container = MagicMock()
    container.resolve.return_value = MagicMock()
    return container


@pytest.fixture
def mock_secret_vault(monkeypatch):
    """模拟 SecretVault，避免触碰真实系统密钥链。"""
    vault = MagicMock()
    vault.get_secret.return_value = "test_secure_token_12345"
    vault.set_secret.return_value = None
    vault.list_secrets.return_value = ["runner_token", "rest_api_bearer_token"]
    vault.initialize.return_value = True
    return vault
