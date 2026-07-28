"""AppContainer shutdown_all 生命周期管理测试。"""

import pytest

from butler.core.container import AppContainer, ServiceSpec


class ServiceWithShutdown:
    """带 shutdown 方法的测试服务。"""

    def __init__(self):
        self.shutdown_called = False
        self.shutdown_order = None

    def shutdown(self):
        self.shutdown_called = True


class ServiceWithoutShutdown:
    """没有 shutdown 方法的测试服务。"""

    def __init__(self):
        self.name = "no_shutdown"


class FailingShutdownService:
    """shutdown 抛异常的服务。"""

    def shutdown(self):
        raise RuntimeError("shutdown failed")


class TestShutdownAll:
    """shutdown_all 方法测试。"""

    def test_shutdown_calls_shutdown_on_services(self):
        """shutdown_all 调用所有服务的 shutdown 方法。"""
        svc_a = ServiceWithShutdown()
        svc_b = ServiceWithShutdown()

        container = AppContainer({})
        container.override("a", svc_a)
        container.override("b", svc_b)

        container.shutdown_all()

        assert svc_a.shutdown_called is True
        assert svc_b.shutdown_called is True

    def test_shutdown_skips_services_without_shutdown(self):
        """没有 shutdown 方法的服务被跳过。"""
        svc = ServiceWithoutShutdown()
        container = AppContainer({})
        container.override("svc", svc)

        # 不应抛异常
        container.shutdown_all()

    def test_shutdown_failure_does_not_block_others(self):
        """一个服务 shutdown 失败不影响其他服务。"""
        failing = FailingShutdownService()
        healthy = ServiceWithShutdown()

        container = AppContainer({})
        container.override("failing", failing)
        container.override("healthy", healthy)

        container.shutdown_all()

        assert healthy.shutdown_called is True

    def test_shutdown_clears_instances(self):
        """shutdown_all 后实例缓存被清空。"""
        svc = ServiceWithShutdown()
        container = AppContainer({})
        container.override("svc", svc)

        container.shutdown_all()

        assert len(container._instances) == 0

    def test_shutdown_reverse_order(self):
        """服务按实例化逆序关闭。"""
        shutdown_order: list[str] = []

        class OrderedService:
            def __init__(self, name):
                self.name = name

            def shutdown(self):
                shutdown_order.append(self.name)

        svc_a = OrderedService("a")
        svc_b = OrderedService("b")
        svc_c = OrderedService("c")

        container = AppContainer({})
        container.override("a", svc_a)
        container.override("b", svc_b)
        container.override("c", svc_c)

        container.shutdown_all()

        # 逆序: c, b, a
        assert shutdown_order == ["c", "b", "a"]

    def test_shutdown_empty_container(self):
        """空容器 shutdown_all 不抛异常。"""
        container = AppContainer({})
        container.shutdown_all()
