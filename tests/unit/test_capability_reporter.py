"""CapabilityReporter 能力诊断单元测试。"""

from butler.core.capability_reporter import CapabilityReporter, CapabilityStatus


class TestCapabilityReporter:
    """CapabilityReporter 测试。"""

    def test_report_returns_dict(self):
        """report 返回包含所有 capability 的字典。"""
        reporter = CapabilityReporter()
        report = reporter.report()
        assert isinstance(report, dict)
        assert "ai" in report
        assert "memory_vec" in report
        assert "crypto" in report

    def test_status_values_valid(self):
        """所有状态值为 full/partial/absent 之一。"""
        reporter = CapabilityReporter()
        report = reporter.report()
        for cap in report.values():
            assert cap.status in ("full", "partial", "absent")

    def test_format_banner_contains_all_caps(self):
        """format_banner 包含所有 capability 名。"""
        reporter = CapabilityReporter()
        banner = reporter.format_banner()
        assert "Capability 诊断:" in banner
        assert "ai" in banner
        assert "memory_vec" in banner

    def test_get_memory_backend_returns_string(self):
        """get_memory_backend 返回有效后端名。"""
        reporter = CapabilityReporter()
        backend = reporter.get_memory_backend()
        assert backend in ("redis", "zvec", "sqlite")

    def test_capability_status_icon(self):
        """CapabilityStatus.icon 返回对应图标。"""
        assert CapabilityStatus(name="test", status="full").icon == "[OK]"
        assert CapabilityStatus(name="test", status="partial").icon == "[--]"
        assert CapabilityStatus(name="test", status="absent").icon == "[!!]"
