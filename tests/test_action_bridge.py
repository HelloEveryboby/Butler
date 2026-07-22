"""
Butler ActionBridge 测试

覆盖 REST API 调用、Webhook 触发、模板匹配。
"""

import pytest
from unittest.mock import patch, MagicMock
from butler.core.action_bridge import ActionBridge


@pytest.fixture
def bridge():
    return ActionBridge()


class TestActionBridgeInit:
    """初始化测试"""

    def test_templates_exist(self, bridge):
        assert "ifttt" in bridge.templates
        assert "feishu" in bridge.templates
        assert "notion" in bridge.templates
        assert "webhook_generic" in bridge.templates

    def test_ifttt_template(self, bridge):
        assert "{event}" in bridge.templates["ifttt"]
        assert "{key}" in bridge.templates["ifttt"]


class TestCallAPI:
    """REST API 调用测试"""

    @patch("butler.core.action_bridge.requests")
    def test_post_success(self, mock_requests, bridge):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = bridge.call_api("https://example.com/api", method="POST", data={"msg": "hi"})

        assert result["success"] is True
        assert result["data"] == {"ok": True}
        mock_requests.post.assert_called_once()

    @patch("butler.core.action_bridge.requests")
    def test_get_success(self, mock_requests, bridge):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"items": [1, 2]}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.get.return_value = mock_resp

        result = bridge.call_api("https://example.com/api", method="GET")

        assert result["success"] is True
        mock_requests.get.assert_called_once()

    @patch("butler.core.action_bridge.requests")
    def test_unsupported_method(self, mock_requests, bridge):
        result = bridge.call_api("https://example.com", method="PATCH")
        assert result["success"] is False
        assert "Unsupported method" in result["error"]

    @patch("butler.core.action_bridge.requests")
    def test_network_error(self, mock_requests, bridge):
        mock_requests.post.side_effect = ConnectionError("timeout")
        result = bridge.call_api("https://example.com", method="POST")
        assert result["success"] is False
        assert "timeout" in result["error"]

    @patch("butler.core.action_bridge.requests")
    def test_non_json_response(self, mock_requests, bridge):
        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("not json")
        mock_resp.text = "plain text"
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = bridge.call_api("https://example.com", method="POST")
        assert result["success"] is True
        assert result["data"] == {"text": "plain text"}


class TestTriggerWebhook:
    """Webhook 触发测试"""

    @patch("butler.core.action_bridge.requests")
    def test_ifttt_webhook(self, mock_requests, bridge):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = bridge.trigger_webhook(
            "test",
            {"value1": "hello"},
            {"template": "ifttt", "event": "my_event", "key": "my_key"},
        )

        assert result["success"] is True
        # 验证 URL 模板被正确替换
        call_args = mock_requests.post.call_args
        assert "my_event" in call_args[0][0]
        assert "my_key" in call_args[0][0]

    @patch("butler.core.action_bridge.requests")
    def test_generic_webhook(self, mock_requests, bridge):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status = MagicMock()
        mock_requests.post.return_value = mock_resp

        result = bridge.trigger_webhook(
            "test",
            {"data": 123},
            {"url": "https://my-server.com/hook"},
        )

        assert result["success"] is True

    def test_missing_url_and_template(self, bridge):
        result = bridge.trigger_webhook("test", {}, {})
        assert result["success"] is False
        assert "No URL" in result["error"]

    def test_missing_template_params(self, bridge):
        result = bridge.trigger_webhook(
            "test",
            {},
            {"template": "ifttt"},  # 缺少 event 和 key
        )
        assert result["success"] is False
        assert "Missing required parameter" in result["error"]
