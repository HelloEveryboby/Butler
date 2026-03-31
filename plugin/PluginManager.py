import importlib
import importlib.util
import pkgutil
import inspect
import ast
from typing import Type, Optional, List, Dict
from .plugin_interface import AbstractPlugin, PluginResult
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger(__name__)

from butler.data_storage import DataStorageManager


class PluginManager:
    def __init__(self, plugin_package: str, data_storage_manager: DataStorageManager):
        self.plugin_package = plugin_package
        self.plugins: Dict[str, AbstractPlugin] = {}
        self.data_storage_manager = data_storage_manager

        # Configure logging
        self.logger = logger

        self.load_all_plugins()

    def load_all_plugins(self):
        """Loads all available plugins"""
        self.logger.info(f"Starting to load plugins package: {self.plugin_package}")
        # walk_packages needs a filesystem path, not a module name
        import os

        package_path = self.plugin_package.replace(".", os.path.sep)
        for importer, module_name, ispkg in pkgutil.walk_packages([package_path]):
            if not ispkg:
                full_module_name = f"{self.plugin_package}.{module_name}"
                self.logger.info(f"Scanning module: {full_module_name}")
                self._load_plugins_from_module(full_module_name)
        self.logger.info(f"Plugin loading complete, total {len(self.plugins)} plugins")

    def _is_plugin_safe(self, module_name: str) -> bool:
        """Performs basic AST analysis to check for dangerous calls."""
        try:
            # Resolve module path
            spec = importlib.util.find_spec(module_name)
            if not spec or not spec.origin:
                return False

            with open(spec.origin, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            forbidden_calls = {
                "os.system",
                "os.popen",
                "subprocess.Popen",
                "subprocess.call",
                "subprocess.run",
                "shutil.rmtree",
                "eval",
                "exec",
            }

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    call_name = ""
                    if isinstance(node.func, ast.Attribute):
                        if hasattr(node.func.value, "id"):
                            call_name = f"{node.func.value.id}.{node.func.attr}"
                    elif isinstance(node.func, ast.Name):
                        call_name = node.func.id

                    if call_name in forbidden_calls:
                        self.logger.warning(
                            f"Plugin {module_name} contains forbidden call: {call_name}"
                        )
                        return False
            return True
        except Exception as e:
            self.logger.error(f"Error analyzing plugin {module_name} safety: {e}")
            return False

    def _load_plugins_from_module(self, module_name: str):
        """Loads all plugin classes from a module"""
        try:
            # Perform safety check before importing
            if not self._is_plugin_safe(module_name):
                self.logger.error(
                    f"Plugin {module_name} failed safety check, skipping."
                )
                return

            module = importlib.import_module(module_name)
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)
                if (
                    inspect.isclass(attribute)
                    and issubclass(attribute, AbstractPlugin)
                    and not inspect.isabstract(attribute)
                ):
                    if attribute.__name__.endswith("Plugin"):
                        self.load_plugin(module_name, attribute.__name__)
        except Exception as e:
            self.logger.error(f"Failed to load module {module_name}: {e}")

    def load_plugin(
        self, module_name: str, class_name: str
    ) -> Optional[AbstractPlugin]:
        """Loads a single plugin from the given module and class name."""
        try:
            module = importlib.import_module(module_name)
            plugin_class: Type[AbstractPlugin] = getattr(module, class_name)
            plugin_instance = plugin_class()

            if plugin_instance.valid():
                plugin_instance.init(self.logger)
                plugin_instance.set_data_storage(self.data_storage_manager)
                plugin_name = plugin_instance.get_name()

                # Handle duplicate loading
                if plugin_name in self.plugins:
                    self.logger.warning(
                        f"Plugin {plugin_name} already exists, reloading"
                    )
                    self.unload_plugin(plugin_name)

                self.plugins[plugin_name] = plugin_instance
                plugin_instance.on_startup()
                self.logger.info(f"Successfully loaded plugin: {plugin_name}")
                return plugin_instance
            else:
                self.logger.warning(f"Plugin {class_name} is invalid, skipping load")
                return None
        except (ModuleNotFoundError, AttributeError) as e:
            self.logger.error(f"Failed to load plugin {module_name}.{class_name}: {e}")
            return None

    def unload_plugin(self, name: str) -> bool:
        """Unloads a plugin and releases its resources."""
        if name in self.plugins:
            plugin = self.plugins.pop(name)
            try:
                plugin.on_shutdown()
                plugin.cleanup()
                self.logger.info(f"Unloaded plugin: {name}")
                return True
            except Exception as e:
                self.logger.error(f"Error while unloading plugin {name}: {e}")
        return False

    def get_plugin(self, name: str) -> Optional[AbstractPlugin]:
        """Get a loaded plugin"""
        return self.plugins.get(name)

    def get_all_plugins(self) -> List[AbstractPlugin]:
        """Get all loaded plugins"""
        return list(self.plugins.values())

    def run_plugin(self, name: str, command: str, args: dict) -> PluginResult:
        """Runs a plugin with the given command and arguments."""
        plugin = self.get_plugin(name)
        if plugin:
            self.logger.info(f"Running plugin: {name}, command: {command}")
            try:
                result = plugin.run(command, args)
                if not isinstance(result, PluginResult):
                    # Handle legacy plugins that might return something else
                    return PluginResult.new(result=result)
                return result
            except Exception as e:
                error_msg = f"Error executing plugin {name}: {str(e)}"
                self.logger.error(error_msg)
                return PluginResult.new(
                    result=None, success=False, error_message=error_msg
                )
        return PluginResult.new(
            result=None,
            success=False,
            error_message=f"Plugin {name} not found or not loaded",
        )

    def stop_plugin(self, name: str) -> PluginResult:
        """Stops plugin execution"""
        plugin = self.get_plugin(name)
        if plugin:
            self.logger.info(f"Stopping plugin: {name}")
            try:
                result = plugin.stop()
                return PluginResult.new(result=result)
            except Exception as e:
                error_msg = f"Error stopping plugin {name}: {str(e)}"
                self.logger.error(error_msg)
                return PluginResult.new(
                    result=None, success=False, error_message=error_msg
                )
        return PluginResult.new(
            result=None,
            success=False,
            error_message=f"Plugin {name} not found or not loaded",
        )

    def get_plugin_status(self, name: str) -> PluginResult:
        """Gets plugin status"""
        plugin = self.get_plugin(name)
        if plugin:
            self.logger.info(f"Querying status for plugin: {name}")
            try:
                status = plugin.status()
                return PluginResult.new(result=status)
            except Exception as e:
                error_msg = f"Error getting status for plugin {name}: {str(e)}"
                self.logger.error(error_msg)
                return PluginResult.new(
                    result=None, success=False, error_message=error_msg
                )
        return PluginResult.new(
            result=None,
            success=False,
            error_message=f"Plugin {name} not found or not loaded",
        )
