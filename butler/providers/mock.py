# -*- coding: utf-8 -*-

class MockProvider:
    def generate_plan(self, task: str):
        print("Intent:\nOrganize files\n")
        print("Plan:\n1 Scan\n2 Classify\n3 Move\n")
        print("Execution:\nSuccess")
        return {
            "steps": [
                "scan files",
                "classify files",
                "move files"
            ]
        }
