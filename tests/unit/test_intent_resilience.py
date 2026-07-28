"""IntentDispatcher 弹性层测试：超时、熔断、指标、速率限制。"""

import time

import pytest

from butler.core.intent_dispatcher import IntentRegistry


class TestMetrics:
    """指标采集测试。"""

    def test_success_metrics_recorded(self):
        """成功调用记录 success 指标。"""
        registry = IntentRegistry()

        @registry.register("ok_intent", source="llm")
        def handler(**kwargs):
            return "ok"

        registry.dispatch_by_llm_intent("ok_intent", entities={})
        metrics = registry.get_metrics()
        assert "ok_intent" in metrics
        assert metrics["ok_intent"]["success"] == 1
        assert metrics["ok_intent"]["total_ms"] > 0

    def test_failure_metrics_recorded(self):
        """失败调用记录 failure 指标。"""
        registry = IntentRegistry()

        @registry.register("bad_intent", source="llm")
        def handler(**kwargs):
            raise ValueError("boom")

        registry.dispatch_by_llm_intent("bad_intent", entities={})
        metrics = registry.get_metrics()
        assert metrics["bad_intent"]["failure"] == 1


class TestCircuitBreaker:
    """熔断器测试。"""

    def test_circuit_opens_after_threshold(self):
        """连续失败达到阈值后熔断器开启。"""
        registry = IntentRegistry()

        @registry.register("always_fail", source="llm")
        def handler(**kwargs):
            raise RuntimeError("always fails")

        # 连续失败 5 次（默认阈值）
        for _ in range(5):
            registry.dispatch_by_llm_intent("always_fail", entities={})

        # 第 6 次调用应该被熔断器拒绝
        found, result = registry.dispatch_by_llm_intent("always_fail", entities={})
        assert found is True
        assert "不可用" in result["error"]

    def test_circuit_resets_on_success(self):
        """成功调用后失败计数重置。"""
        registry = IntentRegistry()
        call_count = [0]

        @registry.register("flaky", source="llm")
        def handler(**kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("flaky")
            return "recovered"

        # 前两次失败
        registry.dispatch_by_llm_intent("flaky", entities={})
        registry.dispatch_by_llm_intent("flaky", entities={})

        # 第三次成功
        found, result = registry.dispatch_by_llm_intent("flaky", entities={})
        assert found is True
        assert result == "recovered"

        # 失败计数应被重置
        assert registry._failure_counts["flaky"] == 0

    def test_reset_circuit_breaker(self):
        """手动重置熔断器。"""
        registry = IntentRegistry()

        @registry.register("failer", source="llm")
        def handler(**kwargs):
            raise RuntimeError("fail")

        for _ in range(5):
            registry.dispatch_by_llm_intent("failer", entities={})

        # 熔断器已开启
        assert registry._circuit_breakers.get("failer", False) is True

        # 手动重置
        registry.reset_circuit_breaker("failer")
        assert registry._circuit_breakers.get("failer", False) is False
        assert registry._failure_counts["failer"] == 0

    def test_reset_all_circuit_breakers(self):
        """重置所有熔断器。"""
        registry = IntentRegistry()

        @registry.register("fail1", source="llm")
        def h1(**kwargs):
            raise RuntimeError()

        @registry.register("fail2", source="llm")
        def h2(**kwargs):
            raise RuntimeError()

        for _ in range(5):
            registry.dispatch_by_llm_intent("fail1", entities={})
            registry.dispatch_by_llm_intent("fail2", entities={})

        registry.reset_circuit_breaker()
        assert len(registry._circuit_breakers) == 0


class TestRateLimit:
    """速率限制测试。"""

    def test_rate_limit_triggers(self):
        """超过速率限制后返回错误。"""
        registry = IntentRegistry()

        @registry.register("fast", source="llm")
        def handler(**kwargs):
            return "ok"

        # 调用 60 次（默认上限）
        for i in range(60):
            found, result = registry.dispatch_by_llm_intent("fast", entities={})
            assert found is True
            assert result == "ok"

        # 第 61 次应被限流
        found, result = registry.dispatch_by_llm_intent("fast", entities={})
        assert found is True
        assert "频繁" in result["error"]
