from package.core_utils.log_manager import LogManager
import time

from plugin.plugin_interface import AbstractPlugin, PluginResult
from plugin.memory_engine import LongMemoryItem

logger = LogManager.get_logger(__name__)

class AddLongMemoryPlugin(AbstractPlugin):
    def valid(self) -> bool:
        # 功能不成熟，先不开放
        return False

    def init(self, logger):
        self._logger = logger

    def get_name(self):
        return "add_long_memory"

    def get_chinese_name(self):
        return "增加长期记忆"

    def get_description(self):
        return "增加长期记忆的接口。长期记忆内容是用户需要你长期记住的内容。\n" \
               "当用户告诉你某个信息很重要，或者让你记住某个信息时，你应该调用本接口。"

    def get_parameters(self):
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "你需要记住的信息内容。你应该把用户告诉你的内容格式化一遍，再传入本字段中。以下是几个示例：\n"
                                   "【用户说的内容】：我叫小郑。\n"
                                   "【传入的参数值】：用户的名字是小郑。\n"
                                   "【用户说的内容】：这是我的朋友，叫小李。\n"
                                   "【传入的参数值】：用户有个朋友，叫小李。\n"
                                   "【用户说的内容】：我喜欢蓝色。\n"
                                   "【传入的参数值】：用户喜欢的颜色是蓝色。\n",
                }
            },
            "required": ["content"],
        }
        
    def on_startup(self):
        self._logger.info("AddLongMemoryPlugin 启动成功")
    
    def on_shutdown(self):
        self._logger.info("AddLongMemoryPlugin 已关闭")

    def on_pause(self):
        self._logger.info("AddLongMemoryPlugin 已暂停")

    def on_resume(self):
        self._logger.info("AddLongMemoryPlugin 已恢复")
        
def run(self, takecommand: str, args: dict) -> PluginResult:
    self._logger.info("开始处理记忆内容")
    if takecommand is None:
        self._logger.warning("没有检测到语音指令")
        return PluginResult.new("没有检测到语音指令", need_call_brain=False)

    content = args.get('content') 
    if content:
        try:
            item = LongMemoryItem.new(
                content=content, 
                metadata={"add_time": time.time()}, 
                id=str(time.time_ns())
            )
            jarvis.long_memory.save([item])
            self._logger.info(f"成功记忆内容: {content}")
            return PluginResult.new(result=f"已成功记忆：{content}", need_call_brain=True)
        except Exception as e:
            self._logger.error(f"记忆内容时出错: {str(e)}")
            return PluginResult.new(result=f"记忆失败: {str(e)}", need_call_brain=False)
    else:
        self._logger.warning("记忆内容不能为空")
        return PluginResult.new(result="记忆内容不能为空", need_call_brain=False) 
