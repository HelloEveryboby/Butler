import collections
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# 异步执行线程池（事件回调在此执行，避免阻塞 emit 调用方）
_async_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="event-bus")


class EventBus:
    """
    内部发布/订阅系统，支持同步和异步两种分发模式。

    增强：
    - emit_async: 回调在独立线程池执行，不阻塞调用方
    - 错误隔离: 单个回调异常不影响其他回调
    - 事件历史: 可选记录最近 N 条事件用于调试
    """

    def __init__(self, history_size: int = 0):
        self._subscribers = collections.defaultdict(list)
        self._lock = threading.Lock()
        self._history: collections.deque | None = (
            collections.deque(maxlen=history_size) if history_size > 0 else None
        )

    def subscribe(self, event_type, callback):
        """订阅事件。"""
        with self._lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
                logger.debug(f"Subscribed {callback} to {event_type}")

    def unsubscribe(self, event_type, callback):
        """取消订阅。"""
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed {callback} from {event_type}")

    def emit(self, event_type, *args, **kwargs):
        """
        同步发射事件：所有回调在当前线程顺序执行。
        单个回调异常被捕获并记录，不影响后续回调。
        """
        self._record_history(event_type, args, kwargs)
        with self._lock:
            callbacks = self._subscribers[event_type][:]

        for callback in callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in callback {callback} for event {event_type}: {e}", exc_info=True)

    def emit_async(self, event_type, *args, **kwargs):
        """
        异步发射事件：回调在独立线程池执行，不阻塞调用方。
        适用于耗时回调或不需要立即确认结果的场景。
        """
        self._record_history(event_type, args, kwargs)
        with self._lock:
            callbacks = self._subscribers[event_type][:]

        for callback in callbacks:
            _async_pool.submit(self._safe_call, callback, event_type, args, kwargs)

    @staticmethod
    def _safe_call(callback, event_type, args, kwargs):
        """线程池中安全执行回调，异常被隔离。"""
        try:
            callback(*args, **kwargs)
        except Exception as e:
            logger.error(f"[async] Error in callback {callback} for event {event_type}: {e}", exc_info=True)

    def _record_history(self, event_type, args, kwargs):
        """记录事件到历史（如果启用）。"""
        if self._history is not None:
            self._history.append({
                "event": event_type,
                "args": args,
                "kwargs": kwargs,
            })

    def get_history(self) -> list[dict] | None:
        """返回事件历史快照（如果启用）。"""
        if self._history is None:
            return None
        return list(self._history)

    def clear(self):
        """清空所有订阅和历史。"""
        with self._lock:
            self._subscribers.clear()
            if self._history is not None:
                self._history.clear()


# Global instance (保留事件历史用于调试)
event_bus = EventBus(history_size=100)
