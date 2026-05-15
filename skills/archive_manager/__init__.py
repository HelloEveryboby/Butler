import os
import zipfile
import hashlib

def get_file_hash(filepath):
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    zip_path = entities.get("zip_path") or kwargs.get("zip_path")
    file_in_zip = entities.get("file_in_zip") or kwargs.get("file_in_zip")

    if action == "list_zip_contents" or "列出" in action:
        if not zip_path: return "提供压缩包路径。"
        with zipfile.ZipFile(zip_path, 'r') as z:
            return "\n".join(z.namelist())

    elif action == "open_zip_file" or "打开" in action:
        # 简化版：仅解压并返回路径
        if not zip_path or not file_in_zip: return "路径缺失。"
        with zipfile.ZipFile(zip_path, 'r') as z:
            z.extract(file_in_zip, "temp_archive")
            return f"已解压到: temp_archive/{file_in_zip}"

    return "压缩管理就绪。"
