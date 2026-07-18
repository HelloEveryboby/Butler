# -*- coding: utf-8 -*-
from butler.providers.factory import ProviderFactory

class Planner:
    def __init__(self, provider=None):
        self.provider = provider or ProviderFactory.get()

    def create(self, task: str):
        return self.provider.generate_plan(task)
