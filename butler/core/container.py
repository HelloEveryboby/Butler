"""
Butler 依赖注入容器 (AppContainer)。

替代旧版 Jarvis.__init__ 中的手动服务实例化链。
每个服务声明自己依赖什么，容器负责按拓扑序实例化。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ServiceSpec:
    """服务声明规格。"""

    factory: Callable[[AppContainer], Any]
    """工厂函数，接收容器自身，返回服务实例。"""

    singleton: bool = True
    """是否单例（默认 True）。"""

    lazy: bool = True
    """是否懒加载（默认 True）。设为 False 时 resolve_all 会立即实例化。"""


class AppContainer:
    """
    声明式依赖注入容器。

    使用方式::

        container = AppContainer({
            "event_bus": ServiceSpec(lambda c: EventBus(), lazy=False),
            "nlu_service": ServiceSpec(lambda c: NLUService(
                c.resolve("config").api.deepseek_key
            )),
        })
        nlu = container.resolve("nlu_service")
    """

    def __init__(self, specs: dict[str, ServiceSpec]):
        self._specs = specs
        self._instances: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._resolving: set[str] = set()

    def resolve(self, name: str) -> Any:
        """
        按名称解析服务。

        如果服务尚未实例化且是单例，则调用工厂创建并缓存。
        工厂函数可以通过容器自身访问其他服务（依赖注入）。
        """
        with self._lock:
            if name in self._instances:
                return self._instances[name]

            if name not in self._specs:
                raise KeyError(f"未注册的服务: '{name}'")

            if name in self._resolving:
                raise RuntimeError(
                    f"检测到循环依赖: {' -> '.join(self._resolving)} -> {name}"
                )

            self._resolving.add(name)
            try:
                spec = self._specs[name]
                instance = spec.factory(self)
                if spec.singleton:
                    self._instances[name] = instance
                logger.debug(f"已解析服务: {name} -> {type(instance).__name__}")
                return instance
            finally:
                self._resolving.discard(name)

    def resolve_all(self) -> dict[str, Any]:
        """按声明顺序实例化所有非 lazy 服务。"""
        for name, spec in self._specs.items():
            if not spec.lazy:
                self.resolve(name)
        return dict(self._instances)

    def has(self, name: str) -> bool:
        """检查服务是否已注册。"""
        return name in self._specs

    def register(self, name: str, spec: ServiceSpec) -> None:
        """运行时动态注册服务。"""
        with self._lock:
            if name in self._specs:
                logger.warning(f"覆盖已注册的服务: {name}")
            self._specs[name] = spec

    def override(self, name: str, instance: Any) -> None:
        """
        用预构建实例覆盖服务（用于测试）。

        覆盖后 resolve 将直接返回该实例，不再调用工厂。
        """
        with self._lock:
            self._instances[name] = instance

    def reset(self) -> None:
        """清除所有已实例化的单例（保留注册规格）。"""
        with self._lock:
            self._instances.clear()

    def shutdown_all(self) -> None:
        """
        按依赖拓扑逆序关闭所有服务。

        遍历已实例化的服务，调用其 shutdown() 方法（如果存在）。
        确保资源释放顺序与初始化顺序相反，避免提前关闭被依赖的服务。
        """
        with self._lock:
            # 逆序关闭：后实例化的服务通常依赖先实例化的
            sorted_names = reversed(list(self._instances.keys()))
            closed: list[str] = []
            failed: list[str] = []

            for name in sorted_names:
                instance = self._instances[name]
                shutdown_fn = getattr(instance, "shutdown", None)
                if callable(shutdown_fn):
                    try:
                        logger.debug(f"正在关闭服务: {name}")
                        shutdown_fn()
                        closed.append(name)
                    except Exception as e:
                        logger.warning(f"服务 '{name}' 关闭失败: {e}")
                        failed.append(name)

            self._instances.clear()
            logger.info(
                f"容器关闭完成: {len(closed)} 个服务已关闭"
                + (f", {len(failed)} 个失败" if failed else "")
            )

    @property
    def registered_names(self) -> list[str]:
        """返回所有已注册的服务名。"""
        return list(self._specs.keys())
