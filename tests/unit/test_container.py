"""AppContainer 依赖注入容器单元测试。"""

import pytest

from butler.core.container import AppContainer, ServiceSpec


class SimpleService:
    def __init__(self, name="default"):
        self.name = name


class DependentService:
    def __init__(self, dep: SimpleService):
        self.dep = dep


class TestAppContainer:
    """AppContainer 核心功能测试。"""

    def test_resolve_singleton(self):
        """单例服务只实例化一次。"""
        call_count = 0

        def factory(c):
            nonlocal call_count
            call_count += 1
            return SimpleService()

        container = AppContainer({"svc": ServiceSpec(factory)})
        a = container.resolve("svc")
        b = container.resolve("svc")
        assert a is b
        assert call_count == 1

    def test_resolve_non_singleton(self):
        """非单例服务每次返回新实例。"""
        container = AppContainer({
            "svc": ServiceSpec(lambda c: SimpleService(), singleton=False)
        })
        a = container.resolve("svc")
        b = container.resolve("svc")
        assert a is not b

    def test_dependency_injection(self):
        """服务可以通过容器访问其他服务。"""
        container = AppContainer({
            "simple": ServiceSpec(lambda c: SimpleService("base")),
            "dependent": ServiceSpec(lambda c: DependentService(c.resolve("simple"))),
        })
        dep = container.resolve("dependent")
        assert dep.dep.name == "base"

    def test_resolve_all_eager(self):
        """lazy=False 的服务在 resolve_all 时被立即实例化。"""
        created = []

        def factory(c):
            created.append("svc")
            return SimpleService()

        container = AppContainer({
            "svc": ServiceSpec(factory, lazy=False),
            "lazy_svc": ServiceSpec(lambda c: SimpleService(), lazy=True),
        })
        container.resolve_all()
        assert "svc" in created
        assert len(container._instances) >= 1

    def test_unknown_service_raises(self):
        """解析未注册的服务抛出 KeyError。"""
        container = AppContainer({})
        with pytest.raises(KeyError, match="未注册的服务"):
            container.resolve("nonexistent")

    def test_circular_dependency_detected(self):
        """循环依赖被检测并抛出 RuntimeError。"""
        container = AppContainer({
            "a": ServiceSpec(lambda c: c.resolve("b")),
            "b": ServiceSpec(lambda c: c.resolve("a")),
        })
        with pytest.raises(RuntimeError, match="循环依赖"):
            container.resolve("a")

    def test_override_for_testing(self):
        """override 方法用预构建实例替换服务。"""
        container = AppContainer({
            "svc": ServiceSpec(lambda c: SimpleService("original"))
        })
        mock = SimpleService("mock")
        container.override("svc", mock)
        assert container.resolve("svc") is mock

    def test_reset_clears_instances(self):
        """reset 清除缓存的单例。"""
        container = AppContainer({
            "svc": ServiceSpec(lambda c: SimpleService())
        })
        a = container.resolve("svc")
        container.reset()
        b = container.resolve("svc")
        assert a is not b

    def test_has_registered(self):
        """has 方法正确报告注册状态。"""
        container = AppContainer({"svc": ServiceSpec(lambda c: SimpleService())})
        assert container.has("svc")
        assert not container.has("nonexistent")

    def test_register_dynamic(self):
        """运行时动态注册新服务。"""
        container = AppContainer({})
        container.register("svc", ServiceSpec(lambda c: SimpleService("dynamic")))
        assert container.resolve("svc").name == "dynamic"

    def test_registered_names(self):
        """registered_names 返回所有已注册服务名。"""
        container = AppContainer({
            "a": ServiceSpec(lambda c: 1),
            "b": ServiceSpec(lambda c: 2),
        })
        assert set(container.registered_names) == {"a", "b"}
