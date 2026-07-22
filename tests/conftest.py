"""
pytest 全局配置

conftest.py 提供共享 fixtures 和测试配置。
"""

import pytest
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


@pytest.fixture(autouse=True)
def _reset_logging():
    """每个测试后重置日志配置"""
    yield
    import logging
    logging.getLogger().handlers.clear()


@pytest.fixture
def tmp_dir(tmp_path):
    """提供临时目录"""
    return tmp_path
