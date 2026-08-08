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


def discover_skills(skills_dir: Path = None, max_depth: int = 2) -> Dict[str, Path]:
    """发现 skills/ 下所有技能文件夹 (递归扫描)。"""
    if skills_dir is None:
        skills_dir = get_skills_dir()

    skills = {}
    if not skills_dir.exists():
        return skills

    def _scan(current: Path, depth: int):
        if depth > max_depth:
            return
        try:
            for item in current.iterdir():
                if item.is_dir() and not item.name.startswith('.') and item.name != "__pycache__":
                    if (item / "SKILL.md").exists() or (item / "manifest.json").exists() or (item / "config.yaml").exists():
                        skills[item.name] = item
                    else:
                        _scan(item, depth + 1)
        except Exception:
            pass

    _scan(skills_dir, 0)
    return skills


def find_entry_point(skill_path: Path) -> Optional[Path]:
    """查找技能的 Python 入口文件。"""
    for name in ["main.py", "__init__.py", "run.py"]:
        p = skill_path / name
        if p.exists():
            return p
    return None


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
    """加载技能的完整元数据 (SKILL.md + manifest.json + config.yaml)。"""
    meta = {"id": skill_id, "path": str(skill_path)}

    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        try:
            content = skill_md.read_text(encoding='utf-8')
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    import yaml
                    md_meta = yaml.safe_load(parts[1]) or {}
                    meta.update(md_meta)
                    meta['description'] = meta.get('description', '')
                    if not meta.get('description'):
                        body = parts[2].strip()
                        meta['description'] = body.split('\n')[0].strip('# ')
            else:
                meta['description'] = content.strip().split('\n')[0].strip('# ')
            meta['format'] = 'SKILL.md'
        except Exception as e:
            logger.debug(f"Failed to parse SKILL.md for {skill_id}: {e}")

    manifest_path = skill_path / "manifest.json"
    if manifest_path.exists():
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
    if config_path.exists():
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

    meta['access_level'] = detect_callable_type(skill_id, skill_path, meta)

    return meta


def load_all_skills() -> List[Tuple[str, Path, Dict]]:
    """加载所有技能的元数据，返回 [(skill_id, path, meta), ...]。"""
    skills = discover_skills()
    result = []
    for skill_id, path in sorted(skills.items()):
        meta = load_skill_metadata(skill_id, path)
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
    """读取 SKILL.md 的正文内容 (去除 YAML frontmatter)。"""
    skill_md = skill_path / "SKILL.md"
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