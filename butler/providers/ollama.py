# -*- coding: utf-8 -*-
import os

class OllamaProvider:
    def __init__(self, host=None):
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def generate_plan(self, task: str):
        return {
            "steps": [
                f"ollama: scan {task}",
                f"ollama: process {task}",
                f"ollama: report {task}"
            ]
        }
