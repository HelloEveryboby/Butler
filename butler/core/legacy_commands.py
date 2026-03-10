# butler/legacy_commands.py

import os
import cv2
import datetime
import threading
from .intent_dispatcher import register_intent
from . import algorithms
from package.document import task_manager_bridge # Register task_manage intent

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

# 用于存储待确认的转换任务
pending_marker_tasks = {}

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

@register_intent("memory_search")
def handle_memory_search(jarvis_app, entities, **kwargs):
    """在长期记忆和每日日志中搜索信息。"""
    query = entities.get("query")
    if not query:
        jarvis_app.speak("请提供您想搜索的内容。")
        return
    from package.document.memory_tools import memory_tools
    result = memory_tools.memory_search(query)
    jarvis_app.ui_print(result)
    jarvis_app.speak(f"已为您搜索记忆，结果已显示在面板上。")

@register_intent("memory_get")
def handle_memory_get(jarvis_app, entities, **kwargs):
    """从特定的记忆文件中获取详细内容。"""
    path = entities.get("path")
    line_start = int(entities.get("line_start", 1))
    num_lines = int(entities.get("num_lines", -1))
    if not path:
        jarvis_app.speak("请提供记忆文件的路径。")
        return
    from package.document.memory_tools import memory_tools
    result = memory_tools.memory_get(path, line_start, num_lines)
    jarvis_app.ui_print(result)

@register_intent("memory_record")
def handle_memory_record(jarvis_app, entities, **kwargs):
    """记录一条新的记忆。"""
    content = entities.get("content")
    mem_type = entities.get("type", "daily")
    if not content:
        jarvis_app.speak("请提供要记录的内容。")
        return
    from package.document.memory_tools import memory_tools
    result = memory_tools.memory_record(content, mem_type)
    jarvis_app.speak(result)

@register_intent("pdf_assistant")
def handle_pdf_assistant(jarvis_app, entities, **kwargs):
    """切换到 PDF 助手模式或处理 PDF 相关任务。"""
    jarvis_app.ui_print("--- PDF 助手模式已激活 ---", tag='system_message')

    # 如果用户没有提供具体 PDF 路径，先询问
    path = entities.get("path")
    if not path:
        jarvis_app.speak("您好！我是您的 PDF 助手。请提供您需要处理的 PDF 文件路径，并告诉我您想进行的操作（如总结、提取表格或问答）。")
    else:
        # 如果提供了路径，直接触发解释器模式，并注入 PDF 助手上下文
        jarvis_app.ui_print(f"正在为您分析 PDF 文档: {path}")
        # 这里我们可以直接复用解释器逻辑，但可以在 prompt 中增强 PDF 助手的角色感
        jarvis_app._execute_with_llm_interpreter(f"请作为 PDF 助手，分析并处理以下文件：{path}。用户需求：{entities.get('operation', '解析该文档')}")

@register_intent("crawl")
def handle_crawl(jarvis_app, entities, **kwargs):
    """网页爬虫意图处理。"""
    url = entities.get("url")
    query = entities.get("search_query")
    res_type = entities.get("type", "image")

    def run_crawl():
        try:
            from package.network.crawler import run as crawl_run
            jarvis_app.ui_print(f"🚀 正在启动爬虫 (URL: {url or '搜索'}, 类型: {res_type})...")
            crawl_run(url=url, search_query=query, type=res_type)
            jarvis_app.speak("爬虫任务执行完毕。")
        except Exception as e:
            jarvis_app.speak(f"爬虫执行失败: {e}")

    threading.Thread(target=run_crawl, daemon=True).start()

@register_intent("email_op")
def handle_email_op(jarvis_app, entities, **kwargs):
    """邮件操作意图处理。"""
    op = entities.get("operation", "receive")

    def run_email():
        try:
            from package.network.e_mail import EmailAssistant
            assistant = EmailAssistant()
            if op == "send":
                to = entities.get("to")
                subject = entities.get("subject", "来自 Jarvis 的邮件")
                body = entities.get("body", "")
                if to and body:
                    jarvis_app.ui_print(f"📧 正在发送邮件到 {to}...")
                    # 注意：send_email 内部有 input() 确认，在某些 UI 下可能阻塞
                    # 这里假设是简单的后端调用或 UI 已处理确认
                    assistant.send_email(subject, body, to)
                    jarvis_app.speak("邮件已发送。")
                else:
                    jarvis_app.speak("发送邮件需要收件人和正文。")
            else:
                jarvis_app.ui_print("📥 正在检查未读邮件...")
                emails = assistant.fetch_unread_emails()
                assistant.display_emails(emails)
                jarvis_app.speak(f"已获取 {len(emails)} 封邮件，请在面板查看详情。")
        except Exception as e:
            jarvis_app.speak(f"邮件操作失败: {e}")

    threading.Thread(target=run_email, daemon=True).start()

@register_intent("image_search")
def handle_image_search(jarvis_app, entities, **kwargs):
    """图片搜索意图处理。"""
    query = entities.get("query")
    path = entities.get("path")
    mode = entities.get("mode", "local")

    def run_img_search():
        try:
            from package.network.image_search_tool import run as img_run
            jarvis_app.ui_print(f"🔍 正在搜索图片: {query or path}...")
            img_run(query=query, path=path, mode=mode)
            jarvis_app.speak("图片搜索完成。")
        except Exception as e:
            jarvis_app.speak(f"图搜失败: {e}")

    threading.Thread(target=run_img_search, daemon=True).start()

@register_intent("crypto_op")
def handle_crypto_op(jarvis_app, entities, **kwargs):
    """加解密操作意图处理。"""
    op = entities.get("operation", "encrypt")
    path = entities.get("path")
    algo = entities.get("algo", "AES")

    if not path:
        jarvis_app.speak("请提供文件路径。")
        return

    def run_crypto():
        try:
            from package.security.encrypt import EnhancedEncryptor
            jarvis_app.ui_print(f"🔐 正在执行{algo}{'加密' if op=='encrypt' else '解密'}: {path}...")
            # 同样注意：handle_file 内部有 getpass，可能在无交互 UI 下挂起
            EnhancedEncryptor().handle_file(path, algo, op)
            jarvis_app.speak(f"文件{'加密' if op=='encrypt' else '解密'}完成。")
        except Exception as e:
            jarvis_app.speak(f"加密操作失败: {e}")

    threading.Thread(target=run_crypto, daemon=True).start()

@register_intent("get_weather")
def handle_get_weather(jarvis_app, entities, **kwargs):
    """天气查询意图处理。"""
    city = entities.get("city")
    if not city:
        jarvis_app.speak("请告诉我你想查询哪个城市的天气。")
        return

    def run_weather():
        try:
            from package.network.weather import get_weather_from_web
            res = get_weather_from_web(city)
            if res:
                report = f"{city}的天气是：{res['description']}，温度{res['temperature']}，湿度{res['humidity']}。"
                jarvis_app.speak(report)
            else:
                jarvis_app.speak(f"抱歉，我没能查到{city}的天气。")
        except Exception as e:
            jarvis_app.speak(f"天气查询出错: {e}")

    threading.Thread(target=run_weather, daemon=True).start()

@register_intent("manage_file")
def handle_manage_file(jarvis_app, entities, **kwargs):
    """基础文件操作意图处理。"""
    op = entities.get("operation")
    path = entities.get("file_path")
    content = entities.get("content", "")

    if not op or not path:
        jarvis_app.speak("文件操作需要指定操作类型和路径。")
        return

    try:
        from package.file_system.file_manager import FileManager
        fm = FileManager()
        if op == "create" or op == "write":
            success, msg = fm.create_file(path, content)
            jarvis_app.speak(msg)
        elif op == "read":
            success, res = fm.read_file(path)
            if success:
                jarvis_app.ui_print(f"📄 文件内容 ({path}):\n{res}")
                jarvis_app.speak("文件读取完成，内容已显示在面板。")
            else:
                jarvis_app.speak(res)
        elif op == "delete":
            success, msg = fm.delete_file(path)
            jarvis_app.speak(msg)
    except Exception as e:
        jarvis_app.speak(f"文件操作失败: {e}")

@register_intent("convert_file")
def handle_convert_file(jarvis_app, entities, **kwargs):
    """文件转换意图处理。"""
    input_p = entities.get("input_path")
    output_p = entities.get("output_path")

    if not input_p or not output_p:
        jarvis_app.speak("请提供输入和输出文件路径。")
        return

    def run_convert():
        try:
            from package.document.file_converter import run as conv_run
            jarvis_app.ui_print(f"🔄 正在转换文件: {input_p} -> {output_p}")
            conv_run(input_file=input_p, output_file=output_p)
            jarvis_app.speak("文件转换完成。")
        except Exception as e:
            jarvis_app.speak(f"转换失败: {e}")

    threading.Thread(target=run_convert, daemon=True).start()

@register_intent("translate_op")
def handle_translate_op(jarvis_app, entities, **kwargs):
    """翻译操作意图处理。"""
    text = entities.get("text")
    path = entities.get("path")
    url = entities.get("url")

    def run_trans():
        try:
            from package.document.translators import translate_text, translate_file, translate_website
            if text:
                res = translate_text(text)
                jarvis_app.ui_print(f"🌐 翻译结果: {res}")
                jarvis_app.speak("翻译完成。")
            elif path:
                out = path + ".translated.txt"
                translate_file(path, out)
                jarvis_app.speak(f"文件翻译完成，结果保存在 {out}")
            elif url:
                translate_website(url)
                jarvis_app.speak("网页翻译已处理，请查看控制台输出。")
        except Exception as e:
            jarvis_app.speak(f"翻译失败: {e}")

    threading.Thread(target=run_trans, daemon=True).start()

@register_intent("system_monitor", requires_entities=False)
def handle_system_monitor(jarvis_app, **kwargs):
    """系统监控意图处理。"""
    try:
        from package.core_utils.health_monitor import run as monitor_run
        monitor_run()
        jarvis_app.speak("系统健康报告已生成。")
    except Exception as e:
        jarvis_app.speak(f"监控运行失败: {e}")

@register_intent("system_audit")
def handle_system_audit(jarvis_app, entities, **kwargs):
    """系统审计意图处理。"""
    directory = entities.get("directory")
    try:
        from package.core_utils.system_executor_tool import run as audit_run
        audit_run(dir=directory)
        jarvis_app.speak("高性能系统审计已完成。")
    except Exception as e:
        jarvis_app.speak(f"审计运行失败: {e}")
