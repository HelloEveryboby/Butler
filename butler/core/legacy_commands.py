# butler/legacy_commands.py

import os
import cv2
import datetime
import threading
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

@register_intent("open_switchboard", requires_entities=False)
def handle_open_switchboard(jarvis_app, **kwargs):
    """打开程序交换机以防止系统混乱。"""
    try:
        from package import autonomous_switch
        # 启动后台守护进程
        threading.Thread(target=autonomous_switch.run, daemon=True).start()
        jarvis_app.speak("自动交换机已在后台启动，将自动管理程序排序并防止混乱。")
    except Exception as e:
        jarvis_app.speak(f"无法启动自动交换机: {e}")

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

@register_intent("query_local_knowledge")
def handle_query_local_knowledge(jarvis_app, entities, **kwargs):
    """在本地知识库中搜索相关信息。"""
    query = entities.get("query")
    kb_name = entities.get("kb_name", "default")
    if not query:
        jarvis_app.speak("请提供您想在知识库中查询的内容。")
        return

    try:
        from package import knowledge_base_manager
        results = knowledge_base_manager.run(operation="query", query=query, kb_name=kb_name)
        jarvis_app.ui_print(results)
        jarvis_app.speak(f"已在知识库 '{kb_name}' 中完成搜索，结果已显示在面板上。")
    except Exception as e:
        jarvis_app.speak(f"查询知识库时出错: {e}")

@register_intent("index_local_files")
def handle_index_local_files(jarvis_app, entities, **kwargs):
    """将本地文件或目录索引到知识库以供后续查询。"""
    path = entities.get("path")
    kb_name = entities.get("kb_name", "default")
    if not path:
        jarvis_app.speak("请提供要索引的文件或目录路径。")
        return

    if not os.path.exists(path):
        jarvis_app.speak(f"找不到路径: {path}")
        return

    def run_index():
        try:
            from package import knowledge_base_manager
            operation = "index_dir" if os.path.isdir(path) else "index_file"
            param = "dir_path" if operation == "index_dir" else "file_path"

            jarvis_app.ui_print(f"开始索引 {path}，这可能需要一点时间...")
            result = knowledge_base_manager.run(operation=operation, kb_name=kb_name, **{param: path})
            jarvis_app.speak(result)
        except Exception as e:
            jarvis_app.speak(f"索引过程中出错: {e}")

    # 开启线程执行，避免阻塞 UI
    threading.Thread(target=run_index, daemon=True).start()

@register_intent("cloud_upload")
def handle_cloud_upload(jarvis_app, entities, **kwargs):
    """上传本地文件到云端网盘。"""
    local_path = entities.get("path")
    remote_path = entities.get("remote_path", "/")

    if not local_path:
        jarvis_app.speak("请提供要上传的本地文件路径。")
        return

    def run_upload():
        try:
            from package import cloud_storage_manager
            jarvis_app.ui_print(f"正在上传 {local_path} 到网盘...")
            result = cloud_storage_manager.run(operation="upload", local_path=local_path, remote_path=remote_path)
            jarvis_app.speak(result)
        except Exception as e:
            jarvis_app.speak(f"上传过程中出错: {e}")

    threading.Thread(target=run_upload, daemon=True).start()

@register_intent("cloud_download")
def handle_cloud_download(jarvis_app, entities, **kwargs):
    """从云端网盘下载文件。"""
    remote_path = entities.get("remote_path")
    local_path = entities.get("local_path", ".")

    if not remote_path:
        jarvis_app.speak("请提供要下载的网盘文件路径。")
        return

    def run_download():
        try:
            from package import cloud_storage_manager
            jarvis_app.ui_print(f"正在从网盘下载 {remote_path}...")
            result = cloud_storage_manager.run(operation="download", remote_path=remote_path, local_path=local_path)
            jarvis_app.speak(result)
        except Exception as e:
            jarvis_app.speak(f"下载过程中出错: {e}")

    threading.Thread(target=run_download, daemon=True).start()

@register_intent("cloud_list")
def handle_cloud_list(jarvis_app, entities, **kwargs):
    """列出云端网盘中的文件和文件夹。"""
    path = entities.get("remote_path", "/")

    def run_list():
        try:
            from package import cloud_storage_manager
            jarvis_app.ui_print(f"正在获取网盘目录 {path} 的列表...")
            result = cloud_storage_manager.run(operation="list", path=path)
            if len(result) > 200:
                jarvis_app.ui_print(result)
                jarvis_app.speak(f"已获取目录 {path} 的列表，文件较多，请在面板查看。")
            else:
                jarvis_app.speak(result)
        except Exception as e:
            jarvis_app.speak(f"获取网盘列表时出错: {e}")

    threading.Thread(target=run_list, daemon=True).start()

@register_intent("cloud_info", requires_entities=False)
def handle_cloud_info(jarvis_app, **kwargs):
    """查看网盘的配额和空间使用信息。"""
    def run_info():
        try:
            from package import cloud_storage_manager
            jarvis_app.ui_print("正在查询网盘容量信息...")
            result = cloud_storage_manager.run(operation="info")
            jarvis_app.speak(result)
        except Exception as e:
            jarvis_app.speak(f"查询网盘信息时出错: {e}")

    threading.Thread(target=run_info, daemon=True).start()

@register_intent("manage_dependencies")
def handle_manage_dependencies(jarvis_app, entities, **kwargs):
    """安装或管理本地依赖库到 lib_external 文件夹。"""
    command = entities.get("command", "install_all")
    package = entities.get("package")

    def run_dep_mgr():
        try:
            from package import dependency_manager
            jarvis_app.ui_print(f"正在启动依赖管理器 (命令: {command})...")
            result = dependency_manager.run(command=command, package=package)
            jarvis_app.speak(result)
        except Exception as e:
            jarvis_app.speak(f"依赖管理执行失败: {e}")

    threading.Thread(target=run_dep_mgr, daemon=True).start()

# 用于存储待确认的任务
pending_marker_tasks = {}
pending_translation_tasks = {}

@register_intent("translate_document")
def handle_translate_document(jarvis_app, entities, **kwargs):
    """翻译各种文档 (PDF, Word, PPTX等)。需要用户确认。"""
    path = entities.get("path")
    target_lang = entities.get("target_lang", "zh")
    confirm_bypass = entities.get("confirm", False)

    if not path:
        jarvis_app.speak("请提供要翻译的文件路径。")
        return

    if not os.path.exists(path):
        jarvis_app.speak(f"找不到文件: {path}")
        return

    if not confirm_bypass:
        # 第一步：预提取并请求确认
        try:
            from package.document import translators
            res = translators.translate_file(path, "", skip_confirmation=False)

            char_count = res.get("char_count", 0)
            task_id = str(datetime.datetime.now().timestamp())
            pending_translation_tasks[task_id] = {"path": path, "target_lang": target_lang}

            jarvis_app.ui_print(f"--- 翻译预解析 ---\n文件: {path}\n字数: {char_count}\n目标语言: {target_lang}")
            jarvis_app.speak(f"已提取出约 {char_count} 个字符。由于大规模翻译会产生 API 消耗，请确认是否继续？如果是，请说“确认翻译”。")
            jarvis_app._last_translate_task_id = task_id
            return
        except Exception as e:
            jarvis_app.speak(f"解析失败: {e}")
            return

    # 如果已经确认，则直接运行
    def run_translate():
        try:
            from package.document import translators
            jarvis_app.ui_print(f"正在翻译文档: {path} (目标语言: {target_lang})")
            # 生成输出文件名
            output_file = os.path.splitext(path)[0] + f"_{target_lang}_translated.md"
            res = translators.translate_file(path, output_file, target_lang=target_lang, skip_confirmation=True)

            if res.get("status") == "success":
                jarvis_app.ui_print(f"翻译结果已保存至: {output_file}")
                jarvis_app.speak(f"翻译任务已完成，结果已保存为 {os.path.basename(output_file)}。")
            else:
                jarvis_app.speak(f"翻译失败: {res.get('message')}")
        except Exception as e:
            jarvis_app.speak(f"翻译过程中出错: {e}")

    threading.Thread(target=run_translate, daemon=True).start()

@register_intent("translate_approve", requires_entities=False)
def handle_translate_approve(jarvis_app, **kwargs):
    """确认执行待定的文档翻译任务。"""
    task_id = getattr(jarvis_app, "_last_translate_task_id", None)
    if not task_id or task_id not in pending_translation_tasks:
        jarvis_app.speak("没有待确认的翻译任务。")
        return

    task = pending_translation_tasks.pop(task_id)
    handle_translate_document(jarvis_app, entities={"path": task["path"], "target_lang": task["target_lang"], "confirm": True})

@register_intent("marker_convert")
def handle_marker_convert(jarvis_app, entities, **kwargs):
    """使用 Marker 高质量转换文档。支持 PDF, DOCX, PPTX, XLSX, HTML, EPUB, 图片。"""
    path = entities.get("path")
    output_format = entities.get("format", "markdown")
    confirm_bypass = entities.get("confirm", False)

    if not path:
        jarvis_app.speak("请提供要转换的文件路径。")
        return

    if not confirm_bypass:
        # 第一步：预解析并请求确认
        try:
            from package import marker_tool
            tool = marker_tool.MarkerTool()
            ext = os.path.splitext(path)[1].lower()

            # 本地初步提取（不耗费 API）
            if ext == '.pdf': extracted = tool.extract_pdf(path)
            elif ext == '.docx': extracted = tool.extract_docx(path)
            elif ext == '.pptx': extracted = tool.extract_pptx(path)
            elif ext in ['.xlsx', '.xls']: extracted = tool.extract_xlsx(path)
            elif ext == '.epub': extracted = tool.extract_epub(path)
            else: extracted = {"text": "文本提取中...", "images": []}

            char_count = len(extracted.get("text", ""))
            img_count = len(extracted.get("images", []))

            task_id = str(datetime.datetime.now().timestamp())
            pending_marker_tasks[task_id] = {"path": path, "format": output_format}

            jarvis_app.ui_print(f"--- 预解析完成 ---\n文件: {path}\n字数: {char_count}\n图像: {img_count}")
            jarvis_app.speak(f"文件预解析已完成。提取了约 {char_count} 个字符和 {img_count} 张图像。请确认是否继续调用 DeepSeek 进行精准转换？如果是，请说“确认转换”。")
            jarvis_app._last_marker_task_id = task_id # 记录在 app 实例中
            return
        except Exception as e:
            jarvis_app.speak(f"预解析失败: {e}")
            return

    # 如果已经确认，则直接运行
    def run_marker():
        try:
            from package import marker_tool
            jarvis_app.ui_print(f"正在进行精准解析: {path}")
            result = marker_tool.MarkerTool().convert(file_path=path, output_format=output_format, skip_confirmation=True)
            jarvis_app.ui_print(result)
            jarvis_app.speak(f"文档转换完成。")
        except Exception as e:
            jarvis_app.speak(f"解析过程中出错: {e}")

    threading.Thread(target=run_marker, daemon=True).start()

@register_intent("marker_approve", requires_entities=False)
def handle_marker_approve(jarvis_app, **kwargs):
    """确认执行待定的 Marker 转换任务。"""
    task_id = getattr(jarvis_app, "_last_marker_task_id", None)
    if not task_id or task_id not in pending_marker_tasks:
        jarvis_app.speak("没有待确认的转换任务。")
        return

    task = pending_marker_tasks.pop(task_id)
    handle_marker_convert(jarvis_app, entities={"path": task["path"], "format": task["format"], "confirm": True})

@register_intent("structured_extract")
def handle_structured_extract(jarvis_app, entities, **kwargs):
    """根据指定的 JSON Schema 从文档中提取结构化数据。"""
    path = entities.get("path")
    schema_path = entities.get("schema_path")

    if not path:
        jarvis_app.speak("请提供要提取数据的文件路径。")
        return

    def run_extract():
        try:
            from package import marker_tool
            import json

            schema = None
            if schema_path and os.path.exists(schema_path):
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema = json.load(f)

            jarvis_app.ui_print(f"正在根据 Schema 提取结构化数据: {path}")
            result = marker_tool.MarkerTool().convert(file_path=path, json_schema=schema)

            if "用户取消转换" in str(result):
                jarvis_app.speak("已取消结构化提取。")
            else:
                jarvis_app.ui_print(result)
                jarvis_app.speak("结构化提取完成。")
        except Exception as e:
            jarvis_app.speak(f"提取过程中出错: {e}")

    threading.Thread(target=run_extract, daemon=True).start()
