"""Bootstrap 容器引导模块单元测试。"""

from unittest.mock import MagicMock

from butler.core.bootstrap import get_secure_api_token, get_secure_runner_token


class TestSecureTokenHelpers:
    """安全 token 获取函数测试。"""

    def test_runner_token_from_vault(self):
        """从 SecretVault 获取 runner token。"""
        vault = MagicMock()
        vault._master_key = b"fake_key"
        vault.get_secret.return_value = "vault_runner_token_12345"
        token = get_secure_runner_token(vault)
        assert token == "vault_runner_token_12345"

    def test_runner_token_fallback_to_env(self, monkeypatch):
        """vault 无 token 时回退到环境变量。"""
        vault = MagicMock()
        vault._master_key = b"fake_key"
        vault.get_secret.return_value = None
        monkeypatch.setenv("BUTLER_RUNNER_TOKEN", "env_runner_token_67890")
        token = get_secure_runner_token(vault)
        assert token == "env_runner_token_67890"

    def test_runner_token_generates_temp_when_missing(self, monkeypatch):
        """无 vault 无环境变量时生成临时 token。"""
        vault = MagicMock()
        vault._master_key = None
        monkeypatch.delenv("BUTLER_RUNNER_TOKEN", raising=False)
        token = get_secure_runner_token(vault)
        assert len(token) == 64  # token_hex(32) -> 64 chars
        assert token != "BUTLER_TOKEN_PLACEHOLDER"

    def test_runner_token_rejects_placeholder(self, monkeypatch):
        """占位符 token 被替换为安全临时 token。"""
        vault = MagicMock()
        vault._master_key = b"fake_key"
        vault.get_secret.return_value = "BUTLER_TOKEN_PLACEHOLDER"
        monkeypatch.delenv("BUTLER_RUNNER_TOKEN", raising=False)
        token = get_secure_runner_token(vault)
        assert token != "BUTLER_TOKEN_PLACEHOLDER"
        assert len(token) == 64

    def test_api_token_from_vault(self):
        """从 SecretVault 获取 API token。"""
        vault = MagicMock()
        vault._master_key = b"fake_key"
        vault.get_secret.return_value = "vault_api_token_abcde"
        token = get_secure_api_token(vault)
        assert token == "vault_api_token_abcde"

    def test_api_token_generates_temp_when_missing(self, monkeypatch):
        """无 vault 无环境变量时生成临时 API token。"""
        vault = MagicMock()
        vault._master_key = None
        monkeypatch.delenv("BUTLER_API_TOKEN", raising=False)
        token = get_secure_api_token(vault)
        assert len(token) == 64
        assert token != "BUTLER_TOKEN_PLACEHOLDER"


class TestContainerBootstrap:
    """build_container 集成测试。"""

    def test_build_container_registers_all_services(self):
        """build_container 注册了所有核心服务。"""
        from butler.core.bootstrap import build_container
        from butler.core.container import AppContainer

        mock_app = MagicMock()
        mock_app.logger = MagicMock()
        mock_app.resource_manager = MagicMock()
        mock_app.long_memory = MagicMock()
        mock_app.voice_service = MagicMock()
        mock_app.team_manager = MagicMock()
        mock_app.workflow_engine = MagicMock()
        mock_app.dream_engine = MagicMock()
        mock_app.proactive_agent = MagicMock()
        mock_app.focus_mode = MagicMock()
        mock_app.self_healing = MagicMock()
        mock_app.runner_server = MagicMock()

        mock_config_loader = MagicMock()
        mock_config_loader._config = {}
        mock_config_loader.get.return_value = None

        container = build_container(mock_app, mock_config_loader, {})

        assert isinstance(container, AppContainer)
        expected_services = [
            "app", "config", "prompts", "logger", "resource_manager",
            "long_memory", "nlu_service", "voice_service", "skill_manager",
            "local_nlu", "task_manager", "message_bus", "team_manager",
            "workflow_engine", "dream_engine", "proactive_agent",
            "focus_mode", "self_healing", "runner_server", "secret_vault",
        ]
        for name in expected_services:
            assert container.has(name), f"服务 '{name}' 未注册"

    def test_build_container_resolves_app(self):
        """container 可以解析 app 服务。"""
        from butler.core.bootstrap import build_container

        mock_app = MagicMock()
        mock_app.logger = MagicMock()
        mock_app.resource_manager = MagicMock()
        mock_app.long_memory = MagicMock()
        mock_app.voice_service = MagicMock()
        mock_app.team_manager = MagicMock()
        mock_app.workflow_engine = MagicMock()
        mock_app.dream_engine = MagicMock()
        mock_app.proactive_agent = MagicMock()
        mock_app.focus_mode = MagicMock()
        mock_app.self_healing = MagicMock()
        mock_app.runner_server = MagicMock()

        mock_config_loader = MagicMock()
        mock_config_loader._config = {}
        mock_config_loader.get.return_value = None

        container = build_container(mock_app, mock_config_loader, {})

        resolved_app = container.resolve("app")
        assert resolved_app is mock_app
