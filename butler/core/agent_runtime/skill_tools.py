# -*- coding: utf-8 -*-
"""技能工具适配器 — 把 Butler 的 One Folder = One Skill 技能暴露给 LLM。

背景
----
``SkillManager.export_openai_tools()`` 早就能把技能导出成 OpenAI 函数定义，
但只被单测使用；真正跑聊天的主循环走的是「意图分类 + 字典派发」，
LLM 无法自主选择技能，也无法在一次任务里连续调用多个工具。

本模块把技能注册进 ``ToolRegistry``，让 ``AgentRuntime`` 的原生
tool calling 循环可以直接调用技能：

    registry = ToolRegistry()
    register_builtin_tools(registry)
    register_skill_tools(registry, skill_manager, butler_app=butler)

约定
----
* 技能名会做 OpenAI 函数名清洗（只保留 ``[A-Za-z0-9_-]``），
  返回值 ``{tool_name: skill_id}`` 用于反查。
* LLM 传入的参数里 ``action`` 表示要执行的动作，其余键作为 kwargs 透传；
  同时把整包参数作为 ``entities`` 传下去，兼容旧式 ``handle_request(action, entities=...)``。
* 只注册「可执行」技能（有 Python/二进制入口），纯 SKILL.md 指令型技能
  仍通过系统提示词注入，不占用工具位。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from .tool_registry import ToolRegistry
from .types import PermissionLevel

logger = logging.getLogger(__name__)

# 工具结果进入上下文前截断，避免一次技能输出吃爆窗口
_MAX_RESULT_CHARS = 12000
# 技能名清洗后允许的最大长度（OpenAI 函数名上限 64）
_MAX_NAME_CHARS = 64

_SAFE_NAME_RE = re.compile(r"[^0-9A-Za-z_-]")


def _sanitize_tool_name(raw: str) -> str:
    """把技能 id 清洗成合法的 OpenAI 函数名。"""
    safe = _SAFE_NAME_RE.sub("_", str(raw or "")).strip("_")
    if not safe:
        safe = "skill"
    if safe[0].isdigit():
        safe = f"skill_{safe}"
    return safe[:_MAX_NAME_CHARS]


def is_executable_skill(skill_manager: Any, skill_id: str, manifest: Dict[str, Any]) -> bool:
    """技能是否有可执行入口（纯指令型技能不注册为工具）。"""
    if manifest.get("has_python") or manifest.get("has_binary"):
        return True
    return skill_id in getattr(skill_manager, "loaded_skills", {})


def _normalize_result(skill_id: str, result: Any) -> Dict[str, Any]:
    """把技能千奇百怪的返回值收敛成 ToolResult 认识的字典。"""
    if isinstance(result, dict):
        status = str(result.get("status") or "").lower()

        if status in ("pending_confirmation", "pending_resource"):
            message = result.get("message") or result.get("error") or "该技能需要用户确认后才能继续。"
            return {
                "success": True,
                "content": str(message)[:_MAX_RESULT_CHARS],
                "metadata": {"pending": True, "skill": skill_id, "status": status},
            }

        if status in ("failed", "error") or result.get("success") is False:
            detail = result.get("error") or result.get("message") or json.dumps(
                result, ensure_ascii=False
            )
            return {
                "success": False,
                "error": str(detail)[:_MAX_RESULT_CHARS],
                "metadata": {"skill": skill_id},
            }

        for key in ("content", "result", "output", "report", "message"):
            if result.get(key) is not None:
                value = result[key]
                text = value if isinstance(value, str) else json.dumps(
                    value, ensure_ascii=False, default=str
                )
                return {
                    "success": True,
                    "content": text[:_MAX_RESULT_CHARS],
                    "metadata": {"skill": skill_id},
                }

        return {
            "success": True,
            "content": json.dumps(result, ensure_ascii=False, default=str)[:_MAX_RESULT_CHARS],
            "metadata": {"skill": skill_id},
        }

    text = "" if result is None else str(result)
    failed = (
        text.startswith("Error:")
        or text.startswith("⚠️")
        or "技能执行出错" in text
        or text.startswith("技能 '") and "无法执行" in text
    )
    if failed:
        return {"success": False, "error": text[:_MAX_RESULT_CHARS], "metadata": {"skill": skill_id}}
    return {"success": True, "content": text[:_MAX_RESULT_CHARS], "metadata": {"skill": skill_id}}


def _make_handler(skill_id: str, skill_manager: Any, butler_app: Any):
    """生成一个绑定到具体技能的 ToolExecutor handler。"""

    def handler(arguments: Dict[str, Any], **context: Any) -> Dict[str, Any]:
        args = dict(arguments or {})
        action = args.pop("action", None) or "run"
        nested = args.pop("kwargs", None)
        if isinstance(nested, dict):
            # 兼容默认 schema 里的 {"action", "kwargs"} 形式
            args.update(nested)
        args.pop("butler_app", None)

        call_kwargs: Dict[str, Any] = dict(args)
        call_kwargs.setdefault("entities", dict(args))
        # 交互式 AI 调用不等同于后台批处理：跳过 DRAS 负载排队，避免用户请求被静默挂起
        call_kwargs.setdefault("force_execute", True)
        call_kwargs["butler_app"] = butler_app

        try:
            result = skill_manager.execute(str(skill_id), str(action), **call_kwargs)
        except TypeError as exc:
            # 少数技能入口不接受额外 kwargs，退化为只传 action
            logger.debug("skill %s rejected extra kwargs (%s), retrying bare", skill_id, exc)
            try:
                result = skill_manager.execute(str(skill_id), str(action))
            except Exception as inner:
                logger.error("skill %s failed: %s", skill_id, inner, exc_info=True)
                return {"success": False, "error": f"技能 {skill_id} 执行异常: {inner}"}
        except Exception as exc:
            logger.error("skill %s failed: %s", skill_id, exc, exc_info=True)
            return {"success": False, "error": f"技能 {skill_id} 执行异常: {exc}"}

        return _normalize_result(skill_id, result)

    return handler


def register_skill_tools(
    registry: ToolRegistry,
    skill_manager: Any,
    butler_app: Any = None,
    permission_level: PermissionLevel = PermissionLevel.REQUIRE_CONFIRM,
    max_tools: Optional[int] = None,
) -> Dict[str, str]:
    """把技能注册进工具表。

    参数
    ----
    registry: 目标工具注册表
    skill_manager: ``SkillManager`` 实例（需已 ``load_skills()``）
    butler_app: 传给技能的宿主对象（可选）
    permission_level: 技能工具的默认权限层级
    max_tools: 可选的注册上限（按名称排序截断），用于控制工具表规模

    返回
    ----
    ``{tool_name: skill_id}`` 映射。
    """
    if skill_manager is None or not getattr(skill_manager, "manifests", None):
        logger.warning("register_skill_tools: no skill manager / no skills loaded")
        return {}

    try:
        schemas = skill_manager.export_openai_tools()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("export_openai_tools failed: %s", exc)
        return {}

    mapping: Dict[str, str] = {}
    used_names: set[str] = set()

    for entry in sorted(schemas, key=lambda e: e.get("function", {}).get("name", "")):
        if max_tools is not None and len(mapping) >= max_tools:
            break

        function = entry.get("function") or {}
        skill_id = function.get("name")
        if not skill_id:
            continue

        manifest = skill_manager.manifests.get(skill_id, {})
        if not is_executable_skill(skill_manager, skill_id, manifest):
            continue

        tool_name = _sanitize_tool_name(skill_id)
        if tool_name in used_names or registry.get(tool_name):
            suffix = 2
            while f"{tool_name}_{suffix}" in used_names or registry.get(f"{tool_name}_{suffix}"):
                suffix += 1
            tool_name = f"{tool_name}_{suffix}"[:_MAX_NAME_CHARS]
        used_names.add(tool_name)

        description = function.get("description") or f"Butler skill: {skill_id}"
        parameters = function.get("parameters") or {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "要执行的动作，缺省为 run"},
            },
        }

        registry.register(
            handler=_make_handler(skill_id, skill_manager, butler_app),
            name=tool_name,
            description=description,
            parameters=parameters,
            permission_level=permission_level,
            is_read_only=False,
            is_destructive=bool(manifest.get("risk") in ("high", "critical")),
        )
        mapping[tool_name] = skill_id

    logger.info("Registered %d skill tools", len(mapping))
    return mapping
