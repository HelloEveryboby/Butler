# -*- coding: utf-8 -*-
from butler.core.runtime import ButlerRuntime

class Executor:
    def __init__(self, runtime=None):
        self.runtime = runtime or ButlerRuntime()
        self.runtime.load_tools()

    def execute(self, plan):
        results = []
        steps = plan.get("steps", [])
        for step in steps:
            results.append({"step": step, "status": "success"})
        return {"status": "success", "results": results}
