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
    Unifies the management of plugins, packages, and external programs.
    """
    def __init__(self, plugin_dir="plugin", package_dir="package", programs_dir="programs"):
        self.plugin_manager = PluginManager(plugin_dir, data_storage_manager)
        self.code_execution_manager = CodeExecutionManager(programs_dir)
        self.package_dir = package_dir
        self.packages: Dict[str, Any] = {}

        self.scan_all()

    def scan_all(self):
        """Scans all extension types."""
        # PluginManager calls load_all_plugins in its __init__
        self.code_execution_manager.scan_and_register()
        self._scan_packages()

    def _scan_packages(self):
        """Scans the package directory for simple Python scripts with a run() function."""
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
        Returns a unified list of tool descriptions for the LLM.
        """
        tools = []

        # Plugins
        for name, plugin in self.plugin_manager.plugins.items():
            tools.append({
                "name": name,
                "type": "plugin",
                "description": f"Plugin: {name}. Handles commands like: {', '.join(plugin.get_commands())}",
                "instance": plugin
            })

        # External Programs
        for name, info in self.code_execution_manager.get_all_programs().items():
            tools.append({
                "name": name,
                "type": "program",
                "description": info.get('description', 'External program.'),
                "path": info['path']
            })

        # Packages
        for name, module in self.packages.items():
            doc = getattr(module, "__doc__", "Python package.")
            tools.append({
                "name": name,
                "type": "package",
                "description": doc if doc else "Python package.",
                "module": module
            })

        return tools

    def execute(self, name: str, *args, **kwargs) -> Any:
        """
        Executes an extension by name.
        """
        # Try plugins
        plugin = self.plugin_manager.get_plugin(name)
        if plugin:
            # Assuming plugin.run expects (command, args_dict)
            # This might need adjustment to unify the interface
            command = kwargs.get("command", name)
            return plugin.run(command, kwargs.get("args", {}))

        # Try packages
        if name in self.packages:
            module = self.packages[name]
            return module.run(*args, **kwargs)

        # Try external programs
        program = self.code_execution_manager.get_program(name)
        if program:
            success, output = self.code_execution_manager.execute_program(name, args)
            return output

        raise ValueError(f"Extension '{name}' not found.")

extension_manager = ExtensionManager()
