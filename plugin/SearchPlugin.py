import webbrowser
import urllib.parse
import logging
from .abstract_plugin import AbstractPlugin

class SearchPlugin(AbstractPlugin):
    def get_name(self) -> str:
        return "SearchPlugin"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.logger.info("SearchPlugin initialized.")

    def get_commands(self) -> list[str]:
        # The PluginManager will match based on the plugin name,
        # the specific engine should be an argument.
        return ["search", "搜索"]

    def run(self, command: str, args: dict) -> str:
        engine = args.get("engine", "bing").lower()
        query = args.get("query")

        if not query:
            return "Error: Please provide a search query."

        query_encoded = urllib.parse.quote(query)
        url = None

        if engine == "baidu":
            url = f"https://www.baidu.com/s?wd={query_encoded}"
        elif engine == "bing":
            url = f"https://www.bing.com/search?q={query_encoded}"
        elif engine == "google":
            url = f"https://www.google.com/search?q={query_encoded}"
        elif engine == "bilibili":
            url = f"https://search.bilibili.com/all?keyword={query_encoded}"
        elif engine == "douyin":
            url = f"https://www.douyin.com/search/{query_encoded}"
        else:
            return f"Error: Unknown search engine '{engine}'. Supported engines: baidu, bing, google, bilibili, douyin."

        try:
            self.logger.info(f"Opening {url} in web browser.")
            webbrowser.open(url)
            return f"I have opened a search for '{query}' on {engine} in your browser."
        except Exception as e:
            self.logger.error(f"Failed to open web browser: {e}")
            return f"Error: Could not open the web browser. {e}"

    def stop(self):
        pass

    def cleanup(self):
        pass

    def status(self) -> str:
        return "active"
