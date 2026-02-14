# butler/legacy_commands.py

import os
import cv2
import datetime
from .intent_dispatcher import register_intent
from . import algorithms

# Note: These functions are designed to be called with keyword arguments
# that are dynamically passed from the intent dispatcher. The `jarvis_app`
# argument is a special case, injected by the dispatcher to provide
# access to the main application instance (for methods like `speak` and `ui_print`).

@register_intent("sort_numbers")
def handle_sort_numbers(jarvis_app, entities, **kwargs):
    """Sorts a list of numbers provided in the 'numbers' entity."""
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
    """Finds the index of a target number in a sorted list of numbers."""
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
    """Calculates the Nth number in the Fibonacci sequence."""
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
    """Detects edges in an image from a given file path and saves the result."""
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
    """Calculates the cosine similarity score between two pieces of text."""
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
    """Opens a program or application specified by name."""
    program_name = entities.get("program_name")
    if not program_name:
        jarvis_app.speak("无法打开程序，未指定程序名称。")
        return

    # This function relies on the `execute_program` method of the Jarvis instance
    # and the program mapping, so we delegate back to it.
    jarvis_app._handle_open_program(entities, programs)

@register_intent("exit", requires_entities=False)
def handle_exit(jarvis_app, **kwargs):
    """Exits the Jarvis assistant application."""
    jarvis_app._handle_exit()

@register_intent("get_current_time", requires_entities=False)
def handle_get_current_time(jarvis_app, **kwargs):
    """Gets the current time and speaks it."""
    current_time = datetime.datetime.now().strftime("%H:%M")
    jarvis_app.speak(f"现在时间是 {current_time}")

@register_intent("cleanup", requires_entities=False)
def handle_cleanup(jarvis_app, **kwargs):
    """Executes the data recycling/cleanup system to remove temporary files."""
    jarvis_app.ui_print("正在执行系统数据回收...")
    try:
        from package import data_recycler
        summary = data_recycler.run()
        jarvis_app.speak(f"数据回收完成。{summary}")
    except Exception as e:
        jarvis_app.speak(f"数据回收失败: {e}")
