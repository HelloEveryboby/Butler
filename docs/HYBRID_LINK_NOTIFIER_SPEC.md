# Butler 提醒系统 BHL 通信协议设计

## 1. 概述
为了实现 C++ 后端对 Python 逻辑层的驱动，我们采用 **BHL (Butler Hybrid Link)** 协议。C++ 作为事件监控器，通过标准输入/输出流与 Python 进行 JSON-RPC 通信。

## 2. 消息格式

### 2.1 C++ 推送提醒到 Python (Notification Push)
当 C++ 监测到硬件事件或系统状态变化时，向 Python 发送以下指令：

```json
{
    "jsonrpc": "2.0",
    "method": "notify",
    "params": {
        "title": "硬件报警",
        "content": "检测到核心温度过高 (85°C)",
        "priority": 2,
        "source": "hardware_monitor",
        "action_data": {
            "device": "cpu",
            "value": 85
        }
    },
    "id": "optional_uuid"
}
```

### 2.2 Python 反馈处理结果 (Optional)
Python 逻辑层在处理完 `push` 请求后（如已记录日志并触发 UI），可以返回：

```json
{
    "jsonrpc": "2.0",
    "result": {"status": "success", "event_id": "notif_123456"},
    "id": "optional_uuid"
}
```

## 3. C++ 侧集成逻辑 (programs/bcli/src/bridge.c 扩展建议)

在 C++ 侧，我们需要确保有一个持久的管道可以向 Python 发送数据。目前的 `bridge_send_query` 是短连接模式。
建议增加一个 `bridge_notify` 函数：

```c
void bridge_notify(const char* title, const char* content, int priority) {
    // 构造符合 BHL 协议的 JSON 字符串
    char buf[1024];
    snprintf(buf, sizeof(buf),
        "{\"jsonrpc\": \"2.0\", \"method\": \"notify\", \"params\": {\"title\": \"%s\", \"content\": \"%s\", \"priority\": %d}}\n",
        title, content, priority);

    // 写入到 Python 进程的 stdin
    if (py_stdin_fd != -1) {
        write(py_stdin_fd, buf, strlen(buf));
    }
}
```

## 4. Python 侧集成逻辑 (butler/core/notifier_system.py 扩展)

我们需要在 Python 侧增加一个监听 BHL 指令的循环，或者将其集成到现有的 `ModernBridge` 中。

```python
def handle_bhl_request(request_json):
    msg = json.loads(request_json)
    if msg.get("method") == "notify":
        from butler.core.notifier_system import notifier
        notifier.push(msg["params"])
```

## 5. 5-10 秒自动关闭逻辑流
1.  **C++** 发送 `notify` 消息。
2.  **Python** `Notifier.push()` 被触发。
3.  **Python** 启动 `threading.Timer(duration, ...)`。
4.  **Python** 向 **UI (JS)** 发送渲染指令。
5.  **计时器到期**，Python 发送 `NOTIFICATION_CLOSE` 事件。
6.  **UI (JS)** 执行消失动画并移除 DOM。
7.  **Python** 将数据库中的状态更新为 `closed`。
