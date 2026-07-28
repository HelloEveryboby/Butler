"""EventBus 增强功能单元测试。"""

import threading
import time

import pytest

from butler.core.event_bus import EventBus


class TestEventBusSync:
    """同步 emit 测试。"""

    def test_sync_emit_calls_all_subscribers(self):
        """同步 emit 调用所有订阅者。"""
        bus = EventBus()
        results = []
        bus.subscribe("test", lambda x: results.append(x))
        bus.emit("test", "hello")
        assert results == ["hello"]

    def test_error_isolation(self):
        """一个回调异常不影响其他回调。"""
        bus = EventBus()
        results = []
        bus.subscribe("test", lambda x: results.append(f"first:{x}"))
        bus.subscribe("test", lambda x: (_ for _ in ()).throw(ValueError("boom")))
        bus.subscribe("test", lambda x: results.append(f"third:{x}"))
        bus.emit("test", "val")
        assert "first:val" in results
        assert "third:val" in results


class TestEventBusAsync:
    """异步 emit_async 测试。"""

    def test_async_emit_does_not_block(self):
        """emit_async 不阻塞调用方。"""
        bus = EventBus()
        called = threading.Event()
        bus.subscribe("slow", lambda: (time.sleep(0.5), called.set()))
        start = time.time()
        bus.emit_async("slow")
        elapsed = time.time() - start
        # 应该立即返回（远小于 0.5s）
        assert elapsed < 0.3
        # 等待异步执行完成
        assert called.wait(timeout=2)

    def test_async_error_isolation(self):
        """异步回调异常被隔离，不影响其他回调。"""
        bus = EventBus()
        results = []
        bus.subscribe("test", lambda x: (_ for _ in ()).throw(ValueError("boom")))
        bus.subscribe("test", lambda x: results.append(x))
        bus.emit_async("test", "ok")
        time.sleep(0.3)  # 等待线程池执行
        assert "ok" in results


class TestEventBusHistory:
    """事件历史记录测试。"""

    def test_history_recorded(self):
        """启用历史后事件被记录。"""
        bus = EventBus(history_size=10)
        bus.emit("event_a", "data_a")
        bus.emit("event_b", "data_b")
        history = bus.get_history()
        assert history is not None
        assert len(history) == 2
        assert history[0]["event"] == "event_a"
        assert history[1]["event"] == "event_b"

    def test_history_disabled_by_default(self):
        """默认不记录历史。"""
        bus = EventBus()
        bus.emit("test", "data")
        assert bus.get_history() is None

    def test_history_max_size(self):
        """历史记录不超过 maxlen。"""
        bus = EventBus(history_size=3)
        for i in range(5):
            bus.emit("test", i)
        history = bus.get_history()
        assert len(history) == 3
        assert history[0]["args"] == (2,)

    def test_clear(self):
        """clear 清空订阅和历史。"""
        bus = EventBus(history_size=10)
        results = []
        bus.subscribe("test", lambda x: results.append(x))
        bus.emit("test", "data")
        bus.clear()
        # clear 后历史已清空
        assert bus.get_history() == []
        # clear 后订阅也已清空，emit 不会触发回调
        bus.emit("test", "after_clear")
        assert results == ["data"]
        # emit 后历史中只有新事件
        assert len(bus.get_history()) == 1


class TestEventBusUnsubscribe:
    """取消订阅测试。"""

    def test_unsubscribe_stops_callbacks(self):
        """取消订阅后不再收到回调。"""
        bus = EventBus()
        results = []
        cb = lambda x: results.append(x)
        bus.subscribe("test", cb)
        bus.emit("test", "first")
        bus.unsubscribe("test", cb)
        bus.emit("test", "second")
        assert results == ["first"]
