# -*- coding: utf-8 -*-
"""
Skill Registry - 共享的技能发现、元数据加载与类型检测模块

CLI (skill_cmd.py) 和 TUI (tui/main.py) 统一使用此模块，
确保技能分类、元数据解析、入口检测的行为完全一致。
"""
import os
import sys
import json
import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("SkillRegistry")


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def get_skills_dir() -> Path:
    return get_project_root() / "skills"


def find_project_root(start: Path = None) -> Path:
    """定位项目根目录：最近的包含 .git 的祖先，否则回退到启点。"""
    start = Path(start) if start else get_project_root()
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def _agents_home() -> Path:
    return Path(os.environ.get("DSH_AGENTS_HOME") or Path.home() / ".agents")


def _dsh_home() -> Path:
    return Path(os.environ.get("DSH_HOME") or Path.home() / ".dsh")


def _add_root(roots: List[Dict[str, Any]], path: Path, rank: int, source: str,
              kind: str = "skills", recursive: bool = False, prefix: str = None):
    path = Path(path)
    if path.is_dir():
        roots.append({
            "path": path,
            "rank": rank,
            "source": source,
            "kind": kind,
            "recursive": recursive,
            "prefix": prefix,
        })


def resolve_skill_roots(project_root: Path = None, include_user: bool = True,
                        include_plugins: bool = True) -> List[Dict[str, Any]]:
    """
    按 DeepSeek Harness (dsh) 的发现优先级解析技能根目录。

    顺序: Butler 原生 skills/ > 插件包 > 项目 .dsh/.agents/.claude > 用户级目录。
    同名技能由先出现的根目录接管（first-wins）。
    """
    project_root = Path(project_root) if project_root else find_project_root()
    roots: List[Dict[str, Any]] = []

    # Butler 原生目录：保留历史行为，支持分类子目录（深度 2）
    _add_root(roots, project_root / "skills", 0, "butler", recursive=True)

    # dsh / Claude 插件包中的声明式技能资产
    if include_plugins:
        from butler.core.plugin_bundle import discover_plugin_roots
        roots.extend(discover_plugin_roots(project_root / "plugins"))

    # dsh 标准项目级技能根（只发现直接子项）
    _add_root(roots, project_root / ".dsh" / "skills", 100, "project-dsh")
    _add_root(roots, project_root / ".agents" / "skills", 200, "project-agents")
    _add_root(roots, project_root / ".claude" / "skills", 210, "project-claude")

    if include_user:
        _add_root(roots, _dsh_home() / "skills", 400, "user-dsh")
        _add_root(roots, _agents_home() / "skills", 500, "user-agents")
        _add_root(roots, Path.home() / ".claude" / "skills", 510, "user-claude")

    roots.sort(key=lambda r: (r["rank"], str(r["path"])))
    return roots


def identify_skill_source(skill_path: Path, roots: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """根据技能路径反查其所属根目录信息。"""
    skill_path = Path(skill_path)
    roots = roots if roots is not None else resolve_skill_roots()
    for root in roots:
        root_path = root["path"]
        if skill_path == root_path or root_path in skill_path.parents:
            return root
    return {"source": "unknown", "rank": 999, "kind": "skills", "path": None, "prefix": None}


def _prefixed_id(root: Dict[str, Any], name: str) -> str:
    prefix = root.get("prefix")
    return f"{prefix}{name}" if prefix else name


def iter_root_entries(root: Dict[str, Any], max_depth: int = 2):
    """遍历单个技能根，产出 (skill_id, skill_path)。"""
    root_path: Path = root["path"]
    prefix = root.get("prefix")

    def _emit_file(file_path: Path, use_prefix: bool = True):
        if file_path.suffix.lower() != ".md" or file_path.name.startswith('.'):
            return None
        if file_path.name.lower() in ("readme.md", "index.md", "skill.md"):
            return None
        return (_prefixed_id(root, file_path.stem) if use_prefix else file_path.stem, file_path)

    if root.get("kind") in ("command", "commands", "agent", "agents"):
        for item in sorted(root_path.iterdir()):
            if item.is_file():
                entry = _emit_file(item, use_prefix=prefix is not None)
                if entry:
                    yield entry
        return

    if root.get("recursive"):
        def _scan(current: Path, depth: int):
            if depth > max_depth:
                return
            for item in current.iterdir():
                if item.is_dir() and not item.name.startswith('.') and item.name != "__pycache__":
                    if (item / "SKILL.md").exists() or (item / "manifest.json").exists() or (item / "config.yaml").exists():
                        yield (item.name, item)
                    else:
                        yield from _scan(item, depth + 1)
                elif item.is_file() and depth == 0:
                    entry = _emit_file(item, use_prefix=False)
                    if entry:
                        yield entry
        yield from _scan(root_path, 0)
        return

    # 标准 Agent Skills 根：只发现直接子项（目录 bundle 或扁平 <name>.md）
    for item in sorted(root_path.iterdir()):
        if item.is_dir() and not item.name.startswith('.') and item.name != "__pycache__":
            if (item / "SKILL.md").exists():
                yield (_prefixed_id(root, item.name), item)
        elif item.is_file():
            entry = _emit_file(item, use_prefix=prefix is not None)
            if entry:
                yield entry


def discover_skill_entries(skills_dir: Path = None) -> List[Tuple[str, Path, Dict[str, Any]]]:
    """发现所有技能，返回 [(skill_id, skill_path, root_info)]，同名 first-wins。"""
    if skills_dir is not None:
        roots = [{"path": Path(skills_dir), "rank": 0, "source": "butler",
                  "kind": "skills", "recursive": True, "prefix": None}]
    else:
        roots = resolve_skill_roots()

    entries = []
    seen = set()
    for root in roots:
        try:
            for skill_id, skill_path in iter_root_entries(root):
                if skill_id in seen:
                    logger.debug(f"Skill '{skill_id}' shadowed by earlier root at {root['path']}")
                    continue
                seen.add(skill_id)
                entries.append((skill_id, skill_path, root))
        except Exception as e:
            logger.debug(f"Failed to scan skill root {root['path']}: {e}")
    return entries


def discover_skills(skills_dir: Path = None, max_depth: int = 2) -> Dict[str, Path]:
    """发现所有技能 (多根目录，first-wins)。"""
    return {skill_id: path for skill_id, path, _ in discover_skill_entries(skills_dir)}


def find_entry_point(skill_path: Path) -> Optional[Path]:
    """查找技能的 Python 入口文件。"""
    if not skill_path.is_dir():
        return None
    for name in ["main.py", "__init__.py", "run.py"]:
        p = skill_path / name
        if p.exists():
            return p
    return None


def _coerce_bool(value: Any) -> Optional[bool]:
    """解析 dsh 风格布尔值；无法解析返回 None。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "yes", "on", "1"):
            return True
        if lowered in ("false", "no", "off", "0"):
            return False
    return None


def parse_invocation_policy(frontmatter: Dict[str, Any]) -> Tuple[bool, bool, bool]:
    """
    解析 dsh 技能的调用策略。

    - disable-model-invocation: true 时模型不可见
    - user-invocable: false 时用户命令不可见
    - 省略字段时默认两者可见
    返回 (model_invocable, user_invocable, valid)。
    camelCase 拼写或非法布尔值会导致整个技能判定为无效（fail closed）。
    """
    if not isinstance(frontmatter, dict):
        return True, True, True

    valid = True
    if "disableModelInvocation" in frontmatter or "userInvocable" in frontmatter:
        valid = False

    model_invocable = True
    if "disable-model-invocation" in frontmatter:
        disable = _coerce_bool(frontmatter["disable-model-invocation"])
        if disable is None:
            valid = False
        else:
            model_invocable = not disable

    user_invocable = True
    if "user-invocable" in frontmatter:
        user_invocable = _coerce_bool(frontmatter["user-invocable"])
        if user_invocable is None:
            valid = False
            user_invocable = True

    return model_invocable, user_invocable, valid


def parse_skill_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """拆分 SKILL.md 的 YAML frontmatter 与正文。"""
    if not content.startswith('---'):
        return {}, content
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    try:
        import yaml
        metadata = yaml.safe_load(parts[1]) or {}
    except Exception:
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata, parts[2].strip()


def detect_callable_type(skill_id: str, skill_path: Path, meta: Dict) -> str:
    """
    检测技能类型: 'user' (可调用) 或 'agent' (仅 AI)。

    检测优先级:
    1. meta 中显式声明的 callable / access_level
    2. manifest.json 中的 callable / access_level / type
    3. config.yaml 中的 callable / access_level / type
    4. 有 Python 入口且含 handle_request / main → 'user'
    5. 其他 → 'agent'
    """
    explicit = meta.get('callable') or meta.get('access_level')
    if explicit in ('user', 'agent'):
        return explicit

    if not skill_path.is_dir():
        return 'agent'

    manifest_path = skill_path / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                m = json.load(f)
            if m.get('callable') in ('user', 'agent'):
                return m['callable']
            if m.get('access_level') in ('user', 'agent'):
                return m['access_level']
            if m.get('type') == 'agent':
                return 'agent'
        except Exception:
            pass

    config_path = skill_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                c = yaml.safe_load(f)
            if isinstance(c, dict):
                if c.get('callable') in ('user', 'agent'):
                    return c['callable']
                if c.get('access_level') in ('user', 'agent'):
                    return c['access_level']
                if c.get('type') == 'agent':
                    return 'agent'
        except Exception:
            pass

    entry_file = meta.get('entry_file')
    if not entry_file:
        return 'agent'

    try:
        spec = importlib.util.spec_from_file_location(f"_detect_{skill_id}", entry_file)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[f"_detect_{skill_id}"] = module
            try:
                spec.loader.exec_module(module)
                if hasattr(module, "handle_request") or (hasattr(module, "main") and callable(module.main)):
                    return 'user'
            except Exception:
                pass
    except Exception:
        pass

    return 'agent'


def load_skill_metadata(skill_id: str, skill_path: Path) -> Dict[str, Any]:
    """加载技能的完整元数据 (SKILL.md / 扁平 .md + manifest.json + config.yaml)。"""
    skill_path = Path(skill_path)
    meta = {"id": skill_id, "path": str(skill_path)}

    frontmatter: Dict[str, Any] = {}
    is_flat_md = skill_path.is_file()
    skill_md = skill_path if is_flat_md else skill_path / "SKILL.md"
    if skill_md.exists():
        try:
            content = skill_md.read_text(encoding='utf-8')
            frontmatter, body = parse_skill_frontmatter(content)
            meta.update(frontmatter)
            if not meta.get('description') and body:
                meta['description'] = body.split('\n')[0].strip('# ')
            meta['format'] = 'flat-md' if is_flat_md else 'SKILL.md'
        except Exception as e:
            logger.debug(f"Failed to parse SKILL.md for {skill_id}: {e}")

    manifest_path = skill_path / "manifest.json"
    if not is_flat_md and manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            for key in ('description', 'name', 'version', 'keywords', 'actions',
                         'author', 'provides', 'requires', 'entry', 'tools'):
                if key not in meta and key in manifest:
                    meta[key] = manifest[key]
            if 'format' not in meta:
                meta['format'] = 'manifest.json'
        except Exception as e:
            logger.debug(f"Failed to parse manifest.json for {skill_id}: {e}")

    config_path = skill_path / "config.yaml"
    if not is_flat_md and config_path.exists():
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            if config_data:
                for key in ('description', 'version', 'author', 'keywords', 'actions', 'tools'):
                    if key not in meta and key in config_data:
                        meta[key] = config_data[key]
                if 'format' not in meta:
                    meta['format'] = 'config.yaml'
        except Exception as e:
            logger.debug(f"Failed to parse config.yaml for {skill_id}: {e}")

    entry_file = find_entry_point(skill_path)
    if entry_file:
        meta['entry_file'] = str(entry_file)
        meta['has_python'] = True
    else:
        meta['has_python'] = False

    # dsh 调用策略 & 元数据扩展
    model_invocable, user_invocable, policy_valid = parse_invocation_policy(frontmatter)
    meta['model_invocable'] = model_invocable
    meta['user_invocable'] = user_invocable
    meta['invocation_valid'] = policy_valid
    meta['when_to_use'] = frontmatter.get('whenToUse') or frontmatter.get('when_to_use') or ''
    if 'metadata' in frontmatter and isinstance(frontmatter['metadata'], dict):
        meta['metadata'] = frontmatter['metadata']

    root = identify_skill_source(skill_path)
    meta['source'] = root.get('source', 'unknown')
    meta['root'] = str(root.get('path') or '')
    meta['rank'] = root.get('rank', 999)
    meta['kind'] = root.get('kind', 'skills')

    meta.setdefault('name', skill_id)
    meta['access_level'] = detect_callable_type(skill_id, skill_path, meta)

    return meta


def load_all_skills() -> List[Tuple[str, Path, Dict]]:
    """加载所有技能的元数据，返回 [(skill_id, path, meta), ...]。"""
    result = []
    for skill_id, path, _root in discover_skill_entries():
        meta = load_skill_metadata(skill_id, path)
        if not meta.get('invocation_valid', True):
            logger.warning(f"Skill '{skill_id}' has an invalid invocation policy; skipped.")
            continue
        result.append((skill_id, path, meta))
    return result


def get_skill(skill_id: str) -> Optional[Tuple[Path, Dict]]:
    """获取单个技能的路径和元数据。"""
    skills = discover_skills()
    if skill_id not in skills:
        return None
    path = skills[skill_id]
    meta = load_skill_metadata(skill_id, path)
    return (path, meta)


def read_skill_contents(skill_path: Path) -> str:
    """读取 SKILL.md / 扁平 .md 的正文内容 (去除 YAML frontmatter)。"""
    skill_path = Path(skill_path)
    skill_md = skill_path if skill_path.is_file() else skill_path / "SKILL.md"
    if not skill_md.exists():
        return ""
    try:
        content = skill_md.read_text(encoding='utf-8')
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                return parts[2].strip()
        return content.strip()
    except Exception:
        return ""


ACCESS_LEVEL_INFO = {
    'user': {
        'label': '可调用',
        'icon': '🐍',
        'color': 'green',
        'description': '有 Python 入口，用户可直接调用',
        'run_cmd': 'python butler_cli.py skill run <ID>',
    },
    'agent': {
        'label': 'Agent',
        'icon': '📖',
        'color': 'blue',
        'description': '纯指令集，仅供 AI 大模型使用',
        'run_cmd': '通过 AI 对话自动触发',
    },
}

# 已知的内置工具名称 (供 manifest.json 中 tools 字段验证)
KNOWN_TOOLS = {
    'read', 'write', 'edit', 'multi_edit', 'glob', 'grep',
    'ls', 'delete', 'move', 'copy', 'bash',
}


def get_skill_tools(skill_id: str) -> List[str]:
    """获取技能声明的工具列表。"""
    result = get_skill(skill_id)
    if result is None:
        return []
    path, meta = result
    return meta.get('tools', [])


def list_all_skill_tools() -> List[Dict[str, Any]]:
    """获取所有技能声明的工具映射。"""
    skills = load_all_skills()
    tool_map = []
    for skill_id, path, meta in skills:
        tools = meta.get('tools', [])
        if tools:
            tool_map.append({
                'skill_id': skill_id,
                'tools': tools,
                'access_level': meta.get('access_level', 'agent'),
            })
    return tool_map