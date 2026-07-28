"""SelfHealing 自愈系统规则引擎单元测试。"""

from unittest.mock import MagicMock

from butler.core.self_healing import SelfHealing, _match_rules, _FALLBACK_RULES


class TestRuleEngine:
    """规则引擎快速匹配测试。"""

    def test_timeout_error_matched(self):
        """超时错误匹配 retry 策略。"""
        result = _match_rules("Connection timed out after 30s")
        assert result is not None
        assert result["strategy"] == "retry"
        assert "超时" in result["explanation"]

    def test_connection_refused_matched(self):
        """连接拒绝匹配 retry 策略。"""
        result = _match_rules("ConnectionRefusedError: connection refused")
        assert result is not None
        assert result["strategy"] == "retry"

    def test_rate_limit_matched(self):
        """速率限制匹配 retry 策略。"""
        result = _match_rules("HTTP 429: Too Many Requests")
        assert result is not None
        assert result["strategy"] == "retry"
        assert result["parameters"]["delay"] == 30

    def test_module_not_found_matched(self):
        """模块缺失匹配 fallback 策略。"""
        result = _match_rules("ModuleNotFoundError: No module named 'foo'")
        assert result is not None
        assert result["strategy"] == "fallback"
        assert result["parameters"]["tool"] == "pip_install"

    def test_permission_denied_matched(self):
        """权限拒绝匹配 abort 策略。"""
        result = _match_rules("PermissionError: [Errno 13] Permission denied")
        assert result is not None
        assert result["strategy"] == "abort"

    def test_file_not_found_matched(self):
        """文件未找到匹配 fallback 策略。"""
        result = _match_rules("FileNotFoundError: No such file or directory")
        assert result is not None
        assert result["strategy"] == "fallback"
        assert result["parameters"]["tool"] == "search_file"

    def test_syntax_error_matched(self):
        """语法错误匹配 fallback 策略。"""
        result = _match_rules("SyntaxError: invalid syntax")
        assert result is not None
        assert result["strategy"] == "fallback"

    def test_oom_matched(self):
        """内存不足匹配 abort 策略。"""
        result = _match_rules("MemoryError: out of memory")
        assert result is not None
        assert result["strategy"] == "abort"

    def test_no_match_returns_none(self):
        """未匹配的错误返回 None。"""
        result = _match_rules("一些完全无法识别的奇怪错误消息")
        assert result is None

    def test_rule_has_all_fields(self):
        """规则匹配结果包含所有必需字段。"""
        result = _match_rules("connection refused")
        assert result is not None
        assert "strategy" in result
        assert "parameters" in result
        assert "explanation" in result
        assert "analysis" in result


class TestSelfHealingIntegration:
    """SelfHealing 集成测试。"""

    def test_rule_hit_skips_llm(self):
        """规则命中时不调用 LLM。"""
        mock_app = MagicMock()
        mock_app.nlu_service.ask_llm.return_value = '{"strategy": "ignore"}'
        healing = SelfHealing(mock_app)

        result = healing.analyze_failure("Connection timed out", {"intent": "test"})
        assert result["strategy"] == "retry"
        mock_app.nlu_service.ask_llm.assert_not_called()

    def test_rule_miss_falls_to_llm(self):
        """规则未命中时降级到 LLM。"""
        mock_app = MagicMock()
        mock_app.nlu_service.ask_llm.return_value = (
            '{"strategy": "ignore", "explanation": "已知问题，忽略。"}'
        )
        healing = SelfHealing(mock_app)

        result = healing.analyze_failure("一些非常特殊的错误", {"intent": "test"})
        assert result["strategy"] == "ignore"
        mock_app.nlu_service.ask_llm.assert_called_once()

    def test_llm_failure_returns_abort(self):
        """LLM 分析失败时返回 abort。"""
        mock_app = MagicMock()
        mock_app.nlu_service.ask_llm.side_effect = Exception("LLM 不可用")
        healing = SelfHealing(mock_app)

        result = healing.analyze_failure("特殊错误", {"intent": "test"})
        assert result["strategy"] == "abort"
        assert "未命中" in result["explanation"]

    def test_add_custom_rule(self):
        """动态添加规则可以被匹配。"""
        mock_app = MagicMock()
        healing = SelfHealing(mock_app)

        healing.add_rule(
            pattern=r"custom_error_\d+",
            strategy="retry",
            parameters={"delay": 10},
            explanation="自定义错误重试",
        )

        result = healing.analyze_failure("custom_error_42 occurred", {})
        assert result["strategy"] == "retry"
        assert result["explanation"] == "自定义错误重试"
