from package.core_utils.log_manager import LogManager
from plugin.plugin_interface import AbstractPlugin, PluginResult
import chardet

logging = LogManager.get_logger(__name__)


class ReadFilePlugin(AbstractPlugin):
    def valid(self) -> bool:
        return True

    def init(self, logging=None):
        self._logger = logging if logging else LogManager.get_logger(__name__)

    def get_name(self):
        return "read_file"

    def get_chinese_name(self):
        return "读取文件"

    def get_description(self):
        return "读取文件内容，并返回文件内容。 需要传入文件路径参数。"

    def get_parameters(self):
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要读取的文件的绝对路径",
                }
            },
            "required": ["file_path"],
        }

    def on_startup(self):
        self._logger.info("ReadFilePlugin 启动成功")

    def on_shutdown(self):
        self._logger.info("ReadFilePlugin 已关闭")

    def on_pause(self):
        self._logger.info("ReadFilePlugin 已暂停")

    def on_resume(self):
        self._logger.info("ReadFilePlugin 已恢复")

    def run(self, takecommand: str, args: dict) -> PluginResult:
        file_path = args.get("file_path")
        if not isinstance(file_path, str) or not file_path.strip():
            self._logger.warning("缺少文件路径参数")
            return PluginResult.new(
                result=None,
                need_call_brain=False,
                success=False,
                error_message="缺少文件路径参数",
            )

        try:
            self._logger.info(f"尝试读取文件: {file_path}")
            with open(file_path, "rb") as f:
                content = f.read()
                encoding = chardet.detect(content)["encoding"]
                content = content.decode(encoding)
            self._logger.info(f"成功读取文件: {file_path}")
            # 返回读取的文件内容
            return PluginResult.new(
                result=content,
                need_call_brain=True,
                success=True,
                metadata={"file_path": file_path},
            )
        except FileNotFoundError:
            self._logger.error(f"文件不存在: {file_path}")
            return PluginResult.new(
                result=None,
                need_call_brain=False,
                success=False,
                error_message=f"文件不存在: {file_path}",
            )
        except UnicodeDecodeError:
            self._logger.error(f"无法解码文件: {file_path}")
            return PluginResult.new(
                result=None,
                need_call_brain=False,
                success=False,
                error_message=f"无法解码文件: {file_path}",
            )
        except PermissionError:
            self._logger.error(f"权限不足，无法读取文件: {file_path}")
            return PluginResult.new(
                result=None,
                need_call_brain=False,
                success=False,
                error_message=f"权限不足，无法读取文件: {file_path}",
            )
        except Exception as e:
            self._logger.error(f"读取文件时出错: {str(e)}")
            return PluginResult.new(
                result=None,
                need_call_brain=False,
                success=False,
                error_message=f"读取文件时出错: {str(e)}",
            )
