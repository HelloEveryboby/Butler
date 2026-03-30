import importlib
import json
import os
import logging
import sys
from pathlib import Path

logger = logging.getLogger("SkillManager")


class SkillManager:
    def __init__(self, skills_dir="skills", lock_file="skills-lock.json"):
        self.skills_dir = skills_dir
        self.lock_file = lock_file
        self.loaded_skills = {}  # 格式: { "skill_id": handle_func }
        self.manifests = {}  # 格式: { "skill_id": manifest_dict }

        # Ensure project root is in sys.path
        project_root = str(Path(__file__).resolve().parent.parent.parent)
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

    def load_skills(self):
        """扫描并加载 skills-lock.json 中启用的所有技能"""
        if not os.path.exists(self.lock_file):
            logger.warning(f"Lock file {self.lock_file} not found.")
            return

        try:
            with open(self.lock_file, "r", encoding="utf-8") as f:
                enabled_skills = json.load(f).get("enabled_skills", [])
        except Exception as e:
            logger.error(f"Failed to read {self.lock_file}: {e}")
            return

        for skill_id in enabled_skills:
            try:
                # 动态导入模块
                # Python imports usually expect dot notation from a root package
                # Since skills/ is in the root, we can use "skills.skill_id"
                module_name = f"skills.{skill_id}"
                module = importlib.import_module(module_name)

                # 加载元数据
                m_path = os.path.join(self.skills_dir, skill_id, "manifest.json")
                if os.path.exists(m_path):
                    with open(m_path, "r", encoding="utf-8") as mf:
                        self.manifests[skill_id] = json.load(mf)

                # 注册入口
                if hasattr(module, "handle_request"):
                    self.loaded_skills[skill_id] = module.handle_request
                    logger.info(f"Loaded skill: {skill_id}")
                else:
                    logger.error(f"技能 {skill_id} 缺失 handle_request 函数")
            except Exception as e:
                logger.error(f"加载技能 {skill_id} 失败: {e}")

    def execute(self, skill_id, action, **kwargs):
        """统一调用接口"""
        if skill_id in self.loaded_skills:
            return self.loaded_skills[skill_id](action, **kwargs)
        return f"Error: 技能 {skill_id} 未找到"

    def match_skill(self, command):
        """
        Simple keyword matching based on manifest descriptions and names.
        This can be improved with NLU.
        """
        for skill_id, manifest in self.manifests.items():
            if manifest.get("name") in command or any(
                keyword in command for keyword in manifest.get("keywords", [])
            ):
                return skill_id
        return None
