# -*- coding: utf-8 -*-

class Verifier:
    def check(self, result):
        if result.get("status") == "success":
            return True
        return False
