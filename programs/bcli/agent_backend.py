import sys
import json
import os
import re
import time
import subprocess
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

# --- Butler 项目核心工具集成 ---
from package.file_system.file_manager import FileManager
from package.network.crawler import run as crawl_run
from butler.interpreter import interpreter

file_mgr = FileManager()

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

def execute_shell(cmd):
    send_msg("tool", "Shell 执行", extra=cmd)
    success, output = interpreter.run("shell", cmd)
    return output

def search_files(pattern, root="."):
    send_msg("tool", "高速搜索", extra=f"关键词: {pattern}")
    try:
        from butler.core.hybrid_link import HybridLinkClient
        sysutil = HybridLinkClient(executable_path=str(project_root / "programs/hybrid_sysutil/sysutil"))
        if sysutil.start():
            res = sysutil.call("fast_file_search", {"root": root, "pattern": pattern})
            sysutil.stop()
            if isinstance(res, dict) and "files" in res:
                return "\n".join(res["files"])
    except: pass
    return "搜索工具不可用或执行失败。"

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
        "你是一个高级软件工程师助手 (Butler CLI)。请使用以下项目专属工具解决问题：\n"
        "- read_file(path): 读取本地文件。\n"
        "- write_file(path, content): 写入文件内容。\n"
        "- list_dir(path='.'): 列出目录内容。\n"
        "- search_files(pattern): 使用高速 C 语言引擎查找文件。\n"
        "- web_search(query): 搜索互联网信息。\n"
        "- translate(text): 翻译文字或文档。\n"
        "- execute_shell(cmd): 执行本地 Shell 或 Git 命令。\n"
        "请先进行深度的逻辑思考，然后在 ```python ... ``` 代码块中执行操作。你可以进行多步操作直到任务完成。"
    )

    history = jarvis.long_memory.get_recent_history(10)
    current_prompt = f"{system_prompt}\n\n用户请求: {query}"

    # 注入执行环境
    exec_globals = {
        "read_file": read_file,
        "write_file": write_file,
        "list_dir": list_dir,
        "search_files": search_files,
        "web_search": web_search,
        "translate": translate,
        "execute_shell": execute_shell,
        "jarvis": jarvis
    }

    for iteration in range(10):
        send_msg("thought", f"正在思考 (步骤 {iteration + 1})...")
        response = nlu.ask_llm(current_prompt, history)

        # 解析 AI 的回复
        code_match = re.search(r"```python\n(.*?)```", response, re.DOTALL)
        thought = response.split("```python")[0].strip()
        if not thought: thought = "正在调用项目工具..."

        if code_match:
            code = code_match.group(1)
            send_msg("thought", thought)
            send_msg("code", code, extra="python")

            # 捕获 Python 的 stdout
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
                current_prompt = f"上一步操作结果:\n{output if output else '执行成功'}\n\n请继续或给出最终结论。"
                history.append({"role": "assistant", "content": response})
                history.append({"role": "user", "content": f"结果: {output}"})
            else:
                send_msg("error", f"执行出错: {output}")
                current_prompt = f"上一步报错了: {output}\n\n请修复代码并重试。"
        else:
            # 最终总结
            send_msg("text", response)
            break

if __name__ == "__main__":
    if len(sys.argv) < 3: sys.exit(1)
    query = sys.argv[2]

    try:
        from butler.butler_app import Jarvis
        jarvis = Jarvis(headless=True)
        # 启动 Agent 循环
        run_agentic_loop(query, jarvis)
    except Exception as e:
        send_msg("error", f"后端初始化失败: {str(e)}")
