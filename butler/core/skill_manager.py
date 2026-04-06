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
        self.manifests = {}      # 格式: { "skill_id": manifest_dict }

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
            with open(self.lock_file, 'r', encoding='utf-8') as f:
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
                    with open(m_path, 'r', encoding='utf-8') as mf:
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
        # 特殊处理系统自带的技能管理动作 (匹配 manage_skills 意图)
        if skill_id == "manage_skills" or skill_id == "skill_manager":
            return self._manage_skills(action, **kwargs)

        if skill_id in self.loaded_skills:
            return self.loaded_skills[skill_id](action, **kwargs)
        return f"Error: 技能 {skill_id} 未找到"

    def _manage_skills(self, action, **kwargs):
        """处理技能管理相关的内部逻辑 (install, uninstall, list, update)"""
        import subprocess
        import shutil
        import sys
        from urllib.parse import urlparse

        entities = kwargs.get("entities", {})
        url = entities.get("url") or kwargs.get("url")
        skill_name = entities.get("skill_name") or kwargs.get("skill_name")

        if action == "install":
            if not url: return "错误：缺少技能下载链接 (URL)。"

            # 健壮地提取技能名
            parsed_url = urlparse(url.rstrip('/'))
            suggested_name = skill_name or os.path.basename(parsed_url.path).replace(".git", "")

            if not suggested_name:
                return "错误：无法从 URL 提取有效的技能名称，请手动提供 skill_name 参数。"

            target_path = os.path.join(self.skills_dir, suggested_name)

            if os.path.exists(target_path):
                return f"错误：技能 '{suggested_name}' 已存在。请先卸载或更换名称。"

            logger.info(f"正在从 {url} 安装技能 '{suggested_name}'...")
            try:
                # 使用 git clone 下载
                clone_res = subprocess.run(["git", "clone", "--depth", "1", url, target_path], capture_output=True, text=True)
                if clone_res.returncode != 0:
                    raise Exception(f"Git Clone 失败: {clone_res.stderr}")

                # 检查并安装依赖
                req_path = os.path.join(target_path, "requirements.txt")
                if os.path.exists(req_path):
                    logger.info(f"正在安装技能 '{suggested_name}' 的依赖...")
                    pip_res = subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_path], capture_output=True, text=True)
                    if pip_res.returncode != 0:
                        logger.error(f"依赖安装失败: {pip_res.stderr}")
                        # 依赖安装失败通常不回滚安装，但通知用户

                # 自动开启该技能
                self._update_lock_file(suggested_name, enable=True)
                # 重新加载
                self.load_skills()

                return f"✅ 技能 '{suggested_name}' 安装成功并已启用！"
            except Exception as e:
                # 只有当 target_path 指向子目录时才进行删除，防止误删根目录
                if suggested_name and os.path.exists(target_path) and os.path.isdir(target_path):
                    shutil.rmtree(target_path)
                return f"❌ 安装失败: {str(e)}"

        elif action == "uninstall":
            if not skill_name: return "错误：请提供要卸载的技能名称。"
            target_path = os.path.join(self.skills_dir, skill_name)

            if not os.path.exists(target_path):
                return f"错误：技能 '{skill_name}' 未安装。"

            try:
                shutil.rmtree(target_path)
                self._update_lock_file(skill_name, enable=False)
                if skill_name in self.loaded_skills: del self.loaded_skills[skill_name]
                if skill_name in self.manifests: del self.manifests[skill_name]
                return f"✅ 技能 '{skill_name}' 已成功卸载。"
            except Exception as e:
                return f"❌ 卸载失败: {str(e)}"

        elif action == "list":
            enabled = []
            if os.path.exists(self.lock_file):
                with open(self.lock_file, 'r', encoding='utf-8') as f:
                    enabled = json.load(f).get("enabled_skills", [])

            installed = [d for d in os.listdir(self.skills_dir) if os.path.isdir(os.path.join(self.skills_dir, d))]

            report = ["### 已安装技能列表："]
            for s in installed:
                status = "🟢 已启用" if s in enabled else "⚪ 已禁用"
                desc = self.manifests.get(s, {}).get("description", "无描述")
                report.append(f"- **{s}**: {desc} ({status})")

            return "\n".join(report)

        return f"错误：技能管理器不支持动作 '{action}'。"

    def _update_lock_file(self, skill_id, enable=True):
        """更新 skills-lock.json"""
        data = {"enabled_skills": []}
        if os.path.exists(self.lock_file):
            with open(self.lock_file, 'r', encoding='utf-8') as f:
                try: data = json.load(f)
                except: pass

        enabled = data.get("enabled_skills", [])
        if enable and skill_id not in enabled:
            enabled.append(skill_id)
        elif not enable and skill_id in enabled:
            enabled.remove(skill_id)

        data["enabled_skills"] = enabled
        with open(self.lock_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def match_skill(self, command):
        """
        Simple keyword matching based on manifest descriptions and names.
        This can be improved with NLU.
        """
        for skill_id, manifest in self.manifests.items():
            if manifest.get("name") in command or any(keyword in command for keyword in manifest.get("keywords", [])):
                return skill_id
        return None
