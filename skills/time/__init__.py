from datetime import datetime

def handle_request(action, **kwargs):
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    return f"现在是北京时间 {current_time}"
