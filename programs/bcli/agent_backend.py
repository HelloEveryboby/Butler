import sys
import json
import os
import re
import time
import subprocess
import shutil
from pathlib import Path

# 环境配置
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
os.chdir(project_root)

# 重定向标准输出/错误，确保 JSON Bridge 干净
real_stdout = sys.__stdout__
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# 禁用所有模块的日志输出
import logging
logging.root.handlers = []
logging.root.setLevel(logging.CRITICAL)

# 消息发送助手
def send_msg(type, content, extra=None):
    msg = {"type": type, "content": content}
    if extra: msg["extra"] = extra
    # 使用 json.dumps 处理所有转义
    real_stdout.write(json.dumps(msg) + "\n")
    real_stdout.flush()

def bcli_ui_print(message, tag='ai_response', extra=None):
    if tag == 'user_input':
        send_msg("text", f"识别到: {message}")
    elif tag == 'error':
        send_msg("error", message)
    elif tag == 'system_message':
        send_msg("thought", message)
    elif tag == 'voice_status':
        send_msg("voice_status", "true" if message else "false")
    else:
        # Avoid double printing if it's already being handled by the loop
        pass

# --- Butler 项目核心工具集成 ---
from package.file_system.file_manager import FileManager
from package.network.crawler import run as crawl_run
from butler.interpreter import interpreter

file_mgr = FileManager()

# 1. 文件操作 (File Operations)
def read_file(path):
    send_msg("file", "正在读取", extra=path)
    success, res = file_mgr.read_file(path)
    return res if success else f"读取失败: {res}"

def write_file(path, content):
    send_msg("file", "正在写入", extra=path)
    success, res = file_mgr.write_to_file(path, content)
    return res

def list_dir(path="."):
    send_msg("file", "正在列出目录", extra=path)
    success, res = file_mgr.list_directory(path)
    return "\n".join(res) if success else res

def delete_file(path):
    send_msg("file", "正在删除", extra=path)
    success, res = file_mgr.delete_file(path)
    return res

def move_file(src, dst):
    send_msg("file", "正在移动/重命名", extra=f"{src} -> {dst}")
    try:
        shutil.move(src, dst)
        return f"成功将 '{src}' 移动/重命名为 '{dst}'。"
    except Exception as e:
        return f"操作失败: {str(e)}"

# 2. 搜索 (Search)
def search_files(pattern, root="."):
    send_msg("tool", "文件搜索", extra=f"名称模式: {pattern}")
    try:
        from butler.core.hybrid_link import HybridLinkClient
        sysutil_path = project_root / "programs/hybrid_sysutil/sysutil"
        if sysutil_path.exists():
            sysutil = HybridLinkClient(executable_path=str(sysutil_path))
            if sysutil.start():
                res = sysutil.call("fast_file_search", {"root": root, "pattern": pattern})
                sysutil.stop()
                if isinstance(res, dict) and "files" in res:
                    return "\n".join(res["files"])
    except: pass
    # 备选方案: 使用 find
    success, output = interpreter.run("shell", f"find {root} -name '*{pattern}*'")
    return output

def search_content(pattern, path=".", regex=True):
    send_msg("tool", "内容搜索", extra=f"关键词: {pattern}")
    # 使用 grep 进行正则搜索
    cmd = f"grep -rnE '{pattern}' {path}" if regex else f"grep -rn '{pattern}' {path}"
    success, output = interpreter.run("shell", cmd)
    return output if success else "未找到匹配内容或执行出错。"

# 3. 执行 (Execution)
def execute_shell(cmd):
    send_msg("tool", "Shell 执行", extra=cmd)
    success, output = interpreter.run("shell", cmd)
    return output

# 4. 网络 (Network)
def web_search(query):
    send_msg("tool", "网页搜索", extra=query)
    from package.network.crawler import run_scrapy_crawler
    return run_scrapy_crawler(query)

def translate(text, target="zh"):
    send_msg("tool", "智能翻译", extra=text[:20] + "...")
    from package.document.translators import translate_text
    return translate_text(text)

# 核心 Agent 逻辑
def run_agentic_loop(query, jarvis):
    nlu = jarvis.nlu_service
    system_prompt = (
        "你是一个名为 Butler CLI 的高级 AI 助手，界面风格模仿 Claude Code。\n"
        "你可以通过调用以下 Python 函数来操作环境：\n"
        "【文件操作】\n"
        "- read_file(path): 读取文件内容。\n"
        "- write_file(path, content): 创建或编辑文件（写入完整内容）。\n"
        "- list_dir(path): 列出目录。\n"
        "- delete_file(path): 删除文件。\n"
        "- move_file(src, dst): 重命名或移动文件。\n"
        "【搜索】\n"
        "- search_files(pattern): 按名称查找文件。\n"
        "- search_content(pattern, path): 在文件内容中搜索（支持正则）。\n"
        "【执行】\n"
        "- execute_shell(cmd): 运行 shell 命令、启动服务器、运行测试、使用 git。\n"
        "【网络】\n"
        "- web_search(query): 搜索互联网、获取文档、查找错误信息。\n"
        "- translate(text): 翻译文本。\n\n"
        "请先思考，然后在 ```python ... ``` 代码块中执行。你可以分多步完成复杂任务。"
    )

    history = jarvis.long_memory.get_recent_history(10)
    current_prompt = f"{system_prompt}\n\n用户请求: {query}"

    exec_globals = {
        "read_file": read_file,
        "write_file": write_file,
        "list_dir": list_dir,
        "delete_file": delete_file,
        "move_file": move_file,
        "search_files": search_files,
        "search_content": search_content,
        "web_search": web_search,
        "translate": translate,
        "execute_shell": execute_shell,
        "jarvis": jarvis
    }

    # Handle Special Commands
    if query == "/voice":
        jarvis.voice_service.ui_print = bcli_ui_print
        jarvis.voice_service.on_status_change = lambda status: send_msg("voice_status", "true" if status else "false")
        jarvis.voice_service.start_listening()
        # Wait for recognition to finish (async in backend but we need to keep loop alive)
        while jarvis.voice_service.is_listening:
            time.sleep(0.1)
        return

    if query.startswith("/voice-engine "):
        engine = query.split(" ")[1]
        if jarvis.voice_service.set_voice_mode(engine):
            send_msg("text", f"已切换至 {engine} 语音引擎。")
        else:
            send_msg("error", "无效的引擎名称。可用: online, local")
        return

    for iteration in range(10):
        send_msg("thought", f"正在思考 (步骤 {iteration + 1})...")
        response = nlu.ask_llm(current_prompt, history)

        code_match = re.search(r"```python\n(.*?)```", response, re.DOTALL)
        thought = response.split("```python")[0].strip()
        if not thought: thought = "正在处理您的请求..."

        if code_match:
            code = code_match.group(1)
            send_msg("thought", thought)
            send_msg("code", code, extra="python")

            import io
            from contextlib import redirect_stdout
            f = io.StringIO()
            success = True
            try:
                with redirect_stdout(f):
                    exec(code, exec_globals)
                output = f.getvalue()
            except Exception as e:
                success = False
                output = str(e)

            if success:
                if output: send_msg("shell", output)
                current_prompt = f"操作结果:\n{output if output else '执行成功'}\n\n请继续或完成任务。"
                history.append({"role": "assistant", "content": response})
                history.append({"role": "user", "content": f"结果: {output}"})
            else:
                send_msg("error", f"执行出错: {output}")
                current_prompt = f"报错: {output}\n\n请修正并重试。"
        else:
            send_msg("text", response)
            break

if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(1)
    query = sys.argv[2]

    try:
        from butler.butler_app import Jarvis
        jarvis = Jarvis(headless=True)
        run_agentic_loop(query, jarvis)
    except Exception as e:
        send_msg("error", f"初始化失败: {str(e)}")
