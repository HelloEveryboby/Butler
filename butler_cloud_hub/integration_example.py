"""
ModernBridge 集成示例

在 butler/frontend/program/modern_app.py 的 ModernBridge 类中添加以下方法。
前端通过 window.pywebview.api.cloud_xxx() 调用。
"""

# === 在 ModernBridge.__init__ 中添加 ===
#
# from butler_cloud_hub.local_hub import LocalCloudHub
# self.cloud_hub = LocalCloudHub(config_dir=os.path.join(project_root, "data", "cloud"))
# self.cloud_hub.init()

# === 在 ModernBridge 类中添加以下方法 ===

def cloud_list_storages(self):
    """列出所有已配置的云存储"""
    return self.cloud_hub.list_storages()

def cloud_list_files(self, storage, path="/"):
    """列出指定存储的文件"""
    return self.cloud_hub.list_files(storage, path)

def cloud_search(self, keyword, storage=None):
    """搜索文件 (指定存储或全局)"""
    return self.cloud_hub.search(keyword, storage)

def cloud_add_storage(self, name, storage_type, config_json):
    """添加新的云存储"""
    import json
    config = json.loads(config_json) if isinstance(config_json, str) else config_json
    return self.cloud_hub.add_storage(name, storage_type, config)

def cloud_remove_storage(self, name):
    """移除云存储"""
    return self.cloud_hub.remove_storage(name)

def cloud_transfer(self, src_storage, src_path, dst_storage, dst_path):
    """跨盘传输文件"""
    return self.cloud_hub.transfer(src_storage, src_path, dst_storage, dst_path)
