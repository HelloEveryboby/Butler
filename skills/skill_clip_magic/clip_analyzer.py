import os
import socket
import threading
import re
import ast
import time
from butler.core.ipc_tlv import recv_tlv
from butler.core.blackboard import blackboard

# 服务状态追踪
_service_active = False
_service_thread = None
_service_started_at = 0.0
_last_clipboard = {}

def handle_request(action, **kwargs):
    global _service_active, _service_thread, _service_started_at
    if action == "run":
        if _service_active:
            return "ClipMagic 服务已在运行中"
        _service_active = True
        _service_started_at = time.time()
        _service_thread = threading.Thread(target=clip_bridge_thread, daemon=True)
        _service_thread.start()
        return "ClipMagic background service started."
    elif action == "stop":
        if not _service_active:
            return "ClipMagic 服务未运行"
        _service_active = False
        # 关闭 socket 以中断 accept() 阻塞
        try:
            sock_path = "butler_clip.sock"
            if os.path.exists(sock_path):
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(sock_path)
                s.close()
        except Exception:
            pass
        return "ClipMagic 服务已停止"
    elif action == "status":
        if _service_active:
            uptime = int(time.time() - _service_started_at)
            clip_text = blackboard.read("clipboard.text") or ""
            clip_type = blackboard.read("clipboard.type") or "unknown"
            return f"ClipMagic 运行中 (uptime: {uptime}s)\n最近剪贴板类型: {clip_type}\n内容预览: {clip_text[:50]}"
        return "ClipMagic 服务未运行"
    elif action == "history":
        # 从 blackboard 读取最近的分类记录
        clip_text = blackboard.read("clipboard.text") or ""
        clip_type = blackboard.read("clipboard.type") or "unknown"
        if clip_text:
            return f"最近剪贴板内容:\n  类型: {clip_type}\n  内容: {clip_text[:200]}"
        return "暂无剪贴板记录"
    return f"Action {action} not supported. 可用: run, stop, status, history"

def classify_content(text):
    """AST and Regex based classification."""
    # 1. Regex for URL
    if re.match(r'^https?://[^\s]+', text):
        return "url"

    # 2. Regex for IP
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', text):
        return "ip_address"

    # 3. AST for Code detection
    try:
        ast.parse(text)
        if len(text) > 20: # Heuristic for code
            return "python_code"
    except:
        pass

    return "plain_text"

def clip_bridge_thread():
    global _service_active
    socket_path = "butler_clip.sock"
    if os.path.exists(socket_path): os.remove(socket_path)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(1)
    server.settimeout(2.0)  # 允许周期性检查 _service_active

    while _service_active:
        try:
            conn, _ = server.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        try:
            while _service_active:
                t, v = recv_tlv(conn)
                if t is None: break

                if t == 2: # Clipboard Text
                    content = v.decode('utf-8', errors='ignore')
                    ctype = classify_content(content)

                    # Update state
                    blackboard.write("clipboard.text", content, ttl=300)
                    blackboard.write("clipboard.type", ctype, ttl=300)

                    print(f"ClipMagic detected {ctype}: {content[:30]}...")
        except Exception as e:
            print(f"Clip Bridge error: {e}")
        finally:
            conn.close()

    try:
        server.close()
    except Exception:
        pass
    if os.path.exists(socket_path):
        try:
            os.remove(socket_path)
        except Exception:
            pass
