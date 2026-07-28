# butler/intent_dispatcher.py

import logging
import time
import concurrent.futures
from collections import defaultdict, deque
from functools import wraps

from . import algorithms

logger = logging.getLogger(__name__)

# ── 弹性层常量 ──────────────────────────────────────────────
_DEFAULT_TIMEOUT = 5            # 单次意图执行超时（秒）
_CB_FAILURE_THRESHOLD = 5       # 连续失败多少次后触发熔断
_CB_RECOVERY_SECONDS = 30       # 熔断后多少秒尝试半开恢复
_RATE_LIMIT_WINDOW = 60         # 速率限制窗口（秒）
_RATE_LIMIT_MAX_CALLS = 60     # 每窗口最大调用次数


class IntentRegistry:
    """用于动态发现和调度意图处理程序的注册表，内置弹性层。"""

    def __init__(self):
        self._intents = {}
        self._llm_handlers: dict[str, dict] = {}
        self._local_handlers: dict[str, dict] = {}
        # 弹性层状态
        self._circuit_breakers: dict[str, bool] = {}
        self._failure_counts: dict[str, int] = defaultdict(int)
        self._breaker_opened_at: dict[str, float] = {}
        self._metrics: dict[str, dict] = defaultdict(lambda: {"success": 0, "failure": 0, "timeout": 0, "total_ms": 0})
        self._rate_limit_window: dict[str, deque] = defaultdict(deque)

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

        内置弹性层：速率限制 → 熔断器检查 → 超时控制 → 指标采集。
        返回 (是否找到, 结果) 元组。
        """
        entry = self._llm_handlers.get(intent_name)
        if not entry:
            return False, None

        # 1. 速率限制检查
        now = time.time()
        window = self._rate_limit_window[intent_name]
        while window and now - window[0] > _RATE_LIMIT_WINDOW:
            window.popleft()
        if len(window) >= _RATE_LIMIT_MAX_CALLS:
            logger.warning(f"Intent '{intent_name}' 触发速率限制（{_RATE_LIMIT_MAX_CALLS}/{_RATE_LIMIT_WINDOW}s）")
            return True, {"error": "请求过于频繁，请稍后再试"}
        window.append(now)

        # 2. 熔断器检查
        if self._is_circuit_open(intent_name):
            logger.warning(f"Intent '{intent_name}' 熔断器开启，拒绝调用")
            return True, {"error": "服务暂时不可用，请稍后再试"}

        handler = entry["function"]
        start = time.time()
        try:
            # 3. 超时控制
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(handler, **kwargs)
                result = future.result(timeout=_DEFAULT_TIMEOUT)

            # 4. 成功：重置失败计数 + 更新指标
            self._failure_counts[intent_name] = 0
            elapsed = (time.time() - start) * 1000
            self._metrics[intent_name]["success"] += 1
            self._metrics[intent_name]["total_ms"] += elapsed
            return True, result

        except concurrent.futures.TimeoutError:
            logger.error(f"LLM intent '{intent_name}' 执行超时（{_DEFAULT_TIMEOUT}s）")
            self._handle_failure(intent_name, "timeout")
            return True, {"error": "操作超时，请稍后再试"}

        except Exception as e:
            logger.error(f"LLM intent '{intent_name}' 执行失败: {e}", exc_info=True)
            self._handle_failure(intent_name, "failure")
            return True, {"error": str(e)}

    def _is_circuit_open(self, intent_name: str) -> bool:
        """检查熔断器是否处于开启状态，半开状态下自动尝试恢复。"""
        if not self._circuit_breakers.get(intent_name, False):
            return False
        opened_at = self._breaker_opened_at.get(intent_name, 0)
        if time.time() - opened_at >= _CB_RECOVERY_SECONDS:
            # 半开：允许一次试探调用
            logger.info(f"Intent '{intent_name}' 熔断器进入半开状态，尝试恢复")
            self._circuit_breakers[intent_name] = False
            return False
        return True

    def _handle_failure(self, intent_name: str, failure_type: str = "failure") -> None:
        """记录失败，连续达到阈值时触发熔断器。"""
        self._metrics[intent_name][failure_type] += 1
        self._failure_counts[intent_name] += 1
        if self._failure_counts[intent_name] >= _CB_FAILURE_THRESHOLD:
            self._circuit_breakers[intent_name] = True
            self._breaker_opened_at[intent_name] = time.time()
            logger.warning(
                f"Intent '{intent_name}' 连续失败 {self._failure_counts[intent_name]} 次，"
                f"熔断器已开启（{_CB_RECOVERY_SECONDS}s 后尝试恢复）"
            )

    def get_metrics(self) -> dict[str, dict]:
        """返回所有意图的执行指标快照。"""
        return dict(self._metrics)

    def reset_circuit_breaker(self, intent_name: str | None = None) -> None:
        """手动重置熔断器（全部或指定意图）。"""
        if intent_name:
            self._circuit_breakers.pop(intent_name, None)
            self._failure_counts[intent_name] = 0
            logger.info(f"Intent '{intent_name}' 熔断器已手动重置")
        else:
            self._circuit_breakers.clear()
            self._failure_counts.clear()
            logger.info("所有熔断器已手动重置")

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
