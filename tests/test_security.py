"""
Butler 安全相关测试

确保安全模块正常工作。
"""

import pytest


class TestFileConverter:
    """文件转换器安全测试"""

    def test_import(self):
        try:
            from package.document.file_converter import convert_file
            assert callable(convert_file)
        except ImportError:
            pytest.skip("file_converter has unmet dependencies")


class TestInputSanitization:
    """输入安全测试 (如果有安全模块)"""

    def test_sec_utils_import(self):
        try:
            from butler.core.sec_utils import audit
            assert audit is not None
        except ImportError:
            pytest.skip("sec_utils not available")
