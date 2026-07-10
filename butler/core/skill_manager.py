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
from butler.core.algorithms import LDSTResolver
from butler.core.blackboard import blackboard

logger = logging.getLogger("SkillManager")

class CorePluginContext:
    """
    Context injected into core plugins to allow privileged access to internal modules.
    Provides direct references to:
    - event_bus
    - message_bus
    - blackboard
    - data_storage
    - system_sensor
    """
    def __init__(self, skill_manager):
        from butler.core.event_bus import event_bus
        from butler.core.message_bus import message_bus
        from butler.core.blackboard import blackboard
        from butler.data_storage import data_storage_manager
        from butler.core.hal import SystemResourceSensor

        self.event_bus = event_bus
        self.message_bus = message_bus
        self.blackboard = blackboard
        self.data_storage = data_storage_manager
        self.system_sensor = SystemResourceSensor()
        self.skill_manager = skill_manager


class SkillEventHandler(FileSystemEventHandler):
    """监听 skills 目录变化的处理器 (支持热插拔与防抖)"""
    def __init__(self, manager):
        self.manager = manager
        self._timers = {} # skill_path -> timer

    def on_modified(self, event):
        self._handle_change(event)

    def on_created(self, event):
        self._handle_change(event)

    def on_deleted(self, event):
        self._handle_change(event)

    def _handle_change(self, event):
        src_path = Path(event.src_path)

        # 确定技能根目录
        if event.is_directory:
            skill_dir = src_path
        else:
            skill_dir = src_path.parent

        if skill_dir == self.manager.skills_dir:
            return # 忽略根目录自身的变动

        if any(x in str(skill_dir) for x in ["__pycache__", ".git", ".lib"]):
            return

        # 只对关键文件变动或目录创建触发加载
        if not event.is_directory:
            filename = src_path.name
            if filename not in ["SKILL.md", "manifest.json", "config.yaml", "requirements.txt", "main.py"] and not filename.endswith(".zip"):
                return

        self._trigger_load(skill_dir)

    def _trigger_load(self, skill_dir):
        skill_path_str = str(skill_dir)
        if skill_path_str in self._timers:
            self._timers[skill_path_str].cancel()

        timer = threading.Timer(0.8, self.manager.load_and_register_skill, args=[skill_dir])
        self._timers[skill_path_str] = timer
        timer.start()

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

    def _extract_zip_skill(self, zip_path: Path):
        """解压单个 ZIP 技能包"""
        import zipfile
        skill_name = zip_path.stem
        target_dir = self.skills_dir / skill_name

        if not target_dir.exists():
            logger.info(f"📦 Detecting and extracting zip skill: {zip_path.name}")
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(target_dir)
                zip_path.unlink()
                return target_dir
            except Exception as e:
                logger.error(f"Failed to extract zip skill {zip_path.name}: {e}")
        return None

    def _handle_zip_skills(self):
        """处理 skills 目录下的所有 .zip 技能包"""
        for item in self.skills_dir.iterdir():
            if item.suffix == ".zip":
                self._extract_zip_skill(item)

    def _wait_for_file_ready(self, file_path, max_retries=10, delay=0.2):
        """确保文件完全写入磁盘后再放行 (处理大文件或慢速拷贝)"""
        import os
        last_size = -1
        for _ in range(max_retries):
            if not os.path.exists(file_path):
                time.sleep(delay)
                continue
            try:
                current_size = os.path.getsize(file_path)
                # 如果文件大小在指定时间内不再变化，且大于 0，说明写入完成
                if current_size == last_size and current_size > 0:
                    # 尝试以追加模式打开，测试文件是否被操作系统释放
                    with open(file_path, "a"):
                        return True
                last_size = current_size
            except (IOError, OSError):
                # 文件仍被独占锁死，继续等待
                pass
            time.sleep(delay)
        return False

    def load_and_register_skill(self, skill_dir_path):
        """增量加载并注册单个技能，支持运行时热插拔 (支持文件夹与 ZIP)"""
        skill_path = Path(skill_dir_path)

        # 处理 ZIP 文件
        if skill_path.suffix == ".zip":
            if not self._wait_for_file_ready(str(skill_path)):
                return
            extracted_dir = self._extract_zip_skill(skill_path)
            if extracted_dir:
                skill_path = extracted_dir
            else:
                return

        skill_dir = skill_path
        skill_id = skill_dir.name

        if not skill_dir.exists():
            # 处理删除逻辑
            logger.info(f"🗑️ 检测到技能目录删除: {skill_id}")
            self.manifests.pop(skill_id, None)
            self.configs.pop(skill_id, None)
            self.skill_contents.pop(skill_id, None)
            self.loaded_skills.pop(skill_id, None)
            return

        # 稳定性保障：如果是新拖入的，检查核心元数据文件是否就绪
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            if not self._wait_for_file_ready(str(skill_md)):
                logger.warning(f"Skill {skill_id} SKILL.md is not ready, skipping.")
                return

        logger.info(f"✨ 正在热加载技能: {skill_id}")

        # 发现并加载
        success = self._discover_skill(skill_id, self.manifests, self.configs, self.skill_contents)

        if success:
            logger.info(f"✅ 技能 [{skill_id}] 热加载/更新成功！")
            # 如果该技能之前已加载过 Python 模块，可能需要考虑重新加载（此处暂不强制，通常由子进程方案解决）
        else:
            logger.error(f"❌ 技能 [{skill_id}] 热加载失败 (未发现有效元数据)")

    def load_skills(self):
        """
        Stage 1: 扫描 skills 目录，发现所有技能并加载元数据。
        支持递归探测 (深度=2)，以便支持分类文件夹。
        """
        if not self.skills_dir.exists():
            self.skills_dir.mkdir(parents=True, exist_ok=True)

        # 自动处理压缩包
        self._handle_zip_skills()

        # 使用局部临时变量进行加载
        new_manifests = {}
        new_configs = {}
        new_skill_contents = {}

        # 扫描目录 (深度优先递归探测)
        def _scan_recursive(current_dir: Path, depth=0):
            if depth > 2: return
            try:
                for item in current_dir.iterdir():
                    if item.is_dir() and not item.name.startswith('.') and item.name != "__pycache__":
                        # 检查是否是技能目录
                        if (item / "SKILL.md").exists() or (item / "config.yaml").exists() or (item / "manifest.json").exists():
                            self._discover_skill(item.name, new_manifests, new_configs, new_skill_contents, skill_path=item)
                        else:
                            _scan_recursive(item, depth + 1)
            except Exception:
                pass

        _scan_recursive(self.skills_dir)

        # 原子交换（在 Python 中，字典赋值是原子的）
        self.manifests = new_manifests
        self.configs = new_configs
        self.skill_contents = new_skill_contents

        logger.info(f"Skill Stage 1 complete: Discovered {len(self.manifests)} skills.")

        # 自动强行加载核心插件，并常驻内存
        for s_id, meta in list(self.manifests.items()):
            if meta.get('is_core'):
                logger.info(f"Forcibly auto-loading core plugin: {s_id}")
                self._load_python_runtime(s_id)

    def _discover_skill(self, skill_id: str, manifests: dict, configs: dict, contents: dict, skill_path: Path = None):
        """
        Stage 1 & 2 预加载：检测技能格式并提取元数据。
        """
        if skill_path is None:
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
            self._load_from_manifest(skill_id, manifest_path, manifests, configs, skill_path=skill_path)

        # 如果至少加载了其中一个
        if skill_id in manifests:
            manifests[skill_id]['path'] = str(skill_path)
            # Detect core plugin status
            if "core_plugins" in str(skill_path.resolve()):
                manifests[skill_id]['is_core'] = True
            else:
                manifests[skill_id]['is_core'] = False
            # 确保关键字段存在 (LDST & Risk)
            manifests[skill_id].setdefault('provides', [])
            manifests[skill_id].setdefault('requires', {})
            manifests[skill_id].setdefault('risk', 'low')

            # 探测执行优先级：Binary > Python
            self._try_load_binary_entry(skill_id, manifests, skill_path=skill_path)
            if not manifests[skill_id].get('has_binary'):
                self._try_load_python_entry(skill_id, manifests, skill_path=skill_path)

            # 探测前端入口
            self._try_load_frontend_entry(skill_id, manifests, skill_path=skill_path)
            return True

        return False

    def _try_load_frontend_entry(self, skill_id: str, manifests: dict, skill_path: Path = None):
        """探测前端 UI 入口 (index.html)"""
        if skill_path is None:
            skill_path = self.skills_dir / skill_id

        # 1. 如果 SKILL.md 中明确指定了 frontend
        frontend_file = manifests[skill_id].get('frontend')
        if frontend_file:
            frontend_path = skill_path / frontend_file
            if frontend_path.exists():
                manifests[skill_id]['has_frontend'] = True
                manifests[skill_id]['frontend_path'] = str(frontend_path)
                return True

        # 2. 自动探测约定位置: ui/index.html 或 index.html
        for rel_path in ["ui/index.html", "index.html"]:
            frontend_path = skill_path / rel_path
            if frontend_path.exists():
                manifests[skill_id]['has_frontend'] = True
                manifests[skill_id]['frontend_path'] = str(frontend_path)
                # 同时也更新 manifests 中的 frontend 字段
                manifests[skill_id]['frontend'] = rel_path
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

            # Ensure LDST and Risk metadata are present
            manifests[skill_id].setdefault('provides', metadata.get('provides', []))
            manifests[skill_id].setdefault('requires', metadata.get('requires', {}))
            manifests[skill_id].setdefault('risk', metadata.get('risk', 'low'))

            contents[skill_id] = body
            return True
        except Exception as e:
            logger.error(f"Error parsing SKILL.md for {skill_id}: {e}")
        return False

    def _load_from_manifest(self, skill_id: str, manifest_path: Path, manifests: dict, configs: dict, skill_path: Path = None):
        """解析旧版的 manifest.json"""
        if skill_path is None:
            skill_path = self.skills_dir / skill_id
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                manifests[skill_id] = metadata
                manifests[skill_id]['id'] = skill_id
                manifests[skill_id]['format'] = 'legacy'

                # 加载 config.json (配置)
                config_path = skill_path / "config.json"
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        configs[skill_id] = json.load(f)

                self._try_load_python_entry(skill_id, manifests, skill_path=skill_path)
                return True
        except Exception as e:
            logger.error(f"Error loading manifest for {skill_id}: {e}")
        return False

    def _try_load_python_entry(self, skill_id: str, manifests: dict, skill_path: Path = None):
        """尝试加载 Python 入口点 (自定义、main.py 或 __init__.py)"""
        if skill_path is None:
            skill_path = self.skills_dir / skill_id
        entry_file = None

        # 1. 优先检查 manifest 中指定的 python_entry
        custom_entry = manifests[skill_id].get('python_entry')
        if custom_entry:
            custom_path = skill_path / custom_entry
            if custom_path.exists():
                entry_file = custom_path

        # 2. 默认探测
        if not entry_file:
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

    def _try_load_binary_entry(self, skill_id: str, manifests: dict, skill_path: Path = None):
        """探测二进制可执行文件 (静默执行优先级最高)"""
        if skill_path is None:
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

    def _ensure_dependencies(self, skill_id: str, target_lib: bool = False):
        """
        自动检查并安装依赖 (requirements.txt)。
        :param target_lib: 是否安装到技能目录下的 .lib 文件夹中 (用于进程隔离)
        """
        manifest = self.manifests.get(skill_id, {})
        skill_path = Path(manifest.get('path', self.skills_dir / skill_id))
        req_path = skill_path / "requirements.txt"

        # 记录安装状态的 key (如果是 target_lib，则区分开)
        dep_key = f"{skill_path}_lib" if target_lib else str(skill_path)

        if req_path.exists() and dep_key not in self.installed_deps:
            logger.info(f"Installing dependencies for skill '{skill_id}' (target_lib={target_lib})...")
            try:
                args = [sys.executable, "-m", "pip", "install", "-r", str(req_path)]
                if target_lib:
                    lib_dir = skill_path / ".lib"
                    lib_dir.mkdir(exist_ok=True)
                    args.extend(["--target", str(lib_dir)])

                subprocess.run(args, check=True, capture_output=True)
                self.installed_deps.add(dep_key)
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

                    # Privilege injection for Core Plugins
                    if manifest.get('is_core') and hasattr(module, "initialize_core"):
                        try:
                            context = CorePluginContext(self)
                            module.initialize_core(context)
                            logger.info(f"Successfully initialized core plugin context for {skill_id}")
                        except Exception as init_err:
                            logger.error(f"Error initializing core context for {skill_id}: {init_err}")

                    return True
                else:
                    logger.error(f"Skill {skill_id} is missing 'handle_request' function.")
        except Exception as e:
            logger.error(f"Error loading Python runtime for {skill_id}: {e}", exc_info=True)

        return False

    def _check_risk_escalation(self, execution_chain: List[str]) -> str:
        """
        检查执行链中的风险等级并进行提权。
        返回最高风险等级 ('low' 或 'high')。
        """
        max_risk = "low"
        high_risk_provides_patterns = ["net.exploit", "system.registry.deleted", "file.deleted", "auth.privilege.escalated"]

        for s_id in execution_chain:
            meta = self.manifests.get(s_id, {})
            risk = meta.get('risk', 'low')

            # 1. 显式声明提权
            if risk == "high":
                max_risk = "high"
                break

            # 2. Requires 提权 (Admin/Root)
            requires = meta.get('requires', {})
            if isinstance(requires, dict):
                if any(v in ["admin", "root"] for v in requires.values()):
                    max_risk = "high"
                    break

            # 3. Provides 提权 (正则匹配敏感操作)
            provides = meta.get('provides', [])
            if any(any(pattern in p for pattern in high_risk_provides_patterns) for p in provides):
                max_risk = "high"
                break

        return max_risk

    def execute(self, skill_id: str, action: str, **kwargs):
        """
        Stage 3: 执行接口。支持 LDST 影子链解析、ESB 黑板快照下发。
        """
        # --- 资源感知调度 (DRAS) ---
        from butler.core.algorithms import dras_manager
        allowed, msg = dras_manager.check_schedule_allowed()
        if not allowed and not kwargs.get("force_execute"):
            return {
                "status": "pending_resource",
                "message": msg
            }

        # 系统内部管理动作
        if skill_id in ["manage_skills", "skill_manager"]:
            return self._manage_skills(action, **kwargs)

        if skill_id not in self.manifests:
            return f"Error: 技能 '{skill_id}' 未发现。"

        # --- LDST 影子链解析 ---
        try:
            resolver = LDSTResolver(self.manifests)
            execution_chain = resolver.resolve(skill_id)
            logger.info(f"LDST Execution Chain resolved: {execution_chain}")
        except Exception as e:
            return str(e)

        # --- 风险分级与确认 ---
        max_risk = self._check_risk_escalation(execution_chain)
        if max_risk == "high" and not kwargs.get("force_execute"):
            # 自动挂起并请求 UI 二次确认
            logger.warning(f"High risk detected for chain: {execution_chain}. Suspending execution.")
            return {
                "status": "pending_confirmation",
                "risk": "high",
                "chain": execution_chain,
                "message": f"⚠️ **高危操作拦截**：执行 '{skill_id}' 涉及敏感操作（风险链：{execution_chain}）。\n为了您的系统安全，此任务已自动挂起。请在下方输入“允许执行”或点击确认按钮。"
            }

        # --- 影子链执行包装器 (处理同步/异步) ---
        def chain_execution_wrapper(**kwargs):
            last_result = None
            for current_skill_id in execution_chain:
                # 强制链条内的子任务同步执行，以便数据接力
                sub_kwargs = kwargs.copy()
                sub_kwargs["async_mode"] = False

                last_result = self._execute_single_skill(current_skill_id, action if current_skill_id == skill_id else "run", **sub_kwargs)

                # 如果是中间节点，将其 Output 写入黑板以便下游使用
                meta = self.manifests[current_skill_id]
                provides = meta.get('provides', [])
                if provides and isinstance(last_result, dict):
                    for p_key in provides:
                        if p_key in last_result:
                            blackboard.write(p_key, last_result[p_key])
            return last_result

        run_async = kwargs.get("async_mode", False)
        if run_async:
            logger.info(f"Scheduling LDST shadow chain execution (ASYNC): {execution_chain}")
            return task_manager.submit(
                chain_execution_wrapper,
                name=f"LDSTChain:{skill_id}",
                **kwargs
            )
        else:
            return chain_execution_wrapper(**kwargs)

    def _execute_single_skill(self, skill_id: str, action: str, **kwargs):
        """执行单个技能（支持进程隔离与向下兼容）"""
        manifest = self.manifests[skill_id]

        # 注入 ESB 快照 (Requires)
        requires = manifest.get('requires', {})
        if isinstance(requires, dict):
            req_keys = list(requires.keys())
            kwargs["blackboard_snapshot"] = blackboard.get_snapshot_payload(req_keys)

        # 1. 优先执行二进制 (Binary Execution)
        if manifest.get('has_binary') and action == "run":
            return self._execute_binary(skill_id, **kwargs)

        # 2. 检查是否是脚本调用 (Stage 3: allowed-tools)
        if action.startswith("scripts/"):
            return self._execute_allowed_script(skill_id, action, **kwargs)

        # 3. Python 技能执行
        if manifest.get('has_python'):
            # Core plugins run in-process for privileged context
            if manifest.get('is_core'):
                if not self._load_python_runtime(skill_id):
                    return f"Error: 技能 '{skill_id}' 的 Python 环境加载失败。"
            else:
                # 确定隔离模式：显式声明 isolation: process 或存在 LDST 路由前缀
                isolation = manifest.get('isolation') == 'process' or \
                            any(str(p).startswith(('system.', 'net.', 'file.')) for p in manifest.get('provides', []))

                if isolation:
                    return self._execute_python_subprocess(skill_id, action, **kwargs)
                else:
                    # 向下兼容：主进程加载，但给予警告
                    logger.warning(f"⚠️ 警告: 技能 [{skill_id}] 正在以非隔离模式运行，强烈建议重构。")
                    if not self._load_python_runtime(skill_id):
                        return f"Error: 技能 '{skill_id}' 的 Python 环境加载失败。"

        if skill_id not in self.loaded_skills:
            if skill_id in self.skill_contents:
                return f"技能 '{skill_id}' 为纯指令集模式。"
            return f"Error: 技能 '{skill_id}' 无法执行 (缺少入口)。"

        # 注入配置与元数据
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
                return f"⚠️ 技能执行出错: {str(e)}"

        run_async = kwargs.get("async_mode", False)
        if run_async:
            return task_manager.submit(skill_wrapper, action, name=f"Skill:{skill_id}", **kwargs)
        else:
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

            # Check if skill is core
            meta = self.manifests.get(skill_name)
            if meta and meta.get('is_core'):
                return f"错误：技能 '{skill_name}' 是核心插件 (Core Plugin)，禁止热卸载！"

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

    def _inject_secrets(self, skill_id: str, env: Dict[str, str]):
        """
        Scan and inject secrets into environment variables.
        Whitelist-based: only for .env or skill configs.
        Pattern: {{VAULT_KEY}}
        """
        from butler.core.secret_vault import secret_vault
        import re

        pattern = re.compile(r"\{\{VAULT_([A-Z0-9_]+)\}\}")

        # Injected via env vars primarily for subprocess isolation
        for key, value in env.items():
            matches = pattern.findall(value)
            for m in matches:
                secret = secret_vault.get_secret(m)
                if secret:
                    env[key] = value.replace(f"{{{{VAULT_{m}}}}}" , secret)
                    logger.debug(f"Injected secret VAULT_{m} into ENV {key}")

    def _execute_python_subprocess(self, skill_id: str, action: str, **kwargs):
        """在独立子进程中执行 Python 技能，并通过 JSON-RPC 通信 (加强鲁棒性版)"""
        manifest = self.manifests[skill_id]
        skill_path = Path(manifest.get('path', self.skills_dir / skill_id)).resolve()
        entry_file = Path(manifest.get('entry_file')).resolve()

        # 准备依赖环境
        self._ensure_dependencies(skill_id, target_lib=True)

        # 构建环境变量
        skill_env = os.environ.copy()

        # 加载 .env 文件内容到 skill_env (如果存在)
        env_file = skill_path / ".env"
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        skill_env[k.strip()] = v.strip()

        # 执行秘密注入
        self._inject_secrets(skill_id, skill_env)

        # 内存安全：显式清理 Python 侧内存痕迹 (as requested)
        import gc
        gc.collect()

        # --- 铁血架构升级：委托 Go Runner (butler_runner) 执行 ---
        from butler.core.runner_server import runner_server

        runner_id = kwargs.get("target_runner", "default_runner")
        is_long_running = manifest.get('is_long_running', False)

        if runner_server.list_runners():
            logger.info(f"🛡️ [影子执行] 委托 Go 内核 (Runner: {runner_id}) 启动技能: {skill_id}")

            spawn_config = {
                "id": skill_id,
                "path": str(entry_file),
                "args": [sys.executable, str(entry_file)], # Base command
                "env": skill_env,
                "risk": manifest.get('risk', 'low'),
                "is_long_running": is_long_running
            }

            success, msg = runner_server.send_command(runner_id, "spawn_skill", payload="", skill_config=spawn_config)
            if success:
                return f"Skill {skill_id} delegated to Go Runner."
            else:
                logger.warning(f"委托 Go 执行失败 ({msg})，Fallback 到本地 Popen。")

        # Fallback 逻辑 (或在 Headless 模式下的默认逻辑)
        local_lib = (skill_path / ".lib").resolve()
        # 确保项目根目录也在 PYTHONPATH 中，以便子进程可以导入 butler.core.skill_sdk
        project_root = str(self.project_root)
        skill_env["PYTHONPATH"] = f"{local_lib}{os.pathsep}{project_root}{os.pathsep}{skill_env.get('PYTHONPATH', '')}"

        # 构建执行参数 (JSON 格式)
        payload = {
            "action": action,
            "config": self.configs.get(skill_id, {}),
            "manifest": manifest,
            "kwargs": {k: v for k, v in kwargs.items() if k not in ['jarvis_app']}
        }

        try:
            logger.info(f"🚀 [隔离执行] 正在启动技能子进程: {skill_id} (Path: {skill_path})")
            process = subprocess.Popen(
                [sys.executable, str(entry_file)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=skill_env,
                cwd=str(skill_path), # 设置工作目录为技能目录
                text=True,
                bufsize=1
            )

            # 向子进程发送初始载荷
            process.stdin.write(json.dumps(payload) + "\n")
            process.stdin.flush()
            process.stdin.close() # 发送完载荷后关闭 stdin

            final_result = []
            output_buffer = []
            jarvis_app = kwargs.get("jarvis_app")

            def handle_stdout():
                for line in iter(process.stdout.readline, ''):
                    line = line.strip()
                    if not line: continue

                    is_rpc = False
                    try:
                        # 尝试解析为 JSON-RPC (必须是严格的 JSON 对象)
                        if line.startswith('{') and line.endswith('}'):
                            msg = json.loads(line)
                            if isinstance(msg, dict) and "action" in msg:
                                act = msg.get("action")
                                pld = msg.get("payload", {})
                                if act == "speak" and jarvis_app:
                                    jarvis_app.speak(pld.get("text", ""))
                                elif act == "ui_print" and jarvis_app:
                                    jarvis_app.ui_print(pld.get("text", ""), tag=pld.get("tag", "ai_response"))
                                elif act == "blackboard_write":
                                    key = pld.get("key")
                                    val = pld.get("value")
                                    ttl = pld.get("ttl", 60.0)
                                    if key:
                                        blackboard.write(key, val, ttl)
                                elif act == "result":
                                    final_result.append(pld)
                                is_rpc = True
                    except Exception as e:
                        logger.debug(f"RPC parse error: {e}")

                    if not is_rpc:
                        # 普通打印输出
                        logger.info(f"[{skill_id}] {line}")
                        output_buffer.append(line)

            # 启动 stdout 监听线程
            stdout_thread = threading.Thread(target=handle_stdout, daemon=True)
            stdout_thread.start()

            # 读取 stderr 并等待进程结束 (避免与 stdout_thread 竞争)
            stderr = process.stderr.read()
            process.wait()
            stdout_thread.join(timeout=2.0)

            # 关闭未关闭的流
            process.stdout.close()
            process.stderr.close()

            if process.returncode != 0:
                logger.error(f"子进程 {skill_id} 异常退出 ({process.returncode}): {stderr}")
                return f"Error: 技能执行失败 ({process.returncode}): {stderr}"

            # 优先返回正式的 result 载荷，否则返回汇总的 stdout 内容
            if final_result:
                return final_result[0]
            return "\n".join(output_buffer) if output_buffer else "Success"

        except Exception as e:
            logger.error(f"启动技能子进程失败: {e}", exc_info=True)
            return f"Error: 无法启动子进程: {e}"

    def _execute_binary(self, skill_id: str, **kwargs):
        """执行二进制程序"""
        if skill_id not in self.manifests: return f"Error: {skill_id} not found."
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
        if skill_id not in self.manifests: return f"Error: {skill_id} not found."
        manifest = self.manifests[skill_id]
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

        skill_path = Path(manifest.get('path', self.skills_dir / skill_id))
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
