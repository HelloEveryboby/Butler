import os
import socket
import threading
import re
import ast
from butler.core.ipc_tlv import recv_tlv
from butler.core.blackboard import blackboard

def handle_request(action, **kwargs):
    if action == "run":
        threading.Thread(target=clip_bridge_thread, daemon=True).start()
        return "ClipMagic background service started."
    return f"Action {action} not supported."

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
    socket_path = "butler_clip.sock"
    if os.path.exists(socket_path): os.remove(socket_path)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(1)

    while True:
        conn, _ = server.accept()
        try:
            while True:
                t, v = recv_tlv(conn)
                if t is None: break

                if t == 2: # Clipboard Text
                    content = v.decode('utf-8', errors='ignore')
                    ctype = classify_content(content)

                    # Update state
                    blackboard.write("clipboard.text", content, ttl=300)
                    blackboard.write("clipboard.type", ctype, ttl=300)

                    print(f"ClipMagic detected {ctype}: {content[:30]}...")
                    # In real app: jarvis_app.ui_print(f"Detected {ctype}")
        except Exception as e:
            print(f"Clip Bridge error: {e}")
        finally:
            conn.close()
