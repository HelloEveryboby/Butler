# butler/intent_dispatcher.py

import logging
from functools import wraps
from . import algorithms

logger = logging.getLogger(__name__)

class IntentRegistry:
    """用于动态发现和调度意图处理程序的注册表。"""
    def __init__(self):
        self._intents = {}

    def register(self, intent_name, requires_entities=True):
        """用于将函数注册为意图处理程序的装饰器。"""
        def decorator(func):
            logger.info(f"Registering intent '{intent_name}' to function {func.__name__}")
            self._intents[intent_name] = {
                "function": func,
                "docstring": func.__doc__,
                "requires_entities": requires_entities
            }
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def dispatch(self, intent_name, **kwargs):
        """
        将命令分发到适当的已注册处理程序。

        参数:
            intent_name (str): 要执行的意图名称。
            **kwargs: 传递给处理程序的参数字典。

        返回:
            处理程序函数的结果，如果未找到意图，则返回 None。
        """
        intent = self._intents.get(intent_name)
        if not intent:
            logger.warning(f"Intent '{intent_name}' not found in registry.")
            return None

        handler = intent["function"]
        try:
            return handler(**kwargs)
        except Exception as e:
            logger.error(f"Error executing intent '{intent_name}': {e}", exc_info=True)
            return None

    def get_all_intents(self):
        """返回所有已注册意图及其文档字符串的字典。"""
        return {name: data["docstring"] for name, data in self._intents.items()}

    def intent_requires_entities(self, intent_name):
        """检查给定意图是否需要实体。"""
        return self._intents.get(intent_name, {}).get("requires_entities", True)

    def match_intent_locally(self, command, threshold=0.7):
        """
        使用余弦相似度在本地查找最佳匹配意图。

        参数:
            command (str): 用户的命令。
            threshold (float): 视为匹配的最小相似度分数。

        返回:
            str: 最佳匹配意图的名称，如果未找到匹配，则返回 None。
        """
        intents = self.get_all_intents()
        if not intents:
            return None

        best_match = None
        highest_similarity = -1.0

        for intent_name, docstring in intents.items():
            if not docstring:
                continue

            similarity = algorithms.text_cosine_similarity(command, docstring)
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = intent_name

        if highest_similarity >= threshold:
            logger.info(f"Local match found for '{command}': '{best_match}' with similarity {highest_similarity:.2f}")
            return best_match
        else:
            logger.info(f"No local match found for '{command}' above threshold {threshold}. Highest similarity was {highest_similarity:.2f} for '{best_match}'.")
            return None

# A single, global instance of the registry
intent_registry = IntentRegistry()

# Make the decorator directly accessible
register_intent = intent_registry.register
