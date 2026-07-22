"""
Butler Cloud Hub — 本地集成版

直接嵌入 Butler 主程序，通过 ButlerBridge 调用。
不启动 HTTP 服务，不依赖浏览器。
"""

import os
import json
import logging
import asyncio
from pathlib import Path

from .drivers.base import StorageConfig, StorageType
from .drivers.hub import CloudHub

logger = logging.getLogger("Butler.CloudHub")


class LocalCloudHub:
    """
    本地 CloudHub — 集成到 Butler

    通过 Butler 的 ModernBridge 暴露给前端:
        ModernBridge.cloud_list_storages()
        ModernBridge.cloud_list_files(storage, path)
        ModernBridge.cloud_search(keyword)
        ModernBridge.cloud_transfer(src, dst)
    """

    def __init__(self, config_dir: str = None):
        self.config_dir = Path(config_dir or os.path.expanduser("~/.butler"))
        self.config_file = self.config_dir / "cloud.json"
        self.hub = CloudHub()
        self._loop = None

    @property
    def loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop

    def init(self):
        """初始化: 加载配置, 连接存储"""
        self._load_config()
        logger.info(f"CloudHub initialized, {len(self.hub.drivers)} storages loaded")

    def _load_config(self):
        if not self.config_file.exists():
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                configs = json.load(f)
            for cfg in configs:
                if not cfg.get("enabled", True):
                    continue
                config = StorageConfig(
                    name=cfg["name"],
                    type=StorageType(cfg["type"]),
                    config=cfg.get("config", {}),
                    enabled=True,
                    read_only=cfg.get("read_only", False),
                )
                try:
                    self.loop.run_until_complete(self.hub.add_storage(config))
                    logger.info(f"Loaded storage: {config.name}")
                except Exception as e:
                    logger.warning(f"Skip storage {config.name}: {e}")
        except Exception as e:
            logger.error(f"Load config failed: {e}")

    def _save_config(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
        configs = []
        for d in self.hub.drivers.values():
            configs.append({
                "name": d.name,
                "type": d.type.value,
                "config": d.config.config,
                "enabled": d.config.enabled,
                "read_only": d.config.read_only,
            })
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(configs, f, ensure_ascii=False, indent=2)

    # === 供 ModernBridge 调用的方法 ===

    def list_storages(self) -> str:
        """JSON: 列出所有存储"""
        return json.dumps(self.hub.list_storages(), ensure_ascii=False)

    def list_files(self, storage: str, path: str = "/") -> str:
        """JSON: 列出文件"""
        try:
            files = self.loop.run_until_complete(self.hub.list_files(storage, path))
            return json.dumps({"status": "ok", "files": files}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def get_file(self, storage: str, path: str) -> str:
        """JSON: 获取文件信息"""
        try:
            driver = self.hub._get_driver(storage)
            item = self.loop.run_until_complete(driver.stat(path))
            return json.dumps({"status": "ok", "file": item.to_dict()}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def search(self, keyword: str, storage: str = None) -> str:
        """JSON: 搜索文件"""
        try:
            if storage:
                results = self.loop.run_until_complete(self.hub.search(storage, keyword))
            else:
                results = self.loop.run_until_complete(self.hub.global_search(keyword))
            return json.dumps({"status": "ok", "results": results}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def add_storage(self, name: str, storage_type: str, config: dict) -> str:
        """JSON: 添加存储"""
        try:
            cfg = StorageConfig(
                name=name,
                type=StorageType(storage_type),
                config=config,
            )
            self.loop.run_until_complete(self.hub.add_storage(cfg))
            self._save_config()
            return json.dumps({"status": "ok", "name": name})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def remove_storage(self, name: str) -> str:
        """JSON: 移除存储"""
        try:
            self.loop.run_until_complete(self.hub.remove_storage(name))
            self._save_config()
            return json.dumps({"status": "ok"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def transfer(self, src_storage: str, src_path: str, dst_storage: str, dst_path: str) -> str:
        """JSON: 跨盘传输"""
        try:
            result = self.loop.run_until_complete(
                self.hub.transfer(src_storage, src_path, dst_storage, dst_path)
            )
            return json.dumps({"status": "ok", "file": result}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def cleanup(self):
        """清理资源"""
        for driver in self.hub.drivers.values():
            try:
                self.loop.run_until_complete(driver.disconnect())
            except Exception:
                pass
        if self._loop and not self._loop.is_closed():
            self._loop.close()
