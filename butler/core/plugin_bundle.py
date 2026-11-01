# -*- coding: utf-8 -*-
"""
DeepSeek Harness (dsh) / Claude Code 插件包的声明式兼容层。

Butler 不运行 Cordis (TS/JS) 运行时，而是解析插件包中的声明式资产，
把 ``skills/``、``commands/``、``agents/`` 导入现有的技能系统。
"""
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("PluginBundle")

MARKER_FILE = ".butler-plugin.json"
ASSET_KINDS = ("skills", "commands", "agents")
_IGNORE = shutil.ignore_patterns(
    "node_modules", ".git", "__pycache__", "*.pyc", ".venv", "venv", "dist", ".butler"
)
_MAX_ASSET_DEPTH = 2


def sanitize_name(name: str) -> str:
    """把 npm 包名 / 目录名转成安全的目录与技能前缀。"""
    name = str(name or "").strip().lstrip("@")
    name = name.replace("/", "-")
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", name)
    return name.strip("-") or "plugin"


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _find_asset_dirs(root: Path, asset: str) -> List[Path]:
    """在插件根目录附近查找声明式资产目录（浅层搜索，避免 node_modules）。"""
    found: List[Path] = []
    seen: set = set()

    def _add(path: Path):
        path = Path(path)
        if path.is_dir() and str(path) not in seen:
            seen.add(str(path))
            found.append(path)

    _add(root / asset)
    if root.is_dir():
        for current in sorted(root.iterdir()):
            if not current.is_dir() or current.name.startswith('.') or current.name in (
                "node_modules", "__pycache__", "dist", "build", ".venv", "venv"
            ):
                continue
            _add(current / asset)
            for nested in sorted(current.iterdir()):
                if nested.is_dir() and not nested.name.startswith('.'):
                    _add(nested / asset)
    return found


def detect_bundle(root: Path) -> Dict[str, Any]:
    """解析插件包元数据与声明式资产。"""
    root = Path(root)
    info: Dict[str, Any] = {
        "name": None,
        "version": None,
        "description": "",
        "author": "",
        "keywords": [],
        "type": "skills",
        "package_name": None,
        "entry": None,
        "dsh_patch": None,
        "hooks": None,
        "mcp": None,
        "skills": [],
        "commands": [],
        "agents": [],
    }
    if not root.exists():
        return info

    package_json = _read_json(root / "package.json")
    if package_json:
        info["package_name"] = package_json.get("name")
        info["name"] = package_json.get("name")
        info["version"] = package_json.get("version")
        info["description"] = package_json.get("description", "") or ""
        info["entry"] = package_json.get("main")
        info["keywords"] = package_json.get("keywords", []) or []
        info["author"] = package_json.get("author", "") if isinstance(package_json.get("author"), str) else ""
        dsh = package_json.get("dsh")
        if isinstance(dsh, dict) and isinstance(dsh.get("bundle"), dict):
            info["type"] = "dsh"
            info["dsh_patch"] = dsh["bundle"].get("patch")

    claude_plugin = root / ".claude-plugin" / "plugin.json"
    if claude_plugin.exists():
        plugin_json = _read_json(claude_plugin)
        info["type"] = "claude" if info["type"] == "skills" else "dual"
        for key in ("name", "version", "description", "author", "keywords"):
            if plugin_json.get(key) and not info.get(key):
                info[key] = plugin_json[key]

    for asset in ASSET_KINDS:
        info[asset] = _find_asset_dirs(root, asset)

    hooks = root / "hooks" / "hooks.json"
    info["hooks"] = str(hooks.relative_to(root)) if hooks.exists() else None
    mcp = root / ".mcp.json"
    info["mcp"] = str(mcp.relative_to(root)) if mcp.exists() else None

    return info


def _quick_asset_dirs(root: Path) -> Dict[str, List[Path]]:
    """不递归扫描的快速资产定位（用于运行时发现）。"""
    assets = {}
    for asset in ASSET_KINDS:
        candidates = [root / asset, root / "dsh-plugin" / asset, root / "plugin" / asset]
        assets[asset] = [p for p in candidates if p.is_dir()]
    return assets


def _asset_summary(root: Path, assets: Dict[str, List[Path]]) -> Dict[str, List[str]]:
    summary = {}
    for kind, dirs in assets.items():
        rel = []
        for d in dirs:
            try:
                rel.append(str(Path(d).relative_to(root)))
            except ValueError:
                rel.append(str(d))
        summary[kind] = rel
    return summary


def discover_plugin_roots(plugins_dir: Path) -> List[Dict[str, Any]]:
    """为 SkillManager 提供插件包内的技能根目录。"""
    plugins_dir = Path(plugins_dir)
    if not plugins_dir.is_dir():
        return []

    roots: List[Dict[str, Any]] = []
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith('.'):
            continue

        marker = _read_json(plugin_dir / MARKER_FILE)
        name = sanitize_name(marker.get("name") or plugin_dir.name)
        assets = marker.get("assets") if isinstance(marker.get("assets"), dict) else None
        if assets is None:
            assets = _asset_summary(plugin_dir, _quick_asset_dirs(plugin_dir))

        for kind in ASSET_KINDS:
            for rel in assets.get(kind, []) or []:
                path = plugin_dir / rel
                if not path.is_dir():
                    continue
                roots.append({
                    "path": path,
                    # 插件技能优先于项目外部目录，但低于 Butler 原生 skills/
                    "rank": 50 if kind == "skills" else 51 if kind == "commands" else 52,
                    "source": f"plugin:{name}",
                    "kind": kind,
                    "recursive": False,
                    "prefix": None if kind == "skills" else f"{name}-",
                })
    return roots


def _safe_extract_zip(zip_path: Path, target: Path):
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"Unsafe zip member: {member.filename}")
        zf.extractall(target)


def _safe_extract_tar(tar_path: Path, target: Path):
    with tarfile.open(tar_path, 'r:*') as tf:
        try:
            tf.extractall(target, filter="data")
        except TypeError:
            tf.extractall(target)


def _copy_bundle(src: Path, dst: Path):
    shutil.copytree(src, dst, ignore=_IGNORE)


def _github_to_git(spec: str) -> str:
    return "https://github.com/" + spec[len("github:"):] + ".git"


def _split_git_spec(spec: str) -> tuple:
    """拆分 github:owner/repo#path:/sub/dir 形式。"""
    sub_path = None
    if "#path:" in spec:
        spec, sub_path = spec.split("#path:", 1)
    return spec, sub_path


def _materialize_source(source: str, tmp_dir: Path) -> Path:
    """把非本地来源展开成临时目录中的插件根，返回插件根路径。"""
    source = str(source).strip()

    if source.startswith("github:"):
        git_ref, sub_path = _split_git_spec(source)
        git_url = _github_to_git(git_ref[7:] if git_ref.startswith("git+") else git_ref)
    elif source.startswith(("git@", "ssh://", "git+")) or source.endswith(".git"):
        git_ref, sub_path = _split_git_spec(source)
        git_url = git_ref[4:] if git_ref.startswith("git+") else git_ref
    else:
        git_url, sub_path = None, None

    if git_url:
        clone_dir = tmp_dir / "repo"
        subprocess.run(["git", "clone", "--depth", "1", git_url, str(clone_dir)],
                       check=True, capture_output=True)
        bundle_root = clone_dir / sub_path if sub_path else clone_dir
        if not sub_path and not (bundle_root / "package.json").exists() and (clone_dir / "dsh-plugin").is_dir():
            bundle_root = clone_dir / "dsh-plugin"
        return bundle_root

    if source.startswith(("http://", "https://")) or Path(source).exists():
        path = Path(source)
        if path.is_file():
            if path.suffix == ".zip":
                _safe_extract_zip(path, tmp_dir / "extracted")
            else:
                _safe_extract_tar(path, tmp_dir / "extracted")
            extracted = tmp_dir / "extracted"
            package_dir = extracted / "package"
            return package_dir if package_dir.is_dir() else extracted
        return path

    # 其余视为 npm 包名/spec，使用 npm pack 获取 tarball
    if not shutil.which("npm"):
        raise RuntimeError("未找到 npm，无法安装 npm 插件包。请改用本地路径 / git / zip 来源。")
    pack_dir = tmp_dir / "pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["npm", "pack", source, "--pack-destination", str(pack_dir), "--silent"],
        check=True, capture_output=True, text=True
    )
    tarballs = sorted(pack_dir.glob("*.tgz"))
    if not tarballs:
        raise RuntimeError(f"npm pack 未产出 tarball: {proc.stderr.strip()}")
    extract_dir = tmp_dir / "npm"
    extract_dir.mkdir(parents=True, exist_ok=True)
    _safe_extract_tar(tarballs[-1], extract_dir)
    package_dir = extract_dir / "package"
    return package_dir if package_dir.is_dir() else extract_dir


def install_plugin(source: str, name: str = None, plugins_dir: Path = None,
                   force: bool = False) -> Dict[str, Any]:
    """安装 dsh / Claude / 技能包插件到 plugins/ 目录（仅导入声明式资产）。"""
    from butler.core.skill_registry import get_project_root

    plugins_dir = Path(plugins_dir) if plugins_dir else get_project_root() / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="butler_plugin_") as tmp:
        bundle_root = _materialize_source(source, Path(tmp))
        if not bundle_root.exists():
            raise ValueError(f"插件来源不存在或无法解析: {source}")

        info = detect_bundle(bundle_root)
        resolved_name = sanitize_name(name or info.get("name") or bundle_root.name)
        target = plugins_dir / resolved_name

        if target.exists() and not force:
            raise FileExistsError(f"插件 '{resolved_name}' 已存在，使用 --force 覆盖。")

        if bundle_root.resolve() != target.resolve():
            if target.exists():
                shutil.rmtree(target)
            _copy_bundle(bundle_root, target)

    info = detect_bundle(target)
    assets = {
        "skills": [str(d.relative_to(target)) for d in info["skills"]],
        "commands": [str(d.relative_to(target)) for d in info["commands"]],
        "agents": [str(d.relative_to(target)) for d in info["agents"]],
    }
    if not any(assets.values()):
        if not force:
            shutil.rmtree(target, ignore_errors=True)
        raise ValueError(
            "该插件不包含可导入的声明式资产 (skills/commands/agents)；"
            "Butler 的导入式兼容不会执行 Cordis 运行时插件代码。"
        )

    marker = {
        "version": 1,
        "name": resolved_name,
        "display_name": info.get("name") or resolved_name,
        "package_name": info.get("package_name"),
        "type": info.get("type"),
        "version": info.get("version"),
        "description": info.get("description"),
        "author": info.get("author"),
        "keywords": info.get("keywords"),
        "source": source,
        "installed_at": datetime.now().isoformat(timespec="seconds"),
        "assets": assets,
        "dsh_patch": info.get("dsh_patch"),
        "hooks": info.get("hooks"),
        "mcp": info.get("mcp"),
    }
    (target / MARKER_FILE).write_text(
        json.dumps(marker, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return marker


def list_plugins(plugins_dir: Path = None) -> List[Dict[str, Any]]:
    from butler.core.skill_registry import get_project_root

    plugins_dir = Path(plugins_dir) if plugins_dir else get_project_root() / "plugins"
    if not plugins_dir.is_dir():
        return []

    result = []
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith('.'):
            continue
        marker = _read_json(plugin_dir / MARKER_FILE)
        if marker:
            marker.setdefault("name", plugin_dir.name)
            result.append(marker)
        else:
            info = detect_bundle(plugin_dir)
            result.append({
                "name": plugin_dir.name,
                "display_name": info.get("name") or plugin_dir.name,
                "type": info.get("type"),
                "version": info.get("version"),
                "description": info.get("description"),
                "source": "directory-drop",
                "installed_at": None,
                "assets": _asset_summary(plugin_dir, _quick_asset_dirs(plugin_dir)),
            })
    return result


def get_plugin(name: str, plugins_dir: Path = None) -> Optional[Dict[str, Any]]:
    name = sanitize_name(name)
    for plugin in list_plugins(plugins_dir):
        if sanitize_name(plugin.get("name")) == name:
            return plugin
    return None


def remove_plugin(name: str, plugins_dir: Path = None) -> bool:
    from butler.core.skill_registry import get_project_root

    plugins_dir = Path(plugins_dir) if plugins_dir else get_project_root() / "plugins"
    target = plugins_dir / sanitize_name(name)
    if not target.is_dir():
        return False
    shutil.rmtree(target)
    return True
