# -*- coding: utf-8 -*-
import os
import shutil
from butler.tools.base import Tool

class FileSystemTool(Tool):
    name = "filesystem"

    def execute(self, action, **kwargs):
        if action == "list":
            return self.list(kwargs.get("path", "."))
        elif action == "move":
            return self.move(kwargs.get("src"), kwargs.get("dst"))
        elif action == "read":
            return self.read(kwargs.get("path"))
        else:
            raise ValueError(f"Unknown action: {action}")

    def list(self, path):
        try:
            return os.listdir(path)
        except Exception as e:
            return str(e)

    def move(self, src, dst):
        try:
            shutil.move(src, dst)
            return True
        except Exception as e:
            return str(e)

    def read(self, path):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as e:
            return str(e)
