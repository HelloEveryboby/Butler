# butler/intent_dispatcher.py

import logging
from functools import wraps

from . import algorithms

logger = logging.getLogger(__name__)


class IntentRegistry:
    """用于动态发现和调度意图处理程序的注册表。"""

    def __init__(self):
        self._intents = {}
        self._llm_handlers: dict[str, dict] = {}
        self._local_handlers: dict[str, dict] = {}

    def register(self, intent_name: str, requires_entities: bool = True, source: str = "local"):
        """
        将函数注册为意图处理程序。

        参数:
            intent_name: 意图名称。
            requires_entities: 是否需要实体参数。
            source: "local" 或 "llm"。"llm" 表示由 LLM 返回 intent 名后分发。
        """
        def decorator(func):
            logger.info(f"Registering intent '{intent_name}' (source={source}) to function {func.__name__}")
            entry = {
                "function": func,
                "docstring": func.__doc__,
                "requires_entities": requires_entities,
                "source": source,
            }
            self._intents[intent_name] = entry
            if source == "llm":
                self._llm_handlers[intent_name] = entry
            else:
                self._local_handlers[intent_name] = entry

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    def dispatch(self, intent_name: str, **kwargs):
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

    def dispatch_by_llm_intent(self, intent_name: str, **kwargs):
        """
        专用分发入口：处理 LLM 返回的 intent 名。

        仅查找 source="llm" 注册的 handler。
        返回 (是否找到, 结果) 元组。
        """
        entry = self._llm_handlers.get(intent_name)
        if not entry:
            return False, None
        handler = entry["function"]
        try:
            result = handler(**kwargs)
            return True, result
        except Exception as e:
            logger.error(f"LLM intent '{intent_name}' 执行失败: {e}", exc_info=True)
            return True, {"error": str(e)}

    def get_all_intents(self):
        """返回所有已注册意图及其文档字符串的字典。"""
        return {name: data["docstring"] for name, data in self._intents.items()}

    def intent_requires_entities(self, intent_name: str) -> bool:
        """检查给定意图是否需要实体。"""
        return self._intents.get(intent_name, {}).get("requires_entities", True)

    def match_intent_locally(self, command: str, threshold: float = 0.7):
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
            logger.info(
                f"Local match found for '{command}': '{best_match}' "
                f"with similarity {highest_similarity:.2f}"
            )
            return best_match
        else:
            logger.info(
                f"No local match found for '{command}' above threshold {threshold}. "
                f"Highest similarity was {highest_similarity:.2f} for '{best_match}'."
            )
            return None


# A single, global instance of the registry
intent_registry = IntentRegistry()

# Make the decorator directly accessible
register_intent = intent_registry.register
