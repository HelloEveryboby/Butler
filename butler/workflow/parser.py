# -*- coding: utf-8 -*-
import yaml

class WorkflowParser:
    @staticmethod
    def parse_string(yaml_str: str):
        return yaml.safe_load(yaml_str)

    @classmethod
    def parse_file(cls, file_path: str):
        with open(file_path, "r", encoding="utf-8") as f:
            return cls.parse_string(f.read())
