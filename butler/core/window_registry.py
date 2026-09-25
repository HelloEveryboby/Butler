# -*- coding: utf-8 -*-
"""Butler 子界面窗口注册表 —— GUI 呼吸灯的数据源。

统一登记两类"子界面"，每个子界面对应 GUI 左上角（或全屏 HUD）的一颗呼吸灯：

1. ``win:*``  独立 OS 窗口（技能子窗口 / 独立终端等）
2. ``view:*`` 主界面内可开关的子面板（终端 / 备忘录 / 设置 ...）

状态语义：
- ``idle``    窗口开着、无程序运行   -> 灯慢呼吸
- ``running`` 有存活任务 / 近期有活动 -> 灯快闪
- ``error``   任务被标记为异常        -> 灯红色常亮

用法（主进程内任意模块）::

    from butler.core.window_registry import window_registry
    window_registry.register_window('win:term', '独立终端', pid=proc.pid)
    task = window_registry.bind_task('win:term', proc, kind='handle', label='make all')
    ...
    window_registry.unbind_task('win:term', task)

无法直接引用注册表的代码（子进程 / 插件）可通过事件总线通知::

    event_bus.emit('window_activity', {'window_id': 'win:term'})
    event_bus.emit('window_opened',  {'window_id': 'win:term', 'title': '独立终端'})
    event_bus.emit('window_closed',  {'window_id': 'win:term'})
"""

import logging
import threading
import time
from typing import Any, Dict, List, Optional

try:
    import psutil
except ImportError:  # psutil 为可选依赖，缺失时退化为 os.kill 探活
    psutil = None

from butler.core.event_bus import event_bus

logger = logging.getLogger("WindowRegistry")

# 任务消失前，"有活动"状态保持的时长（秒）。终端输出等高频活动会持续续期。
ACTIVITY_QUIET_S = 2.5
# 轮询间隔（秒）
POLL_INTERVAL_S = 0.8


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    if psutil is not None:
        try:
            return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
        except Exception:
            return False
    try:
        import os
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class _Task:
    """挂在某个子界面名下的运行任务。"""

    __slots__ = ("kind", "ref", "label", "error", "deadline", "tid")

    _counter = 0
    _counter_lock = threading.Lock()

    def __init__(self, kind: str, ref: Any, label: str = "", timeout: Optional[float] = None):
        self.kind = kind          # 'pid' | 'thread' | 'handle' | 'timer'
        self.ref = ref
        self.label = label
        self.error = False
        self.deadline = (time.time() + timeout) if (kind == "timer" and timeout) else None
        with _Task._counter_lock:
            _Task._counter += 1
            self.tid = _Task._counter

    def alive(self) -> bool:
        if self.error:
            return True  # 出错任务保留在状态里，直到显式移除
        try:
            if self.kind == "pid":
                return _pid_alive(int(self.ref))
            if self.kind == "thread":
                return bool(self.ref.is_alive())
            if self.kind == "handle":   # subprocess.Popen
                return self.ref.poll() is None
            if self.kind == "timer":
                return self.deadline is not None and time.time() < self.deadline
        except Exception:
            return False
        return False


class _Entry:
    """一个子界面（窗口或面板）。"""

    def __init__(self, entry_id: str, title: str, kind: str,
                 window: Any = None, pid: Optional[int] = None,
                 transient: bool = False):
        self.id = entry_id
        self.title = title
        self.kind = kind                # 'window' | 'view'
        self.window = window            # pywebview Window（可选）
        self.pid = pid                  # 窗口进程 pid（存活即窗口开着）
        self.transient = transient      # 仅在运行/出错时显示（如主界面后台任务）
        self.tasks: List[_Task] = []
        self.last_activity = 0.0     # 仅真实活动(touch/bind/unbind)才续期；登记开窗不算活动
        self.created_at = time.time()

    def state(self) -> str:
        if any(t.error for t in self.tasks):
            return "error"
        if any(t.alive() for t in self.tasks):
            return "running"
        if time.time() - self.last_activity < ACTIVITY_QUIET_S:
            return "running"
        return "idle"


class WindowRegistry:
    """子界面窗口 + 窗口内运行任务的统一登记簿（单例见模块底部 ``window_registry``）。"""

    def __init__(self, poll_interval: float = POLL_INTERVAL_S):
        self._entries: Dict[str, _Entry] = {}
        self._lock = threading.RLock()
        self._poll_interval = poll_interval
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._active_id: Optional[str] = None
        self._last_payload: Optional[str] = None

        event_bus.subscribe("window_activity", self._on_event_activity)
        event_bus.subscribe("window_opened", self._on_event_opened)
        event_bus.subscribe("window_closed", self._on_event_closed)

    # ---------- 登记 ----------

    def register_window(self, window_id: str, title: str, *,
                        window: Any = None, pid: Optional[int] = None,
                        transient: bool = False) -> None:
        """登记一个独立 OS 子窗口。pid 给定时，进程存活即视为窗口开着。"""
        with self._lock:
            entry = self._entries.get(window_id)
            if entry is None:
                entry = _Entry(window_id, title, "window", window=window, pid=pid, transient=transient)
                self._entries[window_id] = entry
            else:
                entry.title = title or entry.title
                entry.window = window or entry.window
                entry.pid = pid or entry.pid
        self._wake()

    def register_view(self, view_id: str, title: str) -> None:
        """登记一个主界面内子面板（打开时调用）。"""
        with self._lock:
            entry = self._entries.get(view_id)
            if entry is None:
                self._entries[view_id] = _Entry(view_id, title, "view")
            else:
                entry.title = title or entry.title
        self._wake()

    def remove(self, entry_id: str) -> None:
        with self._lock:
            self._entries.pop(entry_id, None)
            if self._active_id == entry_id:
                self._active_id = None
        self._wake()

    # ---------- 任务绑定 ----------

    def bind_task(self, entry_id: str, task: Any, *, kind: str = "auto",
                  label: str = "", timeout: Optional[float] = None) -> _Task:
        """把一个运行任务挂到子界面名下（灯会闪）。kind: auto|pid|thread|handle|timer"""
        if kind == "auto":
            if isinstance(task, int):
                kind = "pid"
            elif isinstance(task, threading.Thread):
                kind = "thread"
            elif hasattr(task, "poll"):
                kind = "handle"
            else:
                kind = "thread"
        t = _Task(kind, task, label=label, timeout=timeout)
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is None:
                entry = _Entry(entry_id, entry_id, "window" if entry_id.startswith("win:") else "view")
                self._entries[entry_id] = entry
            entry.tasks.append(t)
            entry.last_activity = time.time()
        self._wake()
        return t

    def unbind_task(self, entry_id: str, task: Any) -> None:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is not None:
                entry.tasks = [t for t in entry.tasks if t is not task and t.tid != getattr(task, "tid", -1)]
                entry.last_activity = time.time()
        self._wake()

    def mark_task_error(self, entry_id: str, task: Any, error: bool = True) -> None:
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is not None:
                for t in entry.tasks:
                    if t is task or t.tid == getattr(task, "tid", -1):
                        t.error = error
        self._wake()

    # ---------- 活动与归属 ----------

    def touch(self, entry_id: str) -> None:
        """有活动（终端输出/程序交互等）时调用，灯在静默窗口内保持快闪。"""
        with self._lock:
            entry = self._entries.get(entry_id)
            if entry is not None:
                entry.last_activity = time.time()
        self._wake()

    def set_active(self, entry_id: Optional[str]) -> None:
        """记录用户最后交互的子界面，供后台任务归属（哪个界面在跑程序）。"""
        with self._lock:
            self._active_id = entry_id

    @property
    def active_entry_id(self) -> Optional[str]:
        return self._active_id

    # ---------- 查询 ----------

    def snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._reap_locked()
            return [
                {
                    "id": e.id,
                    "title": e.title,
                    "kind": e.kind,
                    "state": e.state(),
                    "transient": e.transient,
                    "task_count": sum(1 for t in e.tasks if t.alive()),
                    "detail": ", ".join(t.label for t in e.tasks if t.label and t.alive())[:80],
                }
                for e in self._entries.values()
            ]

    def focus(self, entry_id: str) -> Dict[str, Any]:
        """聚焦子界面：OS 窗口走 pywebview，面板交由前端置顶。"""
        with self._lock:
            entry = self._entries.get(entry_id)
        if entry is None:
            return {"status": "error", "message": "unknown entry"}
        if entry.kind == "window" and entry.window is not None:
            for meth in ("restore", "show", "focus", "minimize"):
                fn = getattr(entry.window, meth, None)
                if fn and meth != "minimize":
                    try:
                        fn()
                    except Exception:
                        pass
            return {"status": "ok", "kind": "window"}
        return {"status": "ok", "kind": "view", "view_id": entry.id, "title": entry.title}

    # ---------- 轮询与推送 ----------

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            if "win:main" not in self._entries:
                self._entries["win:main"] = _Entry("win:main", "主界面", "window", transient=True)
            self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="breath-light-registry", daemon=True)
        self._thread.start()
        logger.info("WindowRegistry polling started")

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.wait(self._poll_interval):
            try:
                self._tick()
            except Exception as exc:  # 呼吸灯绝不拖垮主流程
                logger.debug(f"WindowRegistry tick error: {exc}")

    def _tick(self) -> None:
        payload = self.snapshot()
        import json
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if text != self._last_payload:
            self._last_payload = text
            try:
                event_bus.emit("breath_light_states", payload)
            except Exception as exc:
                logger.debug(f"emit breath_light_states failed: {exc}")

    def _wake(self) -> None:
        """状态可能变化，尽快推送（由轮询线程统一发，避免并发 emit）。"""
        return

    def _reap_locked(self) -> None:
        dead_windows = []
        for eid, entry in self._entries.items():
            entry.tasks = [t for t in entry.tasks if t.alive() or t.error]
            if entry.kind == "window" and entry.pid and not _pid_alive(entry.pid):
                dead_windows.append(eid)
        for eid in dead_windows:
            self._entries.pop(eid, None)
            if self._active_id == eid:
                self._active_id = None

    # ---------- 事件总线入口（跨插件通知） ----------

    def _on_event_activity(self, data: Any) -> None:
        if isinstance(data, dict):
            self.touch(data.get("window_id", ""))

    def _on_event_opened(self, data: Any) -> None:
        if isinstance(data, dict) and data.get("window_id"):
            self.register_window(data["window_id"], data.get("title", data["window_id"]),
                                 pid=data.get("pid"))

    def _on_event_closed(self, data: Any) -> None:
        if isinstance(data, dict) and data.get("window_id"):
            self.remove(data["window_id"])


window_registry = WindowRegistry()
