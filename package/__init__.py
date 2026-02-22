import sys

# 辅助函数，用于将子模块映射到旧路径以保持兼容性
def _map_module(old_name, new_module):
    sys.modules[old_name] = new_module
    return new_module

try:
    from .core_utils import log_manager
    _map_module('package.log_manager', log_manager)
    from .core_utils.log_manager import LogManager
    getLogger = LogManager.get_logger
except ImportError:
    LogManager = None
    getLogger = None

try:
    from .core_utils import embedding_utils
    _map_module('package.embedding_utils', embedding_utils)
except ImportError:
    pass

try:
    from .security import crypto_core
    _map_module('package.crypto_core', crypto_core)
except ImportError:
    pass

try:
    from .core_utils import dependency_manager
    _map_module('package.dependency_manager', dependency_manager)
except ImportError:
    pass

try:
    from .core_utils import autonomous_switch
    _map_module('package.autonomous_switch', autonomous_switch)
except ImportError:
    pass

try:
    from .core_utils import knowledge_base_manager
    _map_module('package.knowledge_base_manager', knowledge_base_manager)
except ImportError:
    pass

try:
    from .file_system import data_recycler
    _map_module('package.data_recycler', data_recycler)
except ImportError:
    pass

try:
    from .network import cloud_storage_manager
    _map_module('package.cloud_storage_manager', cloud_storage_manager)
except ImportError:
    pass

try:
    from .document import marker_tool
    _map_module('package.marker_tool', marker_tool)
except ImportError:
    pass
