# -*- coding: utf-8 -*-
import subprocess
from butler.tools.base import Tool

class ShellTool(Tool):
    name = "shell"

    def execute(self, action, **kwargs):
        command = kwargs.get("command") or action
        try:
            res = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            return {
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr
            }
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}
