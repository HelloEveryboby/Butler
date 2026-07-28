"""TypedConfig 强类型配置模型单元测试。"""

import pytest

from butler.core.config_model import (
    ApiConfig,
    ApiGatewayConfig,
    RunnerServerConfig,
    SecurityError,
    load_config_from_env,
)


class TestApiConfig:
    """ApiConfig 测试。"""

    def test_ai_available_with_key(self):
        """有有效密钥时 ai_available 为 True。"""
        config = ApiConfig(deepseek_key="sk-real-key-12345")
        assert config.ai_available is True

    def test_ai_not_available_without_key(self):
        """无密钥时 ai_available 为 False。"""
        config = ApiConfig()
        assert config.ai_available is False

    def test_ai_not_available_with_placeholder(self):
        """占位符密钥 ai_available 为 False。"""
        config = ApiConfig(deepseek_key="YOUR_DEEPSEEK_KEY")
        assert config.ai_available is False


class TestRunnerServerConfig:
    """RunnerServerConfig 安全测试。"""

    def test_default_localhost(self):
        """默认绑定 localhost。"""
        config = RunnerServerConfig()
        assert config.host == "127.0.0.1"

    def test_placeholder_token_raises(self):
        """占位符 token 触发 SecurityError。"""
        config = RunnerServerConfig(token="BUTLER_TOKEN_PLACEHOLDER")
        with pytest.raises(SecurityError):
            config.get_token()

    def test_old_placeholder_token_raises(self):
        """旧版占位符 token 也触发 SecurityError。"""
        config = RunnerServerConfig(token="YOUR_RUNNER_SERVER_TOKEN_HERE")
        with pytest.raises(SecurityError):
            config.get_token()

    def test_valid_token_from_env(self, monkeypatch):
        """环境变量提供有效 token。"""
        monkeypatch.setenv("BUTLER_RUNNER_TOKEN", "secure_token_from_env_12345")
        config = RunnerServerConfig()
        assert config.get_token() == "secure_token_from_env_12345"

    def test_token_from_vault(self):
        """从 SecretVault 获取 token。"""
        from unittest.mock import MagicMock

        vault = MagicMock()
        vault._master_key = b"fake_key"
        vault.get_secret.return_value = "vault_secret_token_67890"
        config = RunnerServerConfig()
        assert config.get_token(vault) == "vault_secret_token_67890"


class TestApiGatewayConfig:
    """ApiGatewayConfig 安全测试。"""

    def test_default_localhost(self):
        """默认绑定 localhost。"""
        config = ApiGatewayConfig()
        assert config.host == "127.0.0.1"

    def test_placeholder_raises(self):
        """占位符 token 触发 SecurityError。"""
        with pytest.raises(SecurityError):
            config = ApiGatewayConfig()
            config.get_token()


class TestLoadConfigFromEnv:
    """load_config_from_env 测试。"""

    def test_load_deepseek_key(self, monkeypatch):
        """从环境变量加载 DeepSeek 密钥。"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-12345")
        config = load_config_from_env()
        assert config.api.deepseek_key == "sk-test-12345"

    def test_load_runner_port(self, monkeypatch):
        """从环境变量加载 Runner 端口。"""
        monkeypatch.setenv("BUTLER_RUNNER_PORT", "9000")
        config = load_config_from_env()
        assert config.runner_server.port == 9000

    def test_default_values(self):
        """未设置环境变量时使用默认值。"""
        config = load_config_from_env()
        assert config.runner_server.host == "127.0.0.1"
        assert config.api_gateway.host == "127.0.0.1"
        assert config.api_gateway.use_ssl is True
