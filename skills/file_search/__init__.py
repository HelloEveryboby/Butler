import os
import time

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    directory = entities.get("directory") or kwargs.get("directory")
    filename = entities.get("filename") or kwargs.get("filename")

    if not directory or not filename:
        return "请提供目录和文件名。"

    if not os.path.exists(directory):
        return f"目录不存在: {directory}"

    matches = []
    start_time = time.time()

    try:
        for root, dirs, files in os.walk(directory):
            if filename in files:
                matches.append(os.path.join(root, filename))

            if time.time() - start_time > 10: # 10s 超时
                break

        if matches:
            return f"找到文件：\n" + "\n".join(matches)
        else:
            return "未找到文件。"
    except Exception as e:
        return f"搜索出错: {str(e)}"
