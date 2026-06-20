import sys
from .core_utils.log_manager import LogManager

# 提供模块级别的快捷访问
getLogger = LogManager.get_logger

# 动态映射以保持向后兼容性
# 这允许 'from package.core_utils.log_manager import LogManager' 继续工作
mapping = {
    "package.log_manager": "package.core_utils.log_manager",
    "package.embedding_utils": "package.core_utils.embedding_utils",
    "package.crypto_core": "package.security.crypto_core",
    "package.dependency_manager": "package.core_utils.dependency_manager",
    "package.hybrid_orchestrator": "package.core_utils.hybrid_orchestrator",
    "package.autonomous_switch": "package.core_utils.autonomous_switch",
    "package.marker_tool": "package.document.marker_tool",
}

for old_mod, new_mod in mapping.items():
    if old_mod not in sys.modules:
        try:
            # 确保新模块已加载
            __import__(new_mod)
            sys.modules[old_mod] = sys.modules[new_mod]
        except ImportError:
            pass
