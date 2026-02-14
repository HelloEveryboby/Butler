# butler/legacy_commands.py

import os
import cv2
import datetime
from .intent_dispatcher import register_intent
from . import algorithms

# 注意：这些函数旨在通过意图分发器动态传递的关键字参数调用。
# `jarvis_app` 参数是一个特殊情况，由分发器注入，以提供
# 对主应用程序实例的访问（用于 `speak` 和 `ui_print` 等方法）。

@register_intent("sort_numbers")
def handle_sort_numbers(jarvis_app, entities, **kwargs):
    """对 'numbers' 实体中提供的数字列表进行排序。"""
    try:
        numbers = entities.get("numbers", [])
        if not numbers or not all(isinstance(n, (int, float)) for n in numbers):
             jarvis_app.speak("排序失败，请提供有效的数字列表。")
             return
        sorted_nums = algorithms.quick_sort(numbers)
        jarvis_app.speak(f"排序结果: {sorted_nums}")
    except Exception as e:
        jarvis_app.speak(f"排序时发生错误: {e}")

@register_intent("find_number")
def handle_find_number(jarvis_app, entities, **kwargs):
    """在已排序的数字列表中查找目标数字的索引。"""
    try:
        numbers = entities.get("numbers", [])
        target = entities.get("target")
        if not numbers or target is None:
            jarvis_app.speak("查找失败，请提供数字列表和目标数字。")
            return

        numbers.sort()
        index = algorithms.binary_search(numbers, target)
        if index != -1:
            jarvis_app.speak(f"数字 {target} 在排序后的位置是: {index}")
        else:
            jarvis_app.speak(f"数字 {target} 不在数组中")
    except Exception as e:
        jarvis_app.speak(f"查找时发生错误: {e}")

@register_intent("calculate_fibonacci")
def handle_calculate_fibonacci(jarvis_app, entities, **kwargs):
    """计算斐波那契数列中的第 N 个数字。"""
    try:
        n = entities.get("number")
        if n is None or not isinstance(n, int):
            jarvis_app.speak("计算失败，请输入一个有效的整数。")
            return
        fib = algorithms.fibonacci(n)
        jarvis_app.speak(f"斐波那契数列第{n}项是: {fib}")
    except Exception as e:
        jarvis_app.speak(f"计算斐波那契数时出错: {e}")

@register_intent("edge_detect_image")
def handle_edge_detect_image(jarvis_app, entities, **kwargs):
    """检测给定文件路径图像中的边缘并保存结果。"""
    try:
        image_path = entities.get("path")
        if not image_path or not isinstance(image_path, str):
            jarvis_app.speak("图像处理失败，请提供有效的路径。")
            return

        if os.path.exists(image_path):
            edges = algorithms.edge_detection(image_path)
            if edges is not None:
                output_path = os.path.splitext(image_path)[0] + '_edges.jpg'
                cv2.imwrite(output_path, edges)
                jarvis_app.speak(f"边缘检测完成，结果已保存到: {output_path}")
            else:
                jarvis_app.speak("图像处理失败，无法读取图片。")
        else:
            jarvis_app.speak("找不到指定的图像文件。")
    except Exception as e:
        jarvis_app.speak(f"图像处理时出错: {e}")

@register_intent("text_similarity")
def handle_text_similarity(jarvis_app, entities, **kwargs):
    """计算两段文本之间的余弦相似度分数。"""
    try:
        text1 = entities.get("text1")
        text2 = entities.get("text2")
        if not text1 or not text2:
            jarvis_app.speak("相似度计算失败，请提供两段文本。")
            return
        similarity = algorithms.text_cosine_similarity(text1, text2)
        jarvis_app.speak(f"文本相似度是: {similarity:.2f}")
    except Exception as e:
        jarvis_app.speak(f"计算相似度时出错: {e}")

@register_intent("open_program")
def handle_open_program(jarvis_app, entities, programs, **kwargs):
    """打开按名称指定的程序或应用程序。"""
    program_name = entities.get("program_name")
    if not program_name:
        jarvis_app.speak("无法打开程序，未指定程序名称。")
        return

    # This function relies on the `execute_program` method of the Jarvis instance
    # and the program mapping, so we delegate back to it.
    jarvis_app._handle_open_program(entities, programs)

@register_intent("exit", requires_entities=False)
def handle_exit(jarvis_app, **kwargs):
    """退出 Jarvis 助手应用程序。"""
    jarvis_app._handle_exit()

@register_intent("get_current_time", requires_entities=False)
def handle_get_current_time(jarvis_app, **kwargs):
    """获取当前时间并播报。"""
    current_time = datetime.datetime.now().strftime("%H:%M")
    jarvis_app.speak(f"现在时间是 {current_time}")

@register_intent("cleanup", requires_entities=False)
def handle_cleanup(jarvis_app, **kwargs):
    """执行数据回收/清理系统以删除临时文件。"""
    jarvis_app.ui_print("正在执行系统数据回收...")
    try:
        from package import data_recycler
        summary = data_recycler.run()
        jarvis_app.speak(f"数据回收完成。{summary}")
    except Exception as e:
        jarvis_app.speak(f"数据回收失败: {e}")

@register_intent("iot_control")
def handle_iot_control(jarvis_app, entities, **kwargs):
    """控制连接的单片机设备（如开灯、关灯）。"""
    device = entities.get("device", "设备")
    action_raw = entities.get("action", "toggle")

    try:
        from package import mqtt_gateway
        # 归一化操作指令
        if any(word in action_raw.lower() for word in ["open", "on", "开启", "打开", "开"]):
            state = "on"
            action_desc = "开启"
        elif any(word in action_raw.lower() for word in ["close", "off", "关闭", "关"]):
            state = "off"
            action_desc = "关闭"
        else:
            state = "toggle"
            action_desc = "切换"

        result = mqtt_gateway.run("publish", "light_control", f"state={state}")

        if isinstance(result, dict) and result.get("success"):
            jarvis_app.speak(f"好的，已为您{action_desc}{device}。")
        else:
            jarvis_app.speak(f"抱歉，控制{device}失败，请确保单片机在线且 MQTT 服务正常。")
    except Exception as e:
        jarvis_app.speak(f"执行 IOT 控制时出错: {e}")

@register_intent("get_mcu_status", requires_entities=False)
def handle_get_mcu_status(jarvis_app, **kwargs):
    """获取单片机终端的当前状态。"""
    try:
        from package import mqtt_gateway
        status = mqtt_gateway.run("status")
        if status:
            uptime = status.get("uptime", 0)
            light_state = "开启" if status.get("light_state") else "关闭"
            jarvis_app.speak(f"单片机报告在线。当前灯光状态：{light_state}。运行时间：{uptime}秒。")
        else:
            jarvis_app.speak("暂未收到单片机状态上报，它可能处于离线状态。")
    except Exception as e:
        jarvis_app.speak(f"查询单片机状态时出错: {e}")
