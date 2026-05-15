def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    name = entities.get("name") or kwargs.get("name")
    jarvis = kwargs.get("jarvis_app")

    # 模拟数据存储（在实际系统中应使用 jarvis.long_memory 或 data_storage）
    # 这里简单演示逻辑
    if "remember" in action or "记得" in action or "叫" in action:
        if name:
            return f"好的，我已经记住了，你叫 {name}。"
        return "请告诉我你的名字。"

    if "who" in action or "谁" in action or "名字" in action:
        return "抱歉，我现在还没记住你的名字。你可以告诉我：‘记得我叫 XXX’。"

    return "用户画像功能就绪。"
