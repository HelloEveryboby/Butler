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

@register_intent("vmail_create", requires_entities=False)
def handle_vmail_create(jarvis_app, **kwargs):
    """创建一个新的 vmail.dev 临时邮箱。"""
    try:
        from package import vmail_tool
        assistant = vmail_tool.VMailAssistant(jarvis_app=jarvis_app)
        success, res = assistant.create_mailbox()
        if success:
            jarvis_app.speak(f"成功创建临时邮箱: {res.get('address')}")
            jarvis_app.ui_print(f"临时邮箱已创建: {res.get('address')}\nID: {res.get('id')}")
        else:
            jarvis_app.speak(f"创建失败: {res}")
    except Exception as e:
        jarvis_app.speak(f"执行 Vmail 创建时出错: {e}")

@register_intent("vmail_check")
def handle_vmail_check(jarvis_app, entities, **kwargs):
    """检查 vmail 临时邮箱的收件箱。"""
    try:
        from package import vmail_tool
        assistant = vmail_tool.VMailAssistant(jarvis_app=jarvis_app)
        if not assistant.api_key:
            jarvis_app.speak("未检测到 Vmail API Key，请先使用 '设置 vmail 密钥' 命令进行设置。")
            return
        msgs = assistant.list_messages()
        if not msgs:
            jarvis_app.speak("收件箱目前是空的。")
        else:
            jarvis_app.speak(f"收件箱中有 {len(msgs)} 封邮件。")
            summary = "📬 Vmail 收件箱:\n"
            for i, m in enumerate(msgs[:5]): # 只显示前5个
                summary += f"[{i+1}] {m.get('from')}: {m.get('subject')}\n"
            summary += "\n提示: 可以通过 '查看 vmail 详情' 并提供编号来阅读全文。"
            jarvis_app.ui_print(summary)
    except Exception as e:
        jarvis_app.speak(f"检查 Vmail 时出错: {e}")

@register_intent("vmail_detail")
def handle_vmail_detail(jarvis_app, entities, **kwargs):
    """获取指定编号或 ID 的 vmail 邮件详情。"""
    try:
        from package import vmail_tool
        index = entities.get("index")
        if index is None:
            jarvis_app.speak("请提供您想查看的邮件编号。")
            return

        assistant = vmail_tool.VMailAssistant(jarvis_app=jarvis_app)
        msgs = assistant.list_messages()

        try:
            idx = int(index) - 1
            if 0 <= idx < len(msgs):
                msg_id = msgs[idx].get("id")
                detail = assistant.get_message_detail(msg_id)
                if detail:
                    content = detail.get("text", "") or "无正文内容"
                    jarvis_app.ui_print(f"📧 详情:\n发件人: {detail.get('from')}\n主题: {detail.get('subject')}\n\n{content}")
                    otp = assistant.extract_otp(content)
                    if otp:
                        jarvis_app.speak(f"识别到验证码 {otp}，已为您显示在面板上。")
                    else:
                        jarvis_app.speak("详情已显示在面板上。")
                else:
                    jarvis_app.speak("获取邮件详情失败。")
            else:
                jarvis_app.speak(f"找不到编号为 {index} 的邮件。")
        except ValueError:
             jarvis_app.speak("无效的邮件编号。")
    except Exception as e:
        jarvis_app.speak(f"获取 Vmail 详情时出错: {e}")

@register_intent("vmail_monitor", requires_entities=False)
def handle_vmail_monitor(jarvis_app, **kwargs):
    """启动 Vmail 后台监控。"""
    try:
        from package import vmail_tool
        assistant = vmail_tool.VMailAssistant(jarvis_app=jarvis_app)
        if not assistant.api_key:
            jarvis_app.speak("未设置 API Key，无法启动监控。")
            return
        assistant.start_monitoring()
        jarvis_app.speak("已启动 Vmail 后台监控，如有新邮件我将提醒您。")
    except Exception as e:
        jarvis_app.speak(f"启动监控失败: {e}")

@register_intent("vmail_set_key")
def handle_vmail_set_key(jarvis_app, entities, **kwargs):
    """设置 vmail.dev 的 API 密钥。"""
    api_key = entities.get("api_key")
    if not api_key:
        jarvis_app.speak("请提供有效的 API 密钥。")
        return

    try:
        from package import vmail_tool
        assistant = vmail_tool.VMailAssistant(jarvis_app=jarvis_app)
        assistant.set_api_key(api_key)
        jarvis_app.speak("Vmail API 密钥已成功保存。")
    except Exception as e:
        jarvis_app.speak(f"设置密钥失败: {e}")

@register_intent("vmail_wait_otp", requires_entities=False)
def handle_vmail_wait_otp(jarvis_app, **kwargs):
    """等待最新的 vmail 验证码并自动播报。"""
    try:
        from package import vmail_tool
        assistant = vmail_tool.VMailAssistant(jarvis_app=jarvis_app)
        if not assistant.api_key:
            jarvis_app.speak("请先设置 Vmail API 密钥。")
            return
        if not assistant.active_mailbox:
            jarvis_app.speak("没有激活的临时邮箱，请先创建一个。")
            return

        jarvis_app.speak("正在为您监控新邮件中的验证码，请在网页上点击发送。")
        jarvis_app.ui_print("⏳ 正在等待验证码 (超时时间 60s)...")

        def do_wait():
            otp, err = assistant.wait_for_otp(timeout=60)
            if otp:
                jarvis_app.speak(f"已收到验证码：{otp}。已自动为您复制到剪贴板。")
                jarvis_app.ui_print(f"✨ 成功获取验证码: {otp}")
            else:
                jarvis_app.speak(f"等待验证码失败：{err}")

        threading.Thread(target=do_wait, daemon=True).start()
    except Exception as e:
        jarvis_app.speak(f"启动等待程序失败: {e}")
