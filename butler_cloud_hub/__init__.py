"""
Butler Cloud Hub — 本地模块入口

直接导入使用，不启动 HTTP 服务。
集成到 Butler 主程序中。

用法:
    from butler_cloud_hub import CloudHub, StorageConfig, StorageType

    hub = CloudHub(config_dir="~/.butler/cloud")
    await hub.add_storage(StorageConfig(...))
    files = await hub.list_files("我的阿里云盘", "/")
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from .drivers.base import StorageDriver, StorageConfig, FileItem, StorageType
from .drivers.hub import CloudHub

__all__ = ["CloudHub", "StorageConfig", "StorageType", "FileItem", "StorageDriver"]
__version__ = "1.0.0"


class ButlerCloudHub(CloudHub):
    """
    Butler 集成版 CloudHub

    - 自动从本地配置文件加载存储
    - 配置保存在 ~/.butler/cloud.json
    - 提供同步/异步双接口供 Butler 调用
    """

    def __init__(self, config_dir: str = None):
        super().__init__()
        self.config_dir = Path(config_dir or os.path.expanduser("~/.butler"))
        self.config_file = self.config_dir / "cloud.json"
        self._auto_load()

    def _auto_load(self):
        """自动加载已保存的存储配置"""
        if not self.config_file.exists():
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                configs = json.load(f)
            for cfg in configs:
                config = StorageConfig(
                    name=cfg["name"],
                    type=StorageType(cfg["type"]),
                    config=cfg.get("config", {}),
                    enabled=cfg.get("enabled", True),
                    read_only=cfg.get("read_only", False),
                )
                if config.enabled:
                    try:
                        asyncio.get_event_loop().run_until_complete(self.add_storage(config))
                    except Exception as e:
                        logging.getLogger("CloudHub").warning(f"Skip {config.name}: {e}")
        except Exception as e:
            logging.getLogger("CloudHub").error(f"Load config failed: {e}")

    def _save_config(self):
        """保存当前存储配置到本地文件"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        configs = []
        for d in self.drivers.values():
            configs.append({
                "name": d.name,
                "type": d.type.value,
                "config": d.config.config,
                "enabled": d.config.enabled,
                "read_only": d.config.read_only,
            })
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(configs, f, ensure_ascii=False, indent=2)

    async def add_storage(self, config: StorageConfig) -> str:
        """添加存储并自动保存配置"""
        name = await super().add_storage(config)
        self._save_config()
        return name

    async def remove_storage(self, name: str) -> None:
        """移除存储并自动保存配置"""
        await super().remove_storage(name)
        self._save_config()

    # === Butler 技能系统集成接口 ===

    def handle_action(self, action: str, **params) -> dict:
        """
        Butler 技能系统调用入口 (同步)

        action:
            list_storages   - 列出所有存储
            list_files      - 列出文件
            search          - 搜索文件
            transfer        - 跨盘传输
            add_storage     - 添加存储
            remove_storage  - 移除存储
        """
        loop = asyncio.new_event_loop()
        try:
            if action == "list_storages":
                return {"storages": self.list_storages()}

            elif action == "list_files":
                files = loop.run_until_complete(
                    self.list_files(params["storage"], params.get("path", "/"))
                )
                return {"files": files}

            elif action == "search":
                if "storage" in params:
                    results = loop.run_until_complete(
                        self.search(params["storage"], params["keyword"], params.get("path", "/"))
                    )
                else:
                    results = loop.run_until_complete(
                        self.global_search(params["keyword"])
                    )
                return {"results": results}

            elif action == "transfer":
                result = loop.run_until_complete(
                    self.transfer(
                        params["src_storage"], params["src_path"],
                        params["dst_storage"], params["dst_path"],
                    )
                )
                return {"file": result}

            elif action == "add_storage":
                config = StorageConfig(
                    name=params["name"],
                    type=StorageType(params["type"]),
                    config=params.get("config", {}),
                )
                name = loop.run_until_complete(self.add_storage(config))
                return {"name": name}

            elif action == "remove_storage":
                loop.run_until_complete(self.remove_storage(params["name"]))
                return {"status": "ok"}

            else:
                return {"error": f"Unknown action: {action}"}

        except Exception as e:
            return {"error": str(e)}
        finally:
            loop.close()
