import os
import requests

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    path = entities.get("path") or kwargs.get("path")
    content = entities.get("content") or kwargs.get("content")
    url = entities.get("url") or kwargs.get("url")

    if action == "read_file" or "读取" in action:
        if not os.path.exists(path): return "文件不存在。"
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    elif action == "write_file" or "写入" in action:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return "写入成功。"

    elif action == "download_url" or "下载" in action:
        res = requests.get(url)
        fname = os.path.basename(url)
        with open(fname, 'wb') as f:
            f.write(res.content)
        return f"已下载到: {fname}"

    return "文件管理就绪。"
