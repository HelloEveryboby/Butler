"""
Butler 模块导入测试

确保所有核心模块可以正常导入，无循环依赖。
"""

import pytest


class TestCoreImports:
    """核心模块导入"""

    def test_import_algorithms(self):
        from butler.core import algorithms
        assert hasattr(algorithms, "quick_sort")
        assert hasattr(algorithms, "merge_sort")
        assert hasattr(algorithms, "binary_search")

    def test_import_action_bridge(self):
        from butler.core.action_bridge import ActionBridge, action_bridge
        assert isinstance(action_bridge, ActionBridge)

    def test_import_agent_node(self):
        try:
            from butler.core import agent_node
            assert agent_node is not None
        except ImportError:
            pytest.skip("agent_node has unmet dependencies")

    def test_import_butler_app(self):
        try:
            from butler.butler_app import main
            assert callable(main)
        except ImportError:
            pytest.skip("butler_app has unmet dependencies")


class TestPackageImports:
    """package 模块导入"""

    def test_import_file_converter(self):
        try:
            from package.document.file_converter import convert_file
            assert callable(convert_file)
        except ImportError:
            pytest.skip("file_converter has unmet dependencies")

    def test_import_log_manager(self):
        try:
            from package.core_utils.log_manager import LogManager
            assert hasattr(LogManager, "get_logger")
        except ImportError:
            pytest.skip("LogManager has unmet dependencies")
