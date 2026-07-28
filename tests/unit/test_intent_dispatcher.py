"""IntentDispatcher 统一策略总线单元测试。"""

from butler.core.intent_dispatcher import IntentRegistry


class TestIntentRegistry:
    """IntentRegistry 核心功能测试。"""

    def test_register_local_intent(self):
        """注册 local 意图。"""
        registry = IntentRegistry()

        @registry.register("test_local", source="local")
        def handler(**kwargs):
            return "local_result"

        result = registry.dispatch("test_local")
        assert result == "local_result"

    def test_register_llm_intent(self):
        """注册 LLM 意图并通过 dispatch_by_llm_intent 分发。"""
        registry = IntentRegistry()

        @registry.register("test_llm", source="llm")
        def handler(entities, **kwargs):
            return f"llm_result_{entities.get('val')}"

        found, result = registry.dispatch_by_llm_intent("test_llm", entities={"val": 42})
        assert found is True
        assert result == "llm_result_42"

    def test_llm_dispatch_not_found(self):
        """未注册的 LLM intent 返回 (False, None)。"""
        registry = IntentRegistry()
        found, result = registry.dispatch_by_llm_intent("nonexistent")
        assert found is False
        assert result is None

    def test_local_intent_not_dispatched_by_llm(self):
        """local 意图不会被 dispatch_by_llm_intent 找到。"""
        registry = IntentRegistry()

        @registry.register("local_only", source="local")
        def handler(**kwargs):
            return "should_not_reach"

        found, result = registry.dispatch_by_llm_intent("local_only")
        assert found is False

    def test_llm_intent_handler_error_caught(self):
        """LLM handler 抛异常时返回 (True, {error: ...})。"""
        registry = IntentRegistry()

        @registry.register("buggy", source="llm")
        def handler(**kwargs):
            raise ValueError("boom")

        found, result = registry.dispatch_by_llm_intent("buggy")
        assert found is True
        assert "error" in result

    def test_get_all_intents(self):
        """get_all_intents 返回所有意图的 docstring。"""
        registry = IntentRegistry()

        @registry.register("intent_a", source="llm")
        def handler_a(**kwargs):
            """意图 A 文档。"""
            pass

        @registry.register("intent_b", source="local")
        def handler_b(**kwargs):
            """意图 B 文档。"""
            pass

        all_intents = registry.get_all_intents()
        assert "intent_a" in all_intents
        assert "intent_b" in all_intents
        assert "意图 A 文档" in all_intents["intent_a"]

    def test_dispatch_unknown_returns_none(self):
        """dispatch 未注册意图返回 None。"""
        registry = IntentRegistry()
        assert registry.dispatch("nonexistent") is None
