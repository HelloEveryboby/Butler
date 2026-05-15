import requests
from package.core_utils.config_loader import config_loader

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    query = entities.get("query") or kwargs.get("query")
    num = entities.get("num") or kwargs.get("num", 5)

    if not query:
        return "请提供要搜索的关键字。"

    base_url = config_loader.get("api.bing.endpoint", "https://api.bing.microsoft.com/v7.0/search")
    headers = {
        "Ocp-Apim-Subscription-Key": config_loader.get("api.bing.search_key")
    }
    params = {
        "q": query,
        "count": num,
        "offset": 0,
        "mkt": "zh-CN",
    }

    try:
        response = requests.get(base_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        result = "以下是从必应中搜索到的网页及其摘要：\n"
        for item in data.get('webPages', {}).get('value', []):
            result += "【网页标题】：{}\n".format(item.get('name', '无标题'))
            result += "【摘要】：{}\n".format(item.get('snippet', '无摘要'))
            result += "【网页链接】：{}\n\n".format(item.get('url', '无链接'))

        return result

    except Exception as e:
        return f"搜索失败: {str(e)}"
