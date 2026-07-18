# -*- coding: utf-8 -*-
import os

class OpenAIProvider:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    def generate_plan(self, task: str):
        if not self.api_key:
            raise ValueError("OpenAI API key missing")
        return {
            "steps": [
                f"openai: scan {task}",
                f"openai: process {task}",
                f"openai: report {task}"
            ]
        }
