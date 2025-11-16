import importlib
import pkgutil
import inspect
from typing import Type, Optional, List, Dict
from .abstract_plugin import AbstractPlugin, PluginResult
from package.log_manager import LogManager

logger = LogManager.get_logger(__name__)

class PluginManager:
    def __init__(self, plugin_package: str):
        self.plugin_package = plugin_package
        self.plugins: Dict[str, AbstractPlugin] = {}
        
        # 配置日志
        self.logger = logger
        
        # self.load_all_plugins()
        
    def load_all_plugins(self):
        """加载所有可用插件"""
        self.logger.info(f"开始加载插件包: {self.plugin_package}")
        for importer, module_name, ispkg in pkgutil.walk_packages([self.plugin_package]):
            if not ispkg:
                full_module_name = f"{self.plugin_package}.{module_name}"
                self.logger.info(f"扫描模块: {full_module_name}")
                self._load_plugins_from_module(full_module_name)
        self.logger.info(f"插件加载完成，共 {len(self.plugins)} 个插件")
    
    def _load_plugins_from_module(self, module_name: str):
        """从模块中加载所有插件类"""
        try:
            module = importlib.import_module(module_name)
            for attribute_name in dir(module):
                attribute = getattr(module, attribute_name)
                if (inspect.isclass(attribute) and 
                    issubclass(attribute, AbstractPlugin) and 
                    not inspect.isabstract(attribute)):
                    if attribute.__name__.endswith("Plugin"):
                        self.load_plugin(module_name, attribute.__name__)
        except Exception as e:
            self.logger.error(f"加载模块 {module_name} 失败: {e}")

    def load_plugin(self, module_name: str, class_name: str) -> Optional[AbstractPlugin]:
        """
        Loads a single plugin from a given module and class name.

        Args:
            module_name: The name of the module where the plugin is located.
            class_name: The name of the plugin class.

        Returns:
            An instance of the plugin if it was loaded successfully, otherwise None.
        """
        try:
            module = importlib.import_module(module_name)
            plugin_class: Type[AbstractPlugin] = getattr(module, class_name)
            plugin_instance = plugin_class()
            
            if plugin_instance.valid():
                plugin_instance.init(self.logger)
                plugin_name = plugin_instance.get_name()
                
                # 处理重复加载
                if plugin_name in self.plugins:
                    self.logger.warning(f"插件 {plugin_name} 已存在，重新加载")
                    self.unload_plugin(plugin_name)
                
                self.plugins[plugin_name] = plugin_instance
                self.logger.info(f"成功加载插件: {plugin_name}")
                return plugin_instance
            else:
                self.logger.warning(f"插件 {class_name} 无效，跳过加载")
                return None
        except (ModuleNotFoundError, AttributeError) as e:
            self.logger.error(f"加载插件 {module_name}.{class_name} 失败: {e}")
            return None

    def unload_plugin(self, name: str) -> bool:
        """
        Unloads a plugin and releases its resources.

        Args:
            name: The name of the plugin to unload.

        Returns:
            True if the plugin was unloaded successfully, otherwise False.
        """
        if name in self.plugins:
            plugin = self.plugins.pop(name)
            try:
                plugin.cleanup()
                self.logger.info(f"已卸载插件: {name}")
                return True
            except Exception as e:
                self.logger.error(f"卸载插件 {name} 时出错: {e}")
        return False

    def get_plugin(self, name: str) -> Optional[AbstractPlugin]:
        """获取已加载的插件"""
        if name not in self.plugins:
            self.logger.info(f"Plugin '{name}' not found in cache. Attempting to load.")
            # This is a simplified dynamic load. A real implementation would need
            # to know the module and class name. We'll assume a convention for now.
            # e.g., plugin name 'BingSearch' corresponds to 'BingSearchPlugin.py' and class 'BingSearchPlugin'
            module_name = f"{self.plugin_package}.{name}Plugin"
            class_name = f"{name}Plugin"
            self.load_plugin(module_name, class_name)

        return self.plugins.get(name)

    def get_all_plugins(self) -> List[AbstractPlugin]:
        """获取所有已加载插件"""
        return list(self.plugins.values())

    def run_plugin(self, name: str, command: str, args: dict) -> PluginResult:
        """
        Runs a plugin with the given command and arguments.

        Args:
            name: The name of the plugin to run.
            command: The command to execute.
            args: The arguments for the command.

        Returns:
            A PluginResult object with the result of the execution.
        """
        plugin = self.get_plugin(name) # Will attempt to lazy-load
        if not plugin:
             # If lazy load by convention failed, scan all modules to find the right plugin
            self.logger.info(f"Scanning all modules to find a plugin matching '{name}'...")
            for importer, module_name, ispkg in pkgutil.walk_packages([self.plugin_package]):
                if not ispkg:
                    full_module_name = f"{self.plugin_package}.{module_name}"
                    try:
                        module = importlib.import_module(full_module_name)
                        for attribute_name in dir(module):
                            attribute = getattr(module, attribute_name)
                            if (inspect.isclass(attribute) and
                                issubclass(attribute, AbstractPlugin) and
                                not inspect.isabstract(attribute)):
                                # Temporarily instantiate to check its name
                                temp_instance = attribute()
                                if temp_instance.get_name() == name:
                                    self.logger.info(f"Found matching plugin for '{name}' in {full_module_name}. Loading.")
                                    # Now properly load it, which will cache it
                                    plugin = self.load_plugin(full_module_name, attribute.__name__)
                                    break
                    except Exception as e:
                        self.logger.error(f"Error while scanning module {full_module_name}: {e}")
                if plugin:
                    break

        if plugin:
            self.logger.info(f"执行插件: {name}，命令: {command}")
            try:
                result = plugin.run(command, args)
                return PluginResult(success=True, result=result)
            except Exception as e:
                error_msg = f"插件 {name} 执行出错: {str(e)}"
                self.logger.error(error_msg)
                return PluginResult(success=False, result=None, error_message=error_msg)
        return PluginResult(
            success=False, 
            result=None, 
            error_message=f"插件 {name} 未找到或未加载"
        )
    
    def stop_plugin(self, name: str) -> PluginResult:
        """停止插件运行"""
        plugin = self.get_plugin(name)
        if plugin:
            self.logger.info(f"停止插件: {name}")
            try:
                result = plugin.stop()
                return PluginResult(success=True, result=result)
            except Exception as e:
                error_msg = f"停止插件 {name} 出错: {str(e)}"
                self.logger.error(error_msg)
                return PluginResult(success=False, result=None, error_message=error_msg)
        return PluginResult(
            success=False, 
            result=None, 
            error_message=f"插件 {name} 未找到或未加载"
        )
    
    def get_plugin_status(self, name: str) -> PluginResult:
        """获取插件状态"""
        plugin = self.get_plugin(name)
        if plugin:
            self.logger.info(f"查询插件状态: {name}")
            try:
                status = plugin.status()
                return PluginResult(success=True, result=status)
            except Exception as e:
                error_msg = f"获取插件 {name} 状态出错: {str(e)}"
                self.logger.error(error_msg)
                return PluginResult(success=False, result=None, error_message=error_msg)
        return PluginResult(
            success=False, 
            result=None, 
            error_message=f"插件 {name} 未找到或未加载"
        )
