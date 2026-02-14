import os
import sys
import importlib.util
import logging
from typing import Dict, List, Any, Optional
from plugin.PluginManager import PluginManager
from butler.code_execution_manager import CodeExecutionManager
from butler.data_storage import data_storage_manager
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class ExtensionManager:
    """
    统一管理插件、包和外部程序。
    """
    def __init__(self, plugin_dir="plugin", package_dir="package", programs_dir="programs"):
        self.plugin_manager = PluginManager(plugin_dir, data_storage_manager)
        self.code_execution_manager = CodeExecutionManager(programs_dir)
        self.package_dir = package_dir
        self.packages: Dict[str, Any] = {}

        self.scan_all()

    def scan_all(self):
        """扫描所有扩展类型。"""
        # PluginManager calls load_all_plugins in its __init__
        self.code_execution_manager.scan_and_register()
        self._scan_packages()

    def _scan_packages(self):
        """扫描包目录中带有 run() 函数的简单 Python 脚本。"""
        if not os.path.exists(self.package_dir):
            logger.warning(f"Package directory '{self.package_dir}' not found.")
            return

        for filename in os.listdir(self.package_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                package_name = filename[:-3]
                package_path = os.path.join(self.package_dir, filename)

                try:
                    spec = importlib.util.spec_from_file_location(package_name, package_path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[package_name] = module
                    spec.loader.exec_module(module)

                    if hasattr(module, "run"):
                        self.packages[package_name] = module
                        logger.info(f"Loaded package: {package_name}")
                except Exception as e:
                    logger.error(f"Failed to load package {package_name}: {e}")

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        为 LLM 返回统一的工具描述列表。
        """
        tools = []

        # 插件
        for name, plugin in self.plugin_manager.plugins.items():
            tools.append({
                "name": name,
                "type": "plugin",
                "description": f"插件: {name}。处理如下命令: {', '.join(plugin.get_commands())}",
                "instance": plugin
            })

        # 外部程序
        for name, info in self.code_execution_manager.get_all_programs().items():
            tools.append({
                "name": name,
                "type": "program",
                "description": info.get('description', '外部程序。'),
                "path": info['path']
            })

        # 包
        for name, module in self.packages.items():
            doc = getattr(module, "__doc__", "Python 包。")
            tools.append({
                "name": name,
                "type": "package",
                "description": doc if doc else "Python 包。",
                "module": module
            })

        return tools

    def execute(self, name: str, *args, **kwargs) -> Any:
        """
        根据名称执行扩展。
        """
        # 尝试插件
        plugin = self.plugin_manager.get_plugin(name)
        if plugin:
            # 假设 plugin.run 期望 (command, args_dict)
            # 这可能需要调整以统一接口
            command = kwargs.get("command", name)
            return plugin.run(command, kwargs.get("args", {}))

        # 尝试包
        if name in self.packages:
            module = self.packages[name]
            return module.run(*args, **kwargs)

        # 尝试外部程序
        program = self.code_execution_manager.get_program(name)
        if program:
            success, output = self.code_execution_manager.execute_program(name, args)
            return output

        raise ValueError(f"Extension '{name}' not found.")

extension_manager = ExtensionManager()
