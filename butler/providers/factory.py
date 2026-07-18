# -*- coding: utf-8 -*-
import os
from butler.providers.mock import MockProvider
from butler.providers.openai import OpenAIProvider
from butler.providers.ollama import OllamaProvider

class ProviderFactory:
    @staticmethod
    def get():
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        if api_key:
            return OpenAIProvider(api_key)

        if os.getenv("USE_OLLAMA") or os.getenv("OLLAMA_API_KEY"):
            return OllamaProvider()

        return MockProvider()
