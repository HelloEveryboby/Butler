import sys
import json
import time

def main():
    """
    Isolated Skill 示例入口。
    Butler 核心启动该进程后，会通过 stdin 发送初始 payload。
    技能通过 stdout 发送 JSON-RPC 指令进行交互。
    """
    try:
        # 1. 接收来自 Butler 的指令
        line = sys.stdin.readline()
        if not line:
            return

        input_data = json.loads(line)
        action = input_data.get("action", "run")

        # 2. 发送实时反馈 (speak)
        print(json.dumps({
            "action": "speak",
            "payload": {"text": "正在通过隔离子进程验证热插拔机制..."}
        }))
        sys.stdout.flush()

        # 3. 模拟一些计算或任务
        time.sleep(0.5)

        # 4. 打印普通日志 (会被 Butler 捕获并记录)
        print(f"DEBUG: 收到动作请求 -> {action}")
        sys.stdout.flush()

        # 5. 返回最终结果
        result_payload = {
            "status": "success",
            "message": "隔离执行与 IPC 通信验证成功！",
            "process_id": sys.executable
        }

        print(json.dumps({
            "action": "result",
            "payload": result_payload
        }))
        sys.stdout.flush()

    except Exception as e:
        # 错误上报
        print(json.dumps({
            "action": "ui_print",
            "payload": {"text": f"技能内部错误: {str(e)}", "tag": "error"}
        }))

if __name__ == "__main__":
    main()
