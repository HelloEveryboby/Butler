import time
from butler.core.skill_sdk import sdk

def main():
    """
    使用 Butler Skill SDK 的隔离技能示例。
    """
    try:
        # 1. 获取输入
        input_data = sdk.get_input()
        if not input_data:
            return

        action = input_data.get("action", "run")

        # 2. 发送实时反馈
        sdk.speak("正在通过隔离子进程与 SDK 验证热插拔机制...")

        # 3. 模拟工作
        time.sleep(0.5)

        # 4. 写入黑板 (ESB)
        sdk.write_blackboard("test.hot_swap.status", "active")

        # 5. 打印普通日志 (stdout)
        print(f"DEBUG: 收到动作请求 -> {action}")

        # 6. 返回结果
        sdk.set_result({
            "status": "success",
            "message": "隔离执行、SDK 调用与 IPC 通信全部验证成功！"
        })

    except Exception as e:
        sdk.ui_print(f"技能内部错误: {str(e)}", tag="error")

if __name__ == "__main__":
    main()
