import os
import sys
import time
import base64
import logging
import threading
import hashlib
from typing import Dict, Any, List
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

logger = logging.getLogger("clipboard_history")
_context = None
_last_clip = ""
_polling_active = False


def get_system_clipboard() -> str:
    """Safely retrieves current clipboard text, with display/OS fallback."""
    # 1. Try Tkinter fallback
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        clip = root.clipboard_get()
        root.destroy()
        if clip:
            return str(clip).strip()
    except Exception:
        pass

    # 2. Try OS subprocess fallback (pbpaste on macOS, xclip on Linux)
    try:
        if sys.platform == "darwin":
            import subprocess
            return subprocess.check_output("pbpaste", text=True).strip()
        elif sys.platform == "linux":
            import subprocess
            # Try xclip, then xsel
            try:
                return subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], text=True).strip()
            except Exception:
                return subprocess.check_output(["xsel", "-b", "-o"], text=True).strip()
    except Exception:
        pass

    return ""


def get_encryption_key() -> str:
    """Retrieves secret seed from SecureVault, falling back to a default system identifier."""
    try:
        from package.security.encrypt import SecureVault
        core_code = SecureVault.get_core_code()
        if core_code:
            return core_code
    except Exception:
        pass
    return "BUTLER_DEFAULT_KEY_CLIP_SEED_789"


def encrypt_text(text: str, key_seed: str) -> str:
    """Encrypts a string using AES-128-CBC and returns a Base64-encoded string."""
    try:
        key = hashlib.sha256(key_seed.encode()).digest()[:16]  # 128-bit key
        cipher = AES.new(key, AES.MODE_CBC)
        iv = cipher.iv
        padded = pad(text.encode('utf-8'), AES.block_size)
        ciphertext = cipher.encrypt(padded)
        combined = iv + ciphertext
        return base64.b64encode(combined).decode('utf-8')
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return text


def decrypt_text(encrypted_b64: str, key_seed: str) -> str:
    """Decrypts an AES-128-CBC base64 string."""
    try:
        combined = base64.b64decode(encrypted_b64.encode('utf-8'))
        key = hashlib.sha256(key_seed.encode()).digest()[:16]
        iv = combined[:16]
        ciphertext = combined[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(ciphertext), AES.block_size)
        return decrypted.decode('utf-8')
    except Exception:
        return "[解密失败：密文损坏或核心码无效]"


def poll_clipboard_loop():
    """Background loop polling system clipboard for modifications."""
    global _context, _last_clip, _polling_active
    _polling_active = True
    logger.info("Clipboard polling loop started.")

    while _polling_active:
        time.sleep(4.0)  # Check every 4 seconds
        if _context is None:
            continue

        try:
            current = get_system_clipboard()
            if current and current != _last_clip:
                _last_clip = current
                # Store new item
                save_clipboard_item(current)
        except Exception as e:
            # Silent fallback to avoid flooding logs
            pass


def save_clipboard_item(text: str) -> None:
    """Encrypts and pushes a new clipboard item into rolling storage."""
    global _context
    if _context is None:
        return

    try:
        key_seed = get_encryption_key()
        encrypted = encrypt_text(text, key_seed)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Load existing history
        history = _context.data_storage.load("clipboard_history", "history") or []

        # Deduplicate: if same encrypted string already exists, move to top or skip
        history = [item for item in history if item.get("data") != encrypted]

        # Insert at the beginning
        history.insert(0, {
            "timestamp": timestamp,
            "data": encrypted
        })

        # Rolling cache limit: maximum 15 items
        if len(history) > 15:
            history = history[:15]

        _context.data_storage.save("clipboard_history", "history", history)
    except Exception as e:
        logger.error(f"Failed to save clipboard item: {e}")


def initialize_core(context) -> None:
    """
    Hook called by SkillManager upon load.
    Directly injects the privileged CorePluginContext.
    """
    global _context, _last_clip
    _context = context
    logger.info("clipboard_history core plugin successfully initialized with privileges.")

    # Seed the initial clipboard state
    try:
        _last_clip = get_system_clipboard()
    except Exception:
        _last_clip = ""

    # Start polling loop thread
    thread = threading.Thread(target=poll_clipboard_loop, daemon=True)
    thread.start()


def handle_request(action: str, **kwargs) -> Any:
    """
    Handles request for clipboard history.
    Supported actions:
    - 'list': Decrypts and outputs standard clipboard history list.
    - 'clear': Wipes clipboard history database.
    - 'add': Manually inserts/encrypts an item into history.
    """
    global _context
    if _context is None:
        return "Error: Core plugin context is not initialized."

    if action == "clear":
        _context.data_storage.save("clipboard_history", "history", [])
        return "🧹 剪贴板历史记录已安全抹除。"

    elif action == "add":
        text = kwargs.get("text")
        if not text:
            return "Error: 'text' parameter is required for manual insertion."
        save_clipboard_item(text)
        return "✅ 已手动加密并载入剪贴板历史记录。"

    elif action == "list" or action == "run":
        history = _context.data_storage.load("clipboard_history", "history") or []
        if not history:
            return "📋 剪贴板历史记录为空（或未捕获到变更）。"

        key_seed = get_encryption_key()
        report = ["🔒 **安全剪贴板历史记录 (已解密并滚动显示最近 15 条)**:"]
        for idx, item in enumerate(history):
            raw_text = decrypt_text(item["data"], key_seed)
            # Truncate text for display
            display_text = raw_text if len(raw_text) < 60 else (raw_text[:57] + "...")
            report.append(f"{idx + 1}. [{item['timestamp']}] {display_text}")

        return "\n".join(report)

    return f"Error: Unsupported action '{action}'."
