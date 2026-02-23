import os
import time
from package.core_utils.log_manager import LogManager
from plugin.plugin_interface import AbstractPlugin, PluginResult

logging = LogManager.get_logger(__name__)

class FileSearchPlugin(AbstractPlugin):
    def __init__(self):
        self.name = "FileSearchPlugin"
        self.chinese_name = "文件搜索"
        self.description = "搜索指定目录中的文件"
        self.parameters = {
            "directory": "str", 
            "filename": "str",
            "foldername": "str",
            "目标文件夹": "str"
        }

    def valid(self) -> bool:
        return True

    def init(self, logging):
        self.logger = LogManager.get_logger(self.name)

    def get_name(self):
        return self.name

    def get_chinese_name(self):
        return self.chinese_name

    def get_description(self):
        return self.description

    def get_parameters(self):
        return self.parameters

    def on_startup(self):
        self.logger.info("文件搜索插件开始.")

    def on_shutdown(self):
        self.logger.info("文件搜索插件关闭.")

    def on_pause(self):
        self.logger.info("文件搜索插件停顿了一下.")

    def on_resume(self):
        self.logger.info("文件搜索插件恢复.")

    def get_commands(self) -> list[str]:
        return ["搜索", "搜索一下"]

    def run(self, takecommand: str, args: dict) -> PluginResult:
        directory = args.get("directory")
        filename = args.get("filename")
        
        if not directory or not filename:
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="directory和filename参数缺失")

        try:
            matches = []
            start_time = time.time()
            
            for root, dirs, files in os.walk(directory):
                if filename in files:
                    matches.append(os.path.join(root, filename))
                
                if time.time() - start_time > 10:  # 10 seconds timeout
                    break

            if matches:
                result = f"在 '{directory}' 找到文件：{', '.join(matches)}"
                return PluginResult.new(result=result, need_call_brain=False, success=True)
            else:
                return PluginResult.new(result="未找到文件", need_call_brain=False, success=False)

        except Exception as e: 
            self.logger.error(f"文件搜索失败: {str(e)}")
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message=f"文件搜索失败: {str(e)}")
