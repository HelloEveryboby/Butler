def handle_request(action, **kwargs):
    """
    处理来自 CLI 或其他接口的请求。
    """
    message = kwargs.get("message", "未收到消息")
    user = kwargs.get("user", "陌生人")

    if action == "run":
        return f"👋 Hello {user}! 你发送的消息是: {message}"
    elif action == "echo":
        return f"📢 Echo: {kwargs}"
    else:
        return f"❓ 未知动作: {action}"
