import requests
from package.core_utils.log_manager import LogManager
from package.core_utils.config_loader import config_loader
from plugin.plugin_interface import AbstractPlugin, PluginResult

logging = LogManager.get_logger(__name__)

class BingSearchPlugin(AbstractPlugin):

    def valid(self) -> bool:
        return True

    def init(self, logging=None):
        self._logger = logging if logging else LogManager.get_logger(__name__)

    def get_name(self):
        return "bing_search"

    def get_chinese_name(self):
        return "必应搜索"

    def get_description(self):
        return "通过必应搜索获取网页标题、摘要及链接"

    def get_parameters(self):
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要搜索的关键字或问题",
                },
                "num": {
                    "type": "integer",
                    "description": "返回结果的数量，默认为5",
                    "minimum": 1,
                    "maximum": 10,
                }
            },
            "required": ["query"],
        }

    def on_startup(self):
        self._logger.info("BingSearchPlugin 启动成功")

    def on_shutdown(self):
        self._logger.info("BingSearchPlugin 已关闭")

    def on_pause(self):
        self._logger.info("BingSearchPlugin 已暂停")

    def on_resume(self):
        self._logger.info("BingSearchPlugin 已恢复")

    def run(self, takecommand: str, args: dict) -> PluginResult:
        # 默认值处理
        query = args.get("query", "").strip()
        num = args.get("num", 5)

        if not query:
            self._logger.warning("缺少搜索关键字参数")
            return PluginResult.new(result=None, need_call_brain=False, success=False,
                                    error_message="缺少搜索关键字参数")

        if not (1 <= num <= 10):
            self._logger.warning("参数 'num' 超出范围")
            return PluginResult.new(result=None, need_call_brain=False, success=False,
                                    error_message="参数 'num' 必须在 1 到 10 之间")

        # 必应搜索 API 的 URL 和请求头
        base_url = config_loader.get("api.bing.endpoint", "https://api.bing.microsoft.com/v7.0/search")
        headers = {
            "Ocp-Apim-Subscription-Key": config_loader.get("api.bing.search_key")
        }
        params = {
            "q": query,
            "count": num,
            "offset": 0,
            "mkt": "zh-CN",  # 设置市场为中国（根据需求修改）
        }

        try:
            self._logger.info(f"发起必应搜索: {query}")
            response = requests.get(base_url, headers=headers, params=params)
            response.raise_for_status()  # 检查请求是否成功
            data = response.json()

            # 解析结果
            result = "以下是从必应中搜索到的网页及其摘要：\n"
            for item in data.get('webPages', {}).get('value', []):
                result += "【网页标题】：{}\n".format(item.get('name', '无标题'))
                result += "【摘要】：{}\n".format(item.get('snippet', '无摘要'))
                result += "【网页链接】：{}\n\n".format(item.get('url', '无链接'))

            result += (
                "如果上述网页的摘要已经足够让你回答用户的问题或者继续与用户对话，那么你可以直接与用户继续对话。\n"
                "如果上述网页的摘要没有足够的信息，那么你应该按照用户的需要，选择其中一至二个与用户问题最相关且最专业的网页，"
                "使用【下载网页内容】接口获取这些网页的详细内容，再根据网页的详细内容与用户继续对话。"
            )

            return PluginResult.new(result=result, need_call_brain=True, success=True)

        except requests.exceptions.RequestException as e:
            self._logger.error(f"必应搜索请求失败: {str(e)}")
            return PluginResult.new(result=None, need_call_brain=False, success=False,
                                    error_message=f"必应搜索请求失败: {str(e)}")

        except Exception as e:
            self._logger.error(f"处理必应搜索结果时出错: {str(e)}")
            return PluginResult.new(result=None, need_call_brain=False, success=False,
                                    error_message=f"处理必应搜索结果时出错: {str(e)}")
