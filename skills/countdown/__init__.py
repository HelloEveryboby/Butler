import time
from datetime import datetime, timedelta

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    seconds = entities.get("seconds") or kwargs.get("seconds")
    jarvis = kwargs.get("jarvis_app")

    if not seconds:
        return "请提供秒数。"

    try:
        seconds = int(seconds)
    except:
        return "秒数无效。"

    end_time = datetime.now() + timedelta(seconds=seconds)
    while datetime.now() < end_time:
        remaining = (end_time - datetime.now()).seconds
        if jarvis:
            jarvis.speak(f"剩余时间: {remaining} 秒")
        time.sleep(1)

    msg = "倒计时结束！"
    if jarvis:
        jarvis.speak(msg)
    return msg
