import sys
import json
import os
import re
import time
import subprocess
from pathlib import Path

# SET UP ENVIRONMENT
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
os.chdir(project_root)

# REDIRECT STDOUT/STDERR TO PREVENT NOISE
real_stdout = sys.__stdout__
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# Suppress all logging
import logging
logging.root.handlers = []
logging.root.setLevel(logging.CRITICAL)

def send_msg(type, content, extra=None):
    msg = {"type": type, "content": content}
    if extra: msg["extra"] = extra
    real_stdout.write(json.dumps(msg) + "\n")
    real_stdout.flush()

# --- Integration of PROJECT DEVELOPED functions ---

# 1. File Management (from package.file_system.file_manager)
from package.file_system.file_manager import FileManager
file_mgr = FileManager()

def read_file(path):
    send_msg("file", "Reading (Project Tool)", extra=path)
    success, res = file_mgr.read_file(path)
    return res if success else f"Error: {res}"

def write_file(path, content):
    send_msg("file", "Writing (Project Tool)", extra=path)
    success, res = file_mgr.write_to_file(path, content)
    return res

def list_dir(path="."):
    send_msg("file", "Listing (Project Tool)", extra=path)
    success, res = file_mgr.list_directory(path)
    return "\n".join(res) if success else res

# 2. Search (from hybrid_sysutil and crawler)
def search_files(pattern, root="."):
    send_msg("tool", "Fast Search (Project Tool)", extra=f"pattern: {pattern}")
    try:
        from butler.core.hybrid_link import HybridLinkClient
        sysutil = HybridLinkClient(executable_path=str(project_root / "programs/hybrid_sysutil/sysutil"))
        if sysutil.start():
            res = sysutil.call("fast_file_search", {"root": root, "pattern": pattern})
            sysutil.stop()
            if isinstance(res, dict) and "files" in res:
                return "\n".join(res["files"])
    except: pass
    return "Search tool failed or not found."

# 3. Network (from package.network.crawler and translators)
def web_search(query):
    send_msg("tool", "Web Crawl (Project Tool)", extra=query)
    from package.network.crawler import run_scrapy_crawler
    return run_scrapy_crawler(query)

def translate(text, target="zh"):
    send_msg("tool", "Translator (Project Tool)", extra=text[:20] + "...")
    from package.document.translators import translate_text
    return translate_text(text)

# 4. Execution (from butler.interpreter)
from butler.interpreter import interpreter
def execute_shell(cmd):
    send_msg("tool", "Shell Exec (Project Tool)", extra=cmd)
    success, output = interpreter.run("shell", cmd)
    return output

def run_agentic_loop(query, jarvis):
    nlu = jarvis.nlu_service
    system_prompt = (
        "You are an AI software engineer. Use the following PROJECT-SPECIFIC tools:\n"
        "- read_file(path): Uses Butler's FileManager.\n"
        "- write_file(path, content): Uses Butler's FileManager.\n"
        "- list_dir(path='.'): Uses Butler's FileManager.\n"
        "- search_files(pattern): Uses Butler's high-speed C-based search utility.\n"
        "- web_search(query): Uses Butler's Scrapy-based crawler.\n"
        "- translate(text): Uses Butler's DeepSeek-integrated translator.\n"
        "- execute_shell(cmd): Uses Butler's secure interpreter.\n"
        "Plan your steps and act in ```python ... ``` blocks."
    )

    history = jarvis.long_memory.get_recent_history(10)
    current_prompt = f"{system_prompt}\n\nUser Query: {query}"

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
        send_msg("thought", f"Thinking Step {iteration + 1}...")
        response = nlu.ask_llm(current_prompt, history)

        code_match = re.search(r"```python\n(.*?)```", response, re.DOTALL)
        thought = response.split("```python")[0].strip()
        if not thought: thought = "Calling project tools..."

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
                current_prompt = f"Previous Action Result:\n{output if output else 'Success'}\n\nContinue or Finish?"
                history.append({"role": "assistant", "content": response})
                history.append({"role": "user", "content": f"Result: {output}"})
            else:
                send_msg("error", output)
                current_prompt = f"Error occurred: {output}\n\nPlease fix and try again."
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
        send_msg("error", f"Backend initialization failed: {str(e)}")
