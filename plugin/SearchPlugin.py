import urllib.parse
from package.core_utils.log_manager import LogManager
from plugin.plugin_interface import AbstractPlugin, PluginResult

class SearchPlugin(AbstractPlugin):
    def __init__(self):
        self.name = "SearchPlugin"
        self.chinese_name = "搜索插件"
        self.description = "使用搜索引擎和视频网站搜索相关信息"
        self.parameters = {}  # 此插件不需要参数
        self.logger = LogManager.get_logger(self.name)

    def valid(self) -> bool:
        return True

    def init(self, logging):
        self.logger = LogManager.get_logger(self.name)

    def get_name(self) -> str:
        return self.name

    def get_chinese_name(self) -> str:
        return self.chinese_name

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> dict:
        return self.parameters

    def on_startup(self):
        self.logger.info("SearchPlugin 开始.")

    def on_shutdown(self):
        self.logger.info("SearchPlugin 关闭.")

    def on_pause(self):
        self.logger.info("SearchPlugin 停顿了一下.")

    def on_resume(self):
        self.logger.info("SearchPlugin 恢复.")

    def get_commands(self) -> list[str]:
        return ["在百度搜索", "在Bing搜索", "bilibili搜索", "快手搜索", "抖音搜索"]

    def run(self, takecommand: str, args: dict) -> PluginResult:
        from butler.main import Jarvis
        query = args.get("query")
        if not query:
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="缺少查询参数")

        # 根据命令选择搜索引擎
        if "百度" in takecommand:
            url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}"
        elif "Bing" in takecommand:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        elif "bilibili" in takecommand:
            url = f"https://search.bilibili.com/all?keyword={urllib.parse.quote(query)}"
        elif "快手" in takecommand:
            url = f"https://www.kuaishou.com/search/video?searchKey={urllib.parse.quote(query)}"
        elif "抖音" in takecommand:
            url = f"https://www.douyin.com/search/{urllib.parse.quote(query)}"
        else:
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="无法识别的搜索引擎")

        try:
            # 在默认浏览器中打开URL
            import webbrowser
            webbrowser.open(url)
            Jarvis(None).speak(f"正在为您搜索 {query}")
            return PluginResult.new(result=f"在浏览器中打开 {url}", need_call_brain=False, success=True)
        except Exception as e:
            self.logger.error(f"打开浏览器失败: {e}")
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message=f"打开浏览器失败: {e}")
