import importlib
import importlib.util
import json
import os
import logging
import sys
import subprocess
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from butler.core.task_manager import task_manager

logger = logging.getLogger("SkillManager")

class SkillManager:
    """
    Butler 技能管理器 (Cloud Code / Claude Code 风格增强版)
    支持即插即用、三阶段加载模式、SKILL.md 规范与自动依赖安装。
    """
    def __init__(self, skills_dir="skills", lock_file="skills-lock.json"):
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.skills_dir = self.project_root / skills_dir
        self.lock_file = self.project_root / lock_file

        # 内存状态
        self.loaded_skills: Dict[str, Callable] = {}  # skill_id -> handle_request (Stage 3)
        self.manifests: Dict[str, Dict[str, Any]] = {}  # skill_id -> metadata (Stage 1 & 2)
        self.configs: Dict[str, Dict[str, Any]] = {}    # skill_id -> config
        self.skill_contents: Dict[str, str] = {}        # skill_id -> SKILL.md body (Stage 2)
        self.installed_deps: set = set()                # 已安装依赖的技能路径记录

        # Ensure project root is in sys.path
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))

    def load_skills(self):
        """
        Stage 1: 扫描 skills 目录，发现所有技能并加载元数据。
        不再强制要求 skills-lock.json，实现即插即用。
        """
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)

        self.loaded_skills.clear()
        self.manifests.clear()
        self.configs.clear()
        self.skill_contents.clear()

        # 扫描目录
        for item in self.skills_dir.iterdir():
            if item.is_dir():
                skill_id = item.name
                self._discover_skill(skill_id)

        logger.info(f"Skill Stage 1 complete: Discovered {len(self.manifests)} skills.")

    def _discover_skill(self, skill_id: str):
        """
        Stage 1 & 2 预加载：检测技能格式并提取元数据。
        """
        skill_path = self.skills_dir / skill_id

        # 优先尝试 SKILL.md (新规范)
        skill_md_path = skill_path / "SKILL.md"
        if skill_md_path.exists():
            return self._load_from_skill_md(skill_id, skill_md_path)

        # Fallback 到 manifest.json (旧规范)
        manifest_path = skill_path / "manifest.json"
        if manifest_path.exists():
            return self._load_from_manifest(skill_id, manifest_path)

        return False

    def _load_from_skill_md(self, skill_id: str, file_path: Path):
        """解析 SKILL.md 中的 YAML Frontmatter 和 Markdown 正文"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1])
                    body = parts[2].strip()

                    self.manifests[skill_id] = metadata or {}
                    self.manifests[skill_id]['id'] = skill_id
                    self.manifests[skill_id]['format'] = 'SKILL.md'
                    self.skill_contents[skill_id] = body

                    # 尝试加载配套的 Python 逻辑（如果有）
                    self._try_load_python_entry(skill_id)
                    return True
        except Exception as e:
            logger.error(f"Error parsing SKILL.md for {skill_id}: {e}")
        return False

    def _load_from_manifest(self, skill_id: str, file_path: Path):
        """解析旧版的 manifest.json"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                self.manifests[skill_id] = metadata
                self.manifests[skill_id]['id'] = skill_id
                self.manifests[skill_id]['format'] = 'legacy'

                # 加载 config.json (配置)
                config_path = (self.skills_dir / skill_id) / "config.json"
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        self.configs[skill_id] = json.load(f)

                self._try_load_python_entry(skill_id)
                return True
        except Exception as e:
            logger.error(f"Error loading manifest for {skill_id}: {e}")
        return False

    def _try_load_python_entry(self, skill_id: str):
        """尝试加载 Python 入口点 (main.py 或 __init__.py)"""
        skill_path = self.skills_dir / skill_id
        entry_file = None
        if (skill_path / "main.py").exists():
            entry_file = skill_path / "main.py"
        elif (skill_path / "__init__.py").exists():
            entry_file = skill_path / "__init__.py"

        if entry_file:
            # 标记该技能需要 Python 运行时环境
            self.manifests[skill_id]['has_python'] = True
            self.manifests[skill_id]['entry_file'] = str(entry_file)

            # 注意：这里不直接加载模块，改为在第一次执行时动态加载（Stage 3）
            return True
        return False

    def _ensure_dependencies(self, skill_id: str):
        """自动检查并安装依赖 (requirements.txt)"""
        skill_path = self.skills_dir / skill_id
        req_path = skill_path / "requirements.txt"

        if req_path.exists() and str(skill_path) not in self.installed_deps:
            logger.info(f"Installing dependencies for skill '{skill_id}'...")
            try:
                # 使用 sys.executable 确保安装到当前 Python 环境
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req_path)],
                               check=True, capture_output=True)
                self.installed_deps.add(str(skill_path))
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install deps for {skill_id}: {e.stderr.decode()}")
                return False
        return True

    def _load_python_runtime(self, skill_id: str):
        """Stage 3: 真正加载 Python 模块"""
        if skill_id in self.loaded_skills:
            return True

        manifest = self.manifests.get(skill_id, {})
        entry_file = manifest.get('entry_file')

        if not entry_file:
            return False

        # 安装依赖
        self._ensure_dependencies(skill_id)

        try:
            module_name = f"skills.{skill_id}"
            spec = importlib.util.spec_from_file_location(module_name, entry_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

                if hasattr(module, "handle_request"):
                    self.loaded_skills[skill_id] = module.handle_request
                    logger.info(f"Successfully loaded Python runtime for skill: {skill_id}")
                    return True
                else:
                    logger.error(f"Skill {skill_id} is missing 'handle_request' function.")
        except Exception as e:
            logger.error(f"Error loading Python runtime for {skill_id}: {e}", exc_info=True)

        return False

    def execute(self, skill_id: str, action: str, **kwargs):
        """
        Stage 3: 执行接口。支持 Python handle_request 和 allowed-tools 脚本执行。
        """
        # 系统内部管理动作
        if skill_id in ["manage_skills", "skill_manager"]:
            return self._manage_skills(action, **kwargs)

        if skill_id not in self.manifests:
            return f"Error: 技能 '{skill_id}' 未发现。"

        manifest = self.manifests[skill_id]

        # 检查是否是脚本调用 (Stage 3: allowed-tools)
        if action.startswith("scripts/"):
            return self._execute_allowed_script(skill_id, action, **kwargs)

        # 确保 Python 运行时已加载（如果存在）
        if manifest.get('has_python'):
            if not self._load_python_runtime(skill_id):
                return f"Error: 技能 '{skill_id}' 的 Python 环境加载失败。"

        if skill_id not in self.loaded_skills:
            # 如果没有 handle_request，但有 SKILL.md，可能是纯指令技能
            if skill_id in self.skill_contents:
                return f"技能 '{skill_id}' 为纯指令集模式，请参考其 SKILL.md 指引。"
            return f"Error: 技能 '{skill_id}' 无法执行 (缺少入口)。"

        # 注入配置信息
        kwargs["config"] = self.configs.get(skill_id, {})
        kwargs["manifest"] = self.manifests.get(skill_id, {})

        jarvis_app = kwargs.get("jarvis_app")

        def skill_wrapper(action, **kwargs):
            try:
                result = self.loaded_skills[skill_id](action, **kwargs)
                if jarvis_app and kwargs.get("_async"):
                    jarvis_app.speak(str(result))
                return result
            except Exception as e:
                logger.error(f"Execution error in skill '{skill_id}': {e}", exc_info=True)
                msg = f"⚠️ 技能执行出错: {str(e)}"
                if jarvis_app and kwargs.get("_async"):
                    jarvis_app.speak(msg)
                return msg

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
        """处理技能管理相关的内部逻辑 (install, uninstall, list)"""
        import shutil
        from urllib.parse import urlparse

        entities = kwargs.get("entities", {})
        url = entities.get("url") or kwargs.get("url")
        skill_name = entities.get("skill_name") or kwargs.get("skill_name")

        if action == "install":
            if not url: return "错误：缺少技能下载链接 (URL)。"
            if not (url.startswith("https://") or url.startswith("git@")):
                return "错误：不安全的 URL 格式。"

            parsed_url = urlparse(url.rstrip('/'))
            suggested_name = skill_name or os.path.basename(parsed_url.path).replace(".git", "")

            target_path = self.skills_dir / suggested_name
            if target_path.exists():
                return f"错误：技能 '{suggested_name}' 已存在。"

            try:
                subprocess.run(["git", "clone", "--depth", "1", url, str(target_path)], check=True)
                # 重新扫描
                self.load_skills()
                return f"✅ 技能 '{suggested_name}' 已通过 Git 安装并识别。"
            except Exception as e:
                if target_path.exists(): shutil.rmtree(target_path)
                return f"❌ 安装失败: {str(e)}"

        elif action == "uninstall":
            if not skill_name: return "错误：请提供要卸载的技能名称。"
            target_path = self.skills_dir / skill_name
            if not target_path.exists():
                return f"错误：技能 '{skill_name}' 未安装。"

            try:
                shutil.rmtree(target_path)
                # 重新加载状态
                self.load_skills()
                return f"✅ 技能 '{skill_name}' 已成功卸载。"
            except Exception as e:
                return f"❌ 卸载失败: {str(e)}"

        elif action == "list":
            report = ["### Butler 技能列表 (即插即用)："]
            for s_id, meta in self.manifests.items():
                fmt = meta.get('format', 'unknown')
                desc = meta.get('description', '无描述')
                report.append(f"- **{s_id}** ({fmt}): {desc}")

            return "\n".join(report)

        return f"错误：技能管理器不支持动作 '{action}'。"

    def match_skill(self, command):
        """
        根据描述、名称或关键字匹配技能。
        """
        for skill_id, manifest in self.manifests.items():
            name = manifest.get("name", skill_id).lower()
            keywords = [k.lower() for k in manifest.get("keywords", [])]
            desc = manifest.get("description", "").lower()

            cmd_lower = command.lower()
            if name in cmd_lower or any(k in cmd_lower for k in keywords):
                return skill_id
        return None

    def get_skill_instruction(self, skill_id: str) -> Optional[str]:
        """获取技能的完整指令 (Stage 2)"""
        return self.skill_contents.get(skill_id)

    def _execute_allowed_script(self, skill_id: str, script_rel_path: str, **kwargs):
        """执行 SKILL.md 中 allowed-tools 授权的脚本"""
        manifest = self.manifests.get(skill_id, {})
        allowed_tools = manifest.get('allowed-tools', [])

        # 将 allowed-tools 转换为列表（如果是字符串）
        if isinstance(allowed_tools, str):
            allowed_tools = [t.strip() for t in allowed_tools.split(',')]

        # 简单的白名单匹配: Bash(python:scripts/...)
        is_allowed = False
        for tool in allowed_tools:
            if script_rel_path in tool:
                is_allowed = True
                break

        if not is_allowed:
            return f"Error: 脚本 '{script_rel_path}' 未在技能 '{skill_id}' 的 allowed-tools 中授权。"

        skill_path = self.skills_dir / skill_id
        script_full_path = skill_path / script_rel_path

        if not script_full_path.exists():
            return f"Error: 脚本文件不存在: {script_rel_path}"

        # 确保依赖已安装
        self._ensure_dependencies(skill_id)

        try:
            logger.info(f"Executing allowed script: {script_full_path}")
            # 构建参数
            args = [sys.executable, str(script_full_path)]
            # 简单地将 kwargs 转换为命令行参数（可选，取决于脚本设计）
            for k, v in kwargs.items():
                if k not in ['jarvis_app', 'config', 'manifest']:
                    args.extend([f"--{k}", str(v)])

            res = subprocess.run(args, capture_output=True, text=True, check=True)
            return res.stdout
        except subprocess.CalledProcessError as e:
            return f"Error: 脚本执行失败 ({e.returncode}): {e.stderr}"
        except Exception as e:
            return f"Error: 执行脚本时发生未知错误: {str(e)}"
