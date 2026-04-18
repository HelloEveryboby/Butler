import importlib
import importlib.util
import json
import os
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from butler.core.task_manager import task_manager

logger = logging.getLogger("SkillManager")

class SkillManager:
    """
    Butler 技能管理器 (P0 增强版)
    支持动态发现、热加载、统一元数据管理与错误隔离。
    """
    def __init__(self, skills_dir="skills", lock_file="skills-lock.json"):
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.skills_dir = self.project_root / skills_dir
        self.lock_file = self.project_root / lock_file
        self.loaded_skills: Dict[str, Callable] = {}  # skill_id -> handle_request
        self.manifests: Dict[str, Dict[str, Any]] = {}  # skill_id -> manifest
        self.configs: Dict[str, Dict[str, Any]] = {}    # skill_id -> config

        # Ensure project root is in sys.path
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))

    def load_skills(self):
        """
        全量扫描并加载已启用的技能。
        支持从 __init__.py 或 main.py 加载入口。
        """
        if not self.lock_file.exists():
            logger.warning(f"Lock file {self.lock_file} not found. Creating default.")
            self._save_lock_file({"enabled_skills": []})

        try:
            with open(self.lock_file, 'r', encoding='utf-8') as f:
                enabled_skills = json.load(f).get("enabled_skills", [])
        except Exception as e:
            logger.error(f"Failed to read {self.lock_file}: {e}")
            enabled_skills = []

        # 清理旧状态以便重新加载（热加载支持）
        self.loaded_skills.clear()
        self.manifests.clear()
        self.configs.clear()

        for skill_id in enabled_skills:
            self._load_single_skill(skill_id)

    def _load_single_skill(self, skill_id: str):
        """加载单个技能，包含元数据和配置文件"""
        skill_path = self.skills_dir / skill_id
        if not skill_path.is_dir():
            logger.warning(f"Skill directory not found: {skill_path}")
            return False

        try:
            # 1. 加载 manifest.json (元数据)
            manifest_path = skill_path / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    self.manifests[skill_id] = json.load(f)

            # 2. 加载 config.json (配置)
            config_path = skill_path / "config.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.configs[skill_id] = json.load(f)

            # 3. 动态加载模块入口
            # 优先顺序: main.py > __init__.py
            entry_file = None
            if (skill_path / "main.py").exists():
                entry_file = skill_path / "main.py"
            elif (skill_path / "__init__.py").exists():
                entry_file = skill_path / "__init__.py"

            if not entry_file:
                logger.error(f"Skill {skill_id} has no entry point (main.py or __init__.py)")
                return False

            # 使用 importlib 细粒度加载，支持热重载
            module_name = f"skills.{skill_id}"
            spec = importlib.util.spec_from_file_location(module_name, str(entry_file))
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                # 强制重新加载以支持代码更新
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                if hasattr(module, "handle_request"):
                    self.loaded_skills[skill_id] = module.handle_request
                    logger.info(f"Successfully loaded skill: {skill_id}")
                    return True
                else:
                    logger.error(f"Skill {skill_id} is missing 'handle_request' function.")

        except Exception as e:
            logger.error(f"Error loading skill {skill_id}: {e}", exc_info=True)

        return False

    def execute(self, skill_id: str, action: str, **kwargs):
        """
        统一执行接口，支持同步与异步模式。
        """
        # 系统内部管理动作
        if skill_id in ["manage_skills", "skill_manager"]:
            return self._manage_skills(action, **kwargs)

        if skill_id not in self.loaded_skills:
            return f"Error: 技能 '{skill_id}' 未加载或不存在。"

        # 注入配置信息
        kwargs["config"] = self.configs.get(skill_id, {})
        kwargs["manifest"] = self.manifests.get(skill_id, {})

        jarvis_app = kwargs.get("jarvis_app")

        def skill_wrapper(action, **kwargs):
            try:
                result = self.loaded_skills[skill_id](action, **kwargs)
                # If we have jarvis_app, we can use it to speak the result in async mode
                if jarvis_app and kwargs.get("_async"):
                    jarvis_app.speak(str(result))
                return result
            except Exception as e:
                logger.error(f"Execution error in skill '{skill_id}': {e}", exc_info=True)
                msg = f"⚠️ 技能执行出错: {str(e)}"
                if jarvis_app and kwargs.get("_async"):
                    jarvis_app.speak(msg)
                return msg

        # Decide if we should run async (e.g., if explicitly requested or for long running tasks)
        run_async = kwargs.get("async_mode", False)

        if run_async:
            logger.info(f"Scheduling skill execution (ASYNC): {skill_id} -> {action}")
            kwargs["_async"] = True
            task_id = task_manager.submit(
                skill_wrapper,
                action,
                name=f"Skill:{skill_id}:{action}",
                **kwargs
            )
            return f"任务已提交 (ID: {task_id})，正在后台处理..."
        else:
            logger.info(f"Executing skill (SYNC): {skill_id} -> {action}")
            return skill_wrapper(action, **kwargs)

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

            # 安全检查：限制 URL 格式，防止恶意参数注入
            if not (url.startswith("https://") or url.startswith("git@")):
                return "错误：不安全的 URL 格式。"

            # 健壮地提取技能名
            parsed_url = urlparse(url.rstrip('/'))
            suggested_name = skill_name or os.path.basename(parsed_url.path).replace(".git", "")

            if not suggested_name:
                return "错误：无法从 URL 提取有效的技能名称，请手动提供 skill_name 参数。"

            # 路径安全检查：防止目录穿越
            if ".." in suggested_name or "/" in suggested_name or "\\" in suggested_name:
                return "错误：非法的技能名称。"

            target_path = os.path.abspath(os.path.join(self.skills_dir, suggested_name))
            if os.path.commonpath([target_path, os.path.abspath(self.skills_dir)]) != os.path.abspath(self.skills_dir):
                return "错误：非法安装路径。"

            if os.path.exists(target_path):
                return f"错误：技能 '{suggested_name}' 已存在。请先卸载或更换名称。"

            logger.info(f"正在从 {url} 安装技能 '{suggested_name}'...")
            try:
                # 使用 git clone 下载 (shell=False 为默认，参数以列表形式传递，安全)
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

            # 路径安全检查
            if ".." in skill_name or "/" in skill_name or "\\" in skill_name:
                return "错误：非法的技能名称。"

            target_path = os.path.abspath(os.path.join(self.skills_dir, skill_name))
            if os.path.commonpath([target_path, os.path.abspath(self.skills_dir)]) != os.path.abspath(self.skills_dir):
                return "错误：非法路径。"

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
