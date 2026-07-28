"""API 健康检查探针测试。"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from butler.core.api import app


class TestHealthProbes:
    """/healthz 和 /readyz 探针测试。"""

    def test_healthz_returns_ok(self):
        """存活探针始终返回 200 ok。"""
        client = TestClient(app)
        resp = client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_healthz_no_auth_required(self):
        """存活探针不需要认证。"""
        client = TestClient(app)
        resp = client.get("/healthz")
        assert resp.status_code == 200

    def test_readyz_returns_structure(self):
        """就绪探针返回结构化依赖状态。"""
        client = TestClient(app)
        resp = client.get("/readyz")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall" in data
        assert "dependencies" in data

    def test_readyz_no_auth_required(self):
        """就绪探针不需要认证。"""
        client = TestClient(app)
        resp = client.get("/readyz")
        assert resp.status_code == 200

    def test_readyz_includes_vault_status(self):
        """就绪探针包含 SecretVault 状态。"""
        client = TestClient(app)
        resp = client.get("/readyz")
        data = resp.json()
        assert "secret_vault" in data["dependencies"]

    def test_readyz_includes_nlu_status(self):
        """就绪探针包含 NLU Service 状态。"""
        client = TestClient(app)
        resp = client.get("/readyz")
        data = resp.json()
        assert "nlu_service" in data["dependencies"]

    def test_readyz_includes_runner_status(self):
        """就绪探针包含 Runner Server 状态。"""
        client = TestClient(app)
        resp = client.get("/readyz")
        data = resp.json()
        assert "runner_server" in data["dependencies"]

    def test_readyz_includes_circuit_breaker_status(self):
        """就绪探针包含熔断器状态。"""
        client = TestClient(app)
        resp = client.get("/readyz")
        data = resp.json()
        assert "intent_circuit_breakers" in data["dependencies"]
