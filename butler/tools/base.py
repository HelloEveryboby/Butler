# -*- coding: utf-8 -*-

class Tool:
    name = ""

    def execute(self, action, **kwargs):
        raise NotImplementedError
