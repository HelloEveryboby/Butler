"""
Butler Android — Python 端桥接模块

由 Kotlin 通过 Chaquopy 调用。
提供 initialize() / call_plugin() / cleanup() 三个入口。
"""

import os
import sys
import json
import logging
import traceback

logger = logging.getLogger("ButlerAndroid")

# SkillManager 延迟初始化
_skill_manager = None
_initialized = False


def initialize(files_dir: str) -> None:
    """初始化 Butler 技能管理器"""
    global _skill_manager, _initialized

    if _initialized:
        logger.warning("Already initialized, skipping")
        return

    try:
        # 技能目录
        skills_path = os.path.join(files_dir, "skills")
        os.makedirs(skills_path, exist_ok=True)

        # 尝试导入 SkillManager
        try:
            from butler.core.skill_manager import SkillManager
            _skill_manager = SkillManager(skills_dir=skills_path)
            _skill_manager.load_skills()
            logger.info(f"SkillManager loaded with skills from {skills_path}")
        except ImportError:
            # Butler 核心模块不可用时，使用内置简化版
            _skill_manager = SimpleSkillManager(skills_path)
            logger.info("Using SimpleSkillManager (butler core not available)")

        _initialized = True

    except Exception as e:
        logger.error(f"Initialize failed: {e}")
        raise


def call_plugin(skill_id: str, action: str, params_json: str) -> str:
    """调用技能插件"""
    if not _initialized:
        return json.dumps({
            "status": "error",
            "error_type": "NotInitialized",
            "message": "Butler not initialized"
        })

    try:
        params = json.loads(params_json) if params_json else {}
        result = _skill_manager.execute(skill_id, action, **params)
        return json.dumps({
            "status": "success",
            "data": result
        })
    except Exception as e:
        tb = traceback.format_exc()
        return json.dumps({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "traceback": tb
        })


def cleanup() -> None:
    """清理资源"""
    global _skill_manager, _initialized
    if _skill_manager and hasattr(_skill_manager, 'stop_monitoring'):
        _skill_manager.stop_monitoring()
    _skill_manager = None
    _initialized = False


class SimpleSkillManager:
    """
    内置简化技能管理器
    当 butler 核心模块不可用时使用。
    提供基础的聊天和系统信息功能。
    """

    def __init__(self, skills_dir: str):
        self.skills_dir = skills_dir
        self.skills = {
            "chat": {"name": "聊天", "description": "AI 对话", "enabled": True},
            "system": {"name": "系统", "description": "系统信息", "enabled": True},
            "file": {"name": "文件", "description": "文件管理", "enabled": True},
        }

    def load_skills(self):
        """扫描技能目录"""
        if not os.path.exists(self.skills_dir):
            return
        for name in os.listdir(self.skills_dir):
            skill_path = os.path.join(self.skills_dir, name)
            if os.path.isdir(skill_path):
                self.skills[name] = {
                    "name": name,
                    "description": f"技能: {name}",
                    "enabled": True,
                    "path": skill_path
                }

    def execute(self, skill_id: str, action: str, **params) -> dict:
        """执行技能"""
        if skill_id == "skill_manager" and action == "list":
            return {
                "skills": [
                    {"id": sid, **info}
                    for sid, info in self.skills.items()
                ]
            }

        if skill_id == "chat":
            return self._handle_chat(action, params)

        if skill_id == "system":
            return self._handle_system(action, params)

        return {"error": f"Unknown skill: {skill_id}"}

    def _handle_chat(self, action: str, params: dict) -> dict:
        """处理聊天请求"""
        message = params.get("message", "")

        if action == "process":
            # 简单的本地响应 (无 LLM 时)
            responses = {
                "/help": "可用命令:\n/help - 帮助\n/status - 系统状态\n/skills - 技能列表",
                "/status": f"✅ Butler Android 运行中\nPython: {sys.version}",
                "/skills": "技能: " + ", ".join(self.skills.keys()),
            }

            if message in responses:
                return {"response": responses[message]}

            # 默认回复
            return {
                "response": f"收到: {message}\n\n💡 配置远程服务器后可使用完整 AI 功能。"
            }

        return {"error": f"Unknown chat action: {action}"}

    def _handle_system(self, action: str, params: dict) -> dict:
        """系统信息"""
        if action == "info":
            return {
                "platform": sys.platform,
                "python_version": sys.version,
                "prefix": sys.prefix,
                "skills_count": len(self.skills)
            }
        return {"error": f"Unknown system action: {action}"}
