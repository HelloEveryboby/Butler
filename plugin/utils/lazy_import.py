import importlib.util
import sys


def lazy_import(name, optional=True):
    """惰性地导入由名称指定的模块。可用于可选软件包，以加快启动时间"""
    # 检查模块是否已经导入
    if name in sys.modules:
        return sys.modules[name]

    # 从模块名称中查找模块规范
    spec = importlib.util.find_spec(name)
    if spec is None:
        if optional:
            return None  # 如果模块是可选的，不要引发错误
        else:
            raise ImportError(f"Module '{name}' cannot be found")

    # 使用LazyLoader延迟模块的加载
    loader = importlib.util.LazyLoader(spec.loader)
    spec.loader = loader

    # 从规范中创建一个模块，并将其设置为延迟加载
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)

    return module
