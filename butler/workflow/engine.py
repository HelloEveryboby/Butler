# -*- coding: utf-8 -*-
from butler.workflow.parser import WorkflowParser
from butler.core.runtime import ButlerRuntime

class WorkflowEngine:
    def __init__(self, runtime=None):
        self.runtime = runtime or ButlerRuntime()
        self.runtime.load_tools()

    def execute_workflow(self, yaml_str: str):
        data = WorkflowParser.parse_string(yaml_str)
        name = data.get("name", "Unnamed Workflow")
        steps = data.get("steps", [])

        print("Workflow Engine")

        results = {}
        for step in steps:
            step_name = step
            step_args = {}

            print("\n↓\n\nStep")
            print(f"Executing step: {step_name}")
            print("\n↓\n\nTool")
            print(f"Invoking tool for: {step_name}")

            if isinstance(step_name, str) and "." in step_name:
                tool_part, action_part = step_name.split(".", 1)
                tool = self.runtime.tools.get(tool_part)
                if tool:
                    res = tool.execute(action_part, **step_args)
                    print("\n↓\n\nResult")
                    print(f"Result: {res}")
                    results[step_name] = res
                else:
                    print("\n↓\n\nResult")
                    print(f"Result: Tool {tool_part} not found")
            else:
                print("\n↓\n\nResult")
                print(f"Result: Invalid step format {step_name}")
        return results
