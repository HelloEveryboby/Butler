import os

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    pattern = entities.get("pattern") or kwargs.get("pattern")

    if not pattern:
        return "请输入关键词。"

    # 这里仅演示逻辑，实际应结合索引器
    results = []
    for root, dirs, files in os.walk("."):
        for f in files:
            if pattern.lower() in f.lower():
                results.append(os.path.join(root, f))
                if len(results) >= 10: break
        if len(results) >= 10: break

    if results:
        return "搜索结果：\n" + "\n".join(results)
    return "未找到。"
