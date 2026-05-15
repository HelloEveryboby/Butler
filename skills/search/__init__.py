import webbrowser
import urllib.parse

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    query = entities.get("query") or kwargs.get("query")
    jarvis = kwargs.get("jarvis_app")

    if not query:
        return "请提供查询关键词。"

    if "百度" in action:
        url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}"
    elif "Bing" in action or "必应" in action:
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
    elif "bilibili" in action or "B站" in action:
        url = f"https://search.bilibili.com/all?keyword={urllib.parse.quote(query)}"
    else:
        url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}"

    webbrowser.open(url)
    msg = f"正在为您搜索：{query}"
    if jarvis:
        jarvis.speak(msg)
    return msg
