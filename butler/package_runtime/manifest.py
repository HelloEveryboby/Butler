# -*- coding: utf-8 -*-
import json
from typing import List, Dict, Any, Optional

class PackageManifest:
    """
    解析并验证 Butler v2.0 Alpha 的包配置信息清单 (manifest.json)。
    """
    def __init__(self, name: str, version: str, type: str, permissions: List[str], entry: str, dependencies: Dict[str, str]):
        self.name = name
        self.version = version
        self.type = type # 例如: "agent"（数字员工）, "skill"（技能扩展）, "tool"（外部工具）
        self.permissions = permissions or []
        self.entry = entry or "main.py"
        self.dependencies = dependencies or {}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageManifest":
        name = data.get("name")
        if not name:
            raise ValueError("清单配置错误: 'name' 字段是必填项。")

        version = data.get("version", "1.0.0")
        pkg_type = data.get("type", "skill") # 默认为技能
        permissions = data.get("permissions", [])
        entry = data.get("entry", "main.py")
        dependencies = data.get("dependencies", {})

        return cls(name, version, pkg_type, permissions, entry, dependencies)

    @classmethod
    def from_json(cls, json_str: str) -> "PackageManifest":
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "type": self.type,
            "permissions": self.permissions,
            "entry": self.entry,
            "dependencies": self.dependencies
        }
