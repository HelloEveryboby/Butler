import importlib
import importlib.util
import json
import os
import shutil
import logging
import sys
import subprocess
import threading
import time
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from butler.core.task_manager import task_manager

logger = logging.getLogger("SkillManager")

class SkillEventHandler(FileSystemEventHandler):
    """监听 skills 目录变化的处理器"""
    def __init__(self, manager):
        self.manager = manager
        self._debounce_timer = None

    def on_any_event(self, event):
        if event.is_directory:
            # 过滤掉一些不需要关注的目录
            if any(x in event.src_path for x in ["__pycache__", ".git"]):
                return
            self._trigger_reload()
        else:
            # 关键文件变化
            filename = os.path.basename(event.src_path)
            if filename in ["SKILL.md", "manifest.json", "config.yaml", "requirements.txt"]:
                self._trigger_reload()

    def _trigger_reload(self):
        if self._debounce_timer:
            self._debounce_timer.cancel()
        self._debounce_timer = threading.Timer(1.0, self.manager.load_skills)
        self._debounce_timer.start()

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

        # 监控相关
        self._observer = None

        # Ensure project root is in sys.path
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))

    def start_monitoring(self):
        """开启异步监控逻辑"""
        if self._observer:
            return

        event_handler = SkillEventHandler(self)
        self._observer = Observer()
        self._observer.schedule(event_handler, str(self.skills_dir), recursive=True)
        self._observer.start()
        logger.info("Skill directory monitoring started.")

    def stop_monitoring(self):
        """停止监控"""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def get_system_prompt_extension(self):
        """生成全量技能目录供 AI 感知 (Stage 2 增强)，支持 OpenAI Actions 风格描述"""
        if not self.manifests:
            return ""

        extension = "\n### 🛠️ Butler 增强技能库 (OpenAI Actions 风格)\n"
        extension += "你当前拥有以下可调用的扩展技能。如果用户请求相关任务，请优先使用对应技能。\n"

        for s_id, meta in self.manifests.items():
            name = meta.get('name', s_id)
            desc = meta.get('description', '暂无描述')

            # 如果存在 OpenAI 风格的工具定义，则注入详细参数描述
            tools = meta.get('tools') or meta.get('actions')
            if tools:
                extension += f"- **{s_id}** ({name}): {desc}\n"
                extension += f"  可用的 Action 定义: {json.dumps(tools, ensure_ascii=False)}\n"
            else:
                extension += f"- **{s_id}** ({name}): {desc}\n"

        extension += "\n当调用这些技能时，请提供 JSON 格式的参数，以便系统精准执行。\n"

        # 注入预置 API 模板说明
        extension += "\n### 🌐 预置 API 模板\n"
        extension += "系统内置了以下常连接口模板，你可以直接调用 `trigger_webhook` 意图，并指定 `template` 参数：\n"
        extension += "- **feishu**: 飞书机器人通知 (参数: token)\n"
        extension += "- **notion**: Notion 页面创建 (需在 headers 中提供 API Key)\n"
        extension += "- **ifttt**: IFTTT Webhook 触发 (参数: event, key)\n"

        return extension

    def _handle_zip_skills(self):
        """处理 skills 目录下的 .zip 技能包，自动解压"""
        import zipfile
        import shutil
        for item in self.skills_dir.iterdir():
            if item.suffix == ".zip":
                skill_name = item.stem
                target_dir = self.skills_dir / skill_name
                if not target_dir.exists():
                    logger.info(f"Detected new zip skill: {item.name}, extracting...")
                    try:
                        with zipfile.ZipFile(item, 'r') as zip_ref:
                            zip_ref.extractall(target_dir)
                        # 解压成功后移除 zip 文件以防重复触发
                        item.unlink()
                    except Exception as e:
                        logger.error(f"Failed to extract zip skill {item.name}: {e}")

    def load_skills(self):
        """
        Stage 1: 扫描 skills 目录，发现所有技能并加载元数据。
        使用临时状态以避免重扫期间的竞争。
        """
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)

        # 自动处理压缩包
        self._handle_zip_skills()

        # 使用局部临时变量进行加载
        new_manifests = {}
        new_configs = {}
        new_skill_contents = {}

        # 扫描目录
        for item in self.skills_dir.iterdir():
            if item.is_dir():
                skill_id = item.name
                self._discover_skill(skill_id, new_manifests, new_configs, new_skill_contents)

        # 原子交换（在 Python 中，字典赋值是原子的）
        self.manifests = new_manifests
        self.configs = new_configs
        self.skill_contents = new_skill_contents

        # 清理已加载的模块状态（可选，如果需要强制重载 Python 模块）
        # self.loaded_skills.clear()

        logger.info(f"Skill Stage 1 complete: Discovered {len(self.manifests)} skills.")

    def _discover_skill(self, skill_id: str, manifests: dict, configs: dict, contents: dict):
        """
        Stage 1 & 2 预加载：检测技能格式并提取元数据。
        """
        skill_path = self.skills_dir / skill_id

        # 1. 优先尝试 SKILL.md (AI 友好规范)
        skill_md_path = skill_path / "SKILL.md"
        if skill_md_path.exists():
            self._load_from_skill_md(skill_id, skill_md_path, manifests, contents)

        # 2. 尝试 config.yaml (系统/硬件友好规范)
        config_yaml_path = skill_path / "config.yaml"
        if config_yaml_path.exists():
            self._load_from_config_yaml(skill_id, config_yaml_path, manifests, configs)

        # 3. Fallback 到 manifest.json (旧版规范)
        manifest_path = skill_path / "manifest.json"
        if manifest_path.exists() and skill_id not in manifests:
            self._load_from_manifest(skill_id, manifest_path, manifests, configs)

        # 如果至少加载了其中一个
        if skill_id in manifests:
            # 探测执行优先级：Binary > Python
            self._try_load_binary_entry(skill_id, manifests)
            if not manifests[skill_id].get('has_binary'):
                self._try_load_python_entry(skill_id, manifests)
            return True

        return False

    def _load_from_config_yaml(self, skill_id: str, file_path: Path, manifests: dict, configs: dict):
        """解析 config.yaml 元数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                if not config_data: return False

                if skill_id not in manifests:
                    manifests[skill_id] = config_data
                    manifests[skill_id]['id'] = skill_id
                    manifests[skill_id]['format'] = 'config.yaml'
                else:
                    manifests[skill_id].update(config_data)

                configs[skill_id] = config_data
                return True
        except Exception as e:
            logger.error(f"Error parsing config.yaml for {skill_id}: {e}")
        return False

    def _load_from_skill_md(self, skill_id: str, file_path: Path, manifests: dict, contents: dict):
        """解析 SKILL.md 中的 YAML Frontmatter 和 Markdown 正文"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            metadata = {}
            body = content
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()

            # 如果元数据中缺失描述，尝试从正文第一行提取
            if 'description' not in metadata:
                first_line = body.split('\n')[0].strip('# ')
                if first_line:
                    metadata['description'] = first_line

            if skill_id not in manifests:
                manifests[skill_id] = metadata
                manifests[skill_id]['id'] = skill_id
                manifests[skill_id]['format'] = 'SKILL.md'
            else:
                manifests[skill_id].update(metadata)

            contents[skill_id] = body
            return True
        except Exception as e:
            logger.error(f"Error parsing SKILL.md for {skill_id}: {e}")
        return False

    def _load_from_manifest(self, skill_id: str, file_path: Path, manifests: dict, configs: dict):
        """解析旧版的 manifest.json"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                manifests[skill_id] = metadata
                manifests[skill_id]['id'] = skill_id
                manifests[skill_id]['format'] = 'legacy'

                # 加载 config.json (配置)
                config_path = (self.skills_dir / skill_id) / "config.json"
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        configs[skill_id] = json.load(f)

                self._try_load_python_entry(skill_id, manifests)
                return True
        except Exception as e:
            logger.error(f"Error loading manifest for {skill_id}: {e}")
        return False

    def _try_load_python_entry(self, skill_id: str, manifests: dict):
        """尝试加载 Python 入口点 (main.py 或 __init__.py)"""
        skill_path = self.skills_dir / skill_id
        entry_file = None
        if (skill_path / "main.py").exists():
            entry_file = skill_path / "main.py"
        elif (skill_path / "__init__.py").exists():
            entry_file = skill_path / "__init__.py"

        if entry_file:
            # 标记该技能需要 Python 运行时环境
            manifests[skill_id].setdefault('has_python', True)
            manifests[skill_id]['entry_file'] = str(entry_file)
            return True
        return False

    def _try_load_binary_entry(self, skill_id: str, manifests: dict):
        """探测二进制可执行文件 (静默执行优先级最高)"""
        skill_path = self.skills_dir / skill_id
        bin_dir = skill_path / "bin"

        # 候选文件列表
        candidates = []
        if sys.platform == "win32":
            candidates.extend([f"{skill_id}.exe", f"bin/{skill_id}.exe"])
        else:
            candidates.extend([skill_id, f"bin/{skill_id}"])

        for rel_path in candidates:
            bin_path = skill_path / rel_path
            if bin_path.exists() and os.access(bin_path, os.X_OK):
                manifests[skill_id]['has_binary'] = True
                manifests[skill_id]['binary_path'] = str(bin_path)
                logger.info(f"Detected binary entry for skill '{skill_id}': {rel_path}")
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
        Stage 3: 执行接口。支持 Binary, Python handle_request 和 allowed-tools 脚本执行。
        """
        # 系统内部管理动作
        if skill_id in ["manage_skills", "skill_manager"]:
            return self._manage_skills(action, **kwargs)

        if skill_id not in self.manifests:
            return f"Error: 技能 '{skill_id}' 未发现。"

        manifest = self.manifests[skill_id]

        # 1. 优先执行二进制 (Binary Execution)
        if manifest.get('has_binary') and action == "run":
            return self._execute_binary(skill_id, **kwargs)

        # 2. 检查是否是脚本调用 (Stage 3: allowed-tools)
        if action.startswith("scripts/"):
            return self._execute_allowed_script(skill_id, action, **kwargs)

        # 3. 确保 Python 运行时已加载（如果存在）
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

        if action == "install" or action == "import":
            # 支持本地路径导入
            local_path = entities.get("path") or kwargs.get("path")
            if local_path and os.path.exists(local_path):
                import zipfile
                suggested_name = skill_name or Path(local_path).stem
                target_path = self.skills_dir / suggested_name

                try:
                    if os.path.isdir(local_path):
                        shutil.copytree(local_path, target_path)
                    elif local_path.endswith(".zip"):
                        with zipfile.ZipFile(local_path, 'r') as zip_ref:
                            zip_ref.extractall(target_path)
                    else:
                        return "错误：不支持的文件格式，请提供目录或 .zip 文件。"

                    self.load_skills()
                    return f"✅ 技能 '{suggested_name}' 已从本地路径导入。"
                except Exception as e:
                    return f"❌ 导入失败: {str(e)}"

            if not url: return "错误：缺少技能下载链接 (URL) 或本地路径 (path)。"
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

    def _execute_binary(self, skill_id: str, **kwargs):
        """执行二进制程序"""
        bin_path = self.manifests[skill_id].get('binary_path')
        if not bin_path:
            return f"Error: 技能 '{skill_id}' 找不到二进制路径。"

        try:
            logger.info(f"Executing binary for skill '{skill_id}': {bin_path}")
            args = [bin_path]
            # 将 kwargs 转换为命令行参数
            for k, v in kwargs.items():
                if k not in ['jarvis_app', 'config', 'manifest']:
                    args.extend([f"--{k}", str(v)])

            res = subprocess.run(args, capture_output=True, text=True, check=True)
            return res.stdout
        except subprocess.CalledProcessError as e:
            return f"Error: 二进制程序执行失败 ({e.returncode}): {e.stderr}"
        except Exception as e:
            return f"Error: 执行二进制程序时发生未知错误: {str(e)}"

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
