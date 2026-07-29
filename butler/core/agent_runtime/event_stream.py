"""
事件流 — 追加式事件日志 + 确定性重放。

参考架构：OpenHands 的事件溯源（EventStream）架构。

事件日志是"追加唯一的真相源"：
    - 所有 agent 行为（消息、工具调用、工具结果、权限请求、压缩等）
      都通过事件记录
    - 支持确定性重放（deterministic replay）
    - 支持订阅/发布模式，用于可观测性、调试、自定义日志

事件类型：
    - MESSAGE: 用户/助手消息
    - TOOL_CALL: 工具调用请求
    - TOOL_RESULT: 工具执行结果
    - TOOL_ERROR: 工具执行错误
    - PERMISSION_REQUEST: 权限确认请求
    - PERMISSION_RESPONSE: 权限确认响应
    - COMPACTION: 上下文压缩事件
    - SUBAGENT_SPAWN: 子代理生成
    - SUBAGENT_RETURN: 子代理返回
    - ERROR: 系统错误
    - STOP: 循环终止
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from pathlib import Path
from typing import Callable

from .types import Event, EventType

logger = logging.getLogger(__name__)

# 订阅者回调类型
EventCallback = Callable[[Event], None]


class EventStream:
    """
    追加式事件流。

    核心设计：
        1. 所有事件追加到内存日志（deque，有界）
        2. 支持订阅/发布：订阅者回调在事件追加时触发
        3. 支持持久化：可导出为 JSON 文件
        4. 支持重放：从 JSON 文件恢复并重新执行

    使用方式::

        stream = EventStream(max_events=10000)

        # 订阅事件
        stream.subscribe(EventType.TOOL_CALL, lambda e: print(f"Tool: {e.data}"))

        # 追加事件
        stream.emit(Event.create(EventType.MESSAGE, role="user", content="hello"))

        # 持久化
        stream.save_to_file("session.json")

        # 重放
        stream2 = EventStream.load_from_file("session.json")
    """

    def __init__(self, max_events: int = 10000):
        self._events: deque[Event] = deque(maxlen=max_events)
        self._subscribers: dict[EventType, list[EventCallback]] = {}
        self._global_subscribers: list[EventCallback] = []
        self._lock = threading.RLock()

    def emit(self, event: Event) -> None:
        """
        追加事件到流并通知订阅者。

        参数:
            event: 要追加的事件
        """
        with self._lock:
            self._events.append(event)

        # 通知类型特定订阅者
        callbacks = self._subscribers.get(event.type, [])
        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event subscriber error for {event.type}: {e}", exc_info=True)

        # 通知全局订阅者
        for callback in self._global_subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Global event subscriber error: {e}", exc_info=True)

    def subscribe(self, event_type: EventType, callback: EventCallback) -> None:
        """订阅特定类型的事件。"""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def subscribe_all(self, callback: EventCallback) -> None:
        """订阅所有事件。"""
        with self._lock:
            self._global_subscribers.append(callback)

    def unsubscribe(self, event_type: EventType, callback: EventCallback) -> None:
        """取消订阅。"""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass

    @property
    def events(self) -> list[Event]:
        """获取所有事件（副本）。"""
        with self._lock:
            return list(self._events)

    def get_events_by_type(self, event_type: EventType) -> list[Event]:
        """获取特定类型的所有事件。"""
        with self._lock:
            return [e for e in self._events if e.type == event_type]

    def get_recent(self, count: int) -> list[Event]:
        """获取最近的 N 个事件。"""
        with self._lock:
            return list(self._events)[-count:]

    def __len__(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        """清空事件流。"""
        with self._lock:
            self._events.clear()

    def save_to_file(self, path: str | Path) -> None:
        """
        持久化事件流到 JSON 文件。

        参数:
            path: 文件路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 1,
            "event_count": len(self._events),
            "events": [
                {
                    "id": e.id,
                    "type": e.type.value,
                    "data": e.data,
                    "timestamp": e.timestamp,
                }
                for e in self._events
            ],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(self._events)} events to {path}")

    @classmethod
    def load_from_file(cls, path: str | Path) -> EventStream:
        """
        从 JSON 文件加载事件流。

        参数:
            path: 文件路径

        返回:
            EventStream: 恢复的事件流
        """
        path = Path(path)
        stream = cls()

        if not path.exists():
            return stream

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        for event_data in data.get("events", []):
            try:
                event_type = EventType(event_data["type"])
            except ValueError:
                continue

            event = Event(
                id=event_data["id"],
                type=event_type,
                data=event_data["data"],
                timestamp=event_data["timestamp"],
            )
            stream._events.append(event)

        logger.info(f"Loaded {len(stream._events)} events from {path}")
        return stream

    def replay(
        self,
        callback: EventCallback | None = None,
        event_types: list[EventType] | None = None,
    ) -> list[Event]:
        """
        重放事件流。

        参数:
            callback: 可选的重放回调
            event_types: 可选的事件类型过滤

        返回:
            匹配的事件列表
        """
        matched: list[Event] = []
        for event in list(self._events):
            if event_types and event.type not in event_types:
                continue
            matched.append(event)
            if callback:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Replay callback error: {e}", exc_info=True)
        return matched

    def get_summary(self) -> dict[str, int]:
        """获取事件流摘要统计。"""
        with self._lock:
            counts: dict[str, int] = {}
            for event in self._events:
                key = event.type.value
                counts[key] = counts.get(key, 0) + 1
            return counts
