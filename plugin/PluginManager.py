import importlib
import pkgutil
import inspect
import logging
from typing import Type, Optional, List, Dict
from .abstract_plugin import AbstractPlugin, PluginResult

logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self, plugin_package: str):
        self.plugin_package = plugin_package
        self.plugins: Dict[str, AbstractPlugin] = {}
        
        # 配置日志
        self.logger = logger
        self._configure_logger()
        
        self.load_all_plugins()
    
    def _configure_logger(self):
        """配置日志处理器"""
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
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
        """动态加载单个插件"""
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
        """卸载插件并释放资源"""
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
        return self.plugins.get(name)

    def get_all_plugins(self) -> List[AbstractPlugin]:
        """获取所有已加载插件"""
        return list(self.plugins.values())

    def run_plugin(self, name: str, command: str, args: dict) -> PluginResult:
        """执行插件功能"""
        plugin = self.get_plugin(name)
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
