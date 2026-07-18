# -*- coding: utf-8 -*-
import yaml
from typing import Dict, Any, List, Optional

class WorkflowParser:
    """
    解析并验证轻量级 YAML 工作流定义文件。
    """
    @staticmethod
    def parse_string(yaml_str: str) -> Dict[str, Any]:
        try:
            data = yaml.safe_load(yaml_str)
            if not isinstance(data, dict):
                raise ValueError("工作流定义必须是合法的 YAML 对象键值对。")

            name = data.get("name")
            if not name:
                raise ValueError("工作流定义缺少必填的 'name' 字段。")

            trigger = data.get("trigger", "manual")
            steps = data.get("steps", [])

            if not isinstance(steps, list):
                raise ValueError("工作流的 'steps' 字段必须是步骤数组列表。")

            return {
                "name": name,
                "trigger": trigger,
                "steps": steps
            }
        except Exception as e:
            raise ValueError(f"解析 YAML 工作流配置失败: {e}")

    @classmethod
    def parse_file(cls, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r", encoding="utf-8") as f:
            return cls.parse_string(f.read())
