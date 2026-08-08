# -*- coding: utf-8 -*-
import os
import sys
import json
import importlib
import importlib.util
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("SkillCLI")


ACCESS_LEVELS = {
    "user": {
        "label": "🧰 手动技能",
        "icon": "🐍",
        "desc": "可直接调用 (有 Python 入口)",
        "run_cmd": "python butler_cli.py skill run <ID>",
    },
    "agent": {
        "label": "🤖 Agent 技能",
        "icon": "📖",
        "desc": "仅供 AI 大模型使用 (纯指令集)",
        "run_cmd": "通过 AI 对话自动触发",
    },
}


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _find_skills_dir() -> Path:
    return _get_project_root() / "skills"


def _discover_skill_folders() -> Dict[str, Path]:
    skills_dir = _find_skills_dir()
    skills = {}
    if not skills_dir.exists():
        return skills

    def _scan_recursive(current_dir: Path, depth=0):
        if depth > 2:
            return
        try:
            for item in current_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.') and item.name != "__pycache__":
                    if (item / "SKILL.md").exists() or (item / "manifest.json").exists() or (item / "config.yaml").exists():
                        skills[item.name] = item
                    else:
                        _scan_recursive(item, depth + 1)
        except Exception:
            pass

    _scan_recursive(skills_dir)
    return skills


def _find_entry_point(skill_id: str, skill_path: Path) -> Optional[Path]:
    candidates = ["main.py", "__init__.py", "run.py"]
    for name in candidates:
        p = skill_path / name
        if p.exists():
            return p
    return None


def _detect_callable_type(skill_id: str, skill_path: Path, meta: Dict) -> str:
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


def _load_skill_metadata(skill_id: str, skill_path: Path) -> Dict[str, Any]:
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
                        first_line = body.split('\n')[0].strip('# ')
                        meta['description'] = first_line
            else:
                body = content.strip()
                first_line = body.split('\n')[0].strip('# ')
                meta['description'] = first_line
            meta['format'] = 'SKILL.md'
        except Exception as e:
            logger.debug(f"Failed to parse SKILL.md for {skill_id}: {e}")

    manifest_path = skill_path / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            if 'description' not in meta:
                meta['description'] = manifest.get('description', '')
            if 'name' not in meta:
                meta['name'] = manifest.get('name', skill_id)
            if 'version' not in meta:
                meta['version'] = manifest.get('version', 'N/A')
            if 'keywords' not in meta:
                meta['keywords'] = manifest.get('keywords', [])
            if 'actions' not in meta:
                meta['actions'] = manifest.get('actions', [])
            if 'author' not in meta:
                meta['author'] = manifest.get('author', 'N/A')
            if 'format' not in meta:
                meta['format'] = 'manifest.json'
            if 'provides' not in meta:
                meta['provides'] = manifest.get('provides', [])
            if 'requires' not in meta:
                meta['requires'] = manifest.get('requires', {})
            if 'entry' not in meta:
                meta['entry'] = manifest.get('entry', '')
        except Exception as e:
            logger.debug(f"Failed to parse manifest.json for {skill_id}: {e}")

    config_path = skill_path / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            if config_data:
                if 'description' not in meta:
                    meta['description'] = config_data.get('description', '')
                for field in ['version', 'author', 'keywords', 'actions']:
                    if field not in meta and field in config_data:
                        meta[field] = config_data[field]
                if 'format' not in meta:
                    meta['format'] = 'config.yaml'
        except Exception as e:
            logger.debug(f"Failed to parse config.yaml for {skill_id}: {e}")

    entry_file = _find_entry_point(skill_id, skill_path)
    if entry_file:
        meta['entry_file'] = str(entry_file)
        meta['has_python'] = True
    else:
        meta['has_python'] = False

    meta['access_level'] = _detect_callable_type(skill_id, skill_path, meta)

    return meta


def _collect_all_skills() -> List[Tuple[str, Path, Dict]]:
    skills = _discover_skill_folders()
    result = []
    for skill_id, path in sorted(skills.items()):
        meta = _load_skill_metadata(skill_id, path)
        result.append((skill_id, path, meta))
    return result


def list_skills(filter_type: str = None):
    all_skills = _collect_all_skills()

    if filter_type in ('user', 'agent'):
        filtered = [(sid, path, m) for sid, path, m in all_skills if m.get('access_level') == filter_type]
    else:
        filtered = all_skills

    if not filtered:
        label = ACCESS_LEVELS.get(filter_type, {}).get('label', '') if filter_type else ''
        print(f"🛠️  未发现任何{label}技能。")
        return

    user_skills = [(s, p, m) for s, p, m in filtered if m.get('access_level') == 'user']
    agent_skills = [(s, p, m) for s, p, m in filtered if m.get('access_level') == 'agent']

    print("\n" + "=" * 70)
    print("  🛠️  Butler 技能库 (One Folder = One Skill)")
    print("=" * 70)

    if user_skills:
        info = ACCESS_LEVELS['user']
        print(f"\n  {info['icon']} {info['label']} - {info['desc']}")
        print(f"  {'─' * 60}")
        for skill_id, path, meta in user_skills:
            name = meta.get('name', skill_id)
            desc = meta.get('description', '无描述')
            version = meta.get('version', '')
            actions = meta.get('actions', [])

            print(f"\n    🐍 {skill_id} v{version}")
            print(f"       名称: {name}")
            print(f"       描述: {desc}")
            if actions:
                print(f"       动作: {', '.join(actions)}")
            print(f"       使用: python butler_cli.py skill run {skill_id} [action]")

    if agent_skills:
        info = ACCESS_LEVELS['agent']
        print(f"\n  {info['icon']} {info['label']} - {info['desc']}")
        print(f"  {'─' * 60}")
        for skill_id, path, meta in agent_skills:
            name = meta.get('name', skill_id)
            desc = meta.get('description', '无描述')
            version = meta.get('version', '')
            keywords = meta.get('keywords', [])

            print(f"\n    📖 {skill_id} v{version}")
            print(f"       名称: {name}")
            print(f"       描述: {desc}")
            if keywords:
                print(f"       关键词: {', '.join(keywords)}")
            print(f"       来源: {path}")

    total = len(all_skills)
    u_count = len(user_skills)
    a_count = len(agent_skills)
    print(f"\n{'=' * 70}")
    print(f"  共 {total} 个技能: 🐍 可调用 {u_count} 个 | 📖 Agent {a_count} 个")
    if filter_type:
        print(f"  (已过滤: 仅显示 {ACCESS_LEVELS[filter_type]['label']})")
    print(f"  {'─' * 60}")
    print(f"  手动: python butler_cli.py skill list --type user")
    print(f"  Agent: python butler_cli.py skill list --type agent")
    print(f"  运行: python butler_cli.py skill run <ID> [action]")
    print(f"  详情: python butler_cli.py skill info <ID>")
    print(f"{'=' * 70}\n")


def info_skill(skill_id: str):
    all_skills = _discover_skill_folders()
    if skill_id not in all_skills:
        print(f"❌ 技能 '{skill_id}' 未找到。")
        print(f"   可用技能: {', '.join(sorted(all_skills.keys()))}")
        return

    skill_path = all_skills[skill_id]
    meta = _load_skill_metadata(skill_id, skill_path)
    access_level = meta.get('access_level', 'agent')
    access_info = ACCESS_LEVELS.get(access_level, ACCESS_LEVELS['agent'])

    contents = ""
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        try:
            content = skill_md.read_text(encoding='utf-8')
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    contents = parts[2].strip()
            else:
                contents = content.strip()
        except Exception:
            pass

    print("\n" + "=" * 70)
    print(f"  📖 技能详情: {skill_id}")
    print("=" * 70)
    print(f"  [{access_info['icon']} {access_info['label']}] {access_info['desc']}")
    print(f"  名称: {meta.get('name', skill_id)}")
    print(f"  版本: {meta.get('version', 'N/A')}")
    print(f"  作者: {meta.get('author', 'N/A')}")
    print(f"  格式: {meta.get('format', 'unknown')}")
    print(f"  描述: {meta.get('description', '无描述')}")
    print(f"  路径: {skill_path}")

    entry_file = meta.get('entry_file')
    if entry_file:
        print(f"  入口: {entry_file}")
    else:
        print(f"  入口: (无 Python 入口 - Agent 技能)")

    actions = meta.get('actions', [])
    if actions:
        print(f"  可用动作: {', '.join(actions)}")

    keywords = meta.get('keywords', [])
    if keywords:
        print(f"  关键词: {', '.join(keywords)}")

    provides = meta.get('provides', [])
    if provides:
        print(f"  提供能力: {', '.join(provides)}")

    requires = meta.get('requires', {})
    if requires:
        print(f"  依赖: {json.dumps(requires, ensure_ascii=False)}")

    if contents:
        preview = contents[:600]
        print(f"\n  📋 SKILL.md 指令预览:\n  {'─' * 60}")
        for line in preview.split('\n'):
            print(f"  {line}")
        if len(contents) > 600:
            print(f"  ... (共 {len(contents)} 字符，已截断)")

    print(f"\n  {'─' * 60}")
    if access_level == 'user':
        print(f"  运行方式: python butler_cli.py skill run {skill_id} [action]")
        print(f"  Chat 中:  /skill {skill_id} [action]")
    else:
        print(f"  这是 Agent 技能，仅能通过 AI 对话使用。")
        print(f"  AI 会自动读取 SKILL.md 指令来完成任务。")
        print(f"  查看指令: python butler_cli.py skill info {skill_id}")
        print(f"  转为手动技能: 在目录中添加 main.py 或 __init__.py")
    print("=" * 70 + "\n")


def run_skill(skill_id: str, action: str = "run", extra_params: dict = None):
    skills = _discover_skill_folders()
    if skill_id not in skills:
        print(f"❌ 技能 '{skill_id}' 未找到。")
        print(f"   可用技能: {', '.join(sorted(skills.keys()))}")
        return False

    skill_path = skills[skill_id]
    meta = _load_skill_metadata(skill_id, skill_path)
    access_level = meta.get('access_level', 'agent')

    if access_level == 'agent':
        print(f"\n❌ 技能 '{skill_id}' 是 Agent 技能 (AI-only)")
        print(f"   类型: {ACCESS_LEVELS['agent']['desc']}")
        print(f"   无法直接运行，请通过 AI 对话使用。")
        print(f"   查看指令: python butler_cli.py skill info {skill_id}")
        print(f"   转为手动技能: 在 {skill_path} 中添加 main.py 或 __init__.py")
        return False

    entry_file = meta.get('entry_file')
    if not entry_file:
        print(f"⚠️  技能 '{skill_id}' 无 Python 入口文件。")
        print(f"   这是一个纯指令集技能 (SKILL.md only)，仅支持 AI 调用。")
        print(f"   如需独立运行，请在技能目录下添加 main.py 或 __init__.py。")
        return False

    print(f"\n🚀 正在运行技能: {skill_id} (action={action})")
    print(f"   路径: {skill_path}")
    print(f"   类型: {ACCESS_LEVELS['user']['desc']}")

    sys.path.insert(0, str(_get_project_root()))

    if _try_run_direct(skill_id, skill_path, entry_file, action, extra_params):
        return True

    if _try_run_skill_manager(skill_id, action, extra_params):
        return True

    return _try_run_isolated(skill_id, skill_path, entry_file, action, extra_params)


def _try_run_direct(skill_id: str, skill_path: Path, entry_file: str, action: str, extra_params: dict) -> bool:
    if not entry_file.endswith('.py'):
        return False

    module_name = f"skills.{skill_id}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, entry_file)
        if not spec or not spec.loader:
            return False
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if hasattr(module, "handle_request"):
            kwargs = {"entities": extra_params or {}}
            result = module.handle_request(action, **kwargs)
            _print_result(result)
            return True

        if hasattr(module, "main") and callable(module.main):
            kwargs = extra_params or {}
            result = module.main(**kwargs)
            if result is not None:
                _print_result(result)
            else:
                print(f"✅ 技能 '{skill_id}' 执行完成。")
            return True

        if entry_file.endswith("__init__.py") or entry_file.endswith("main.py"):
            print(f"⚠️  技能 '{skill_id}' 缺少 handle_request 或 main 函数。")
            print(f"   请确保入口文件定义了 handle_request(action, **kwargs) 或 main(**kwargs)。")
            return False

        return False
    except Exception as e:
        logger.debug(f"Direct run failed for {skill_id}: {e}")
        return False


def _try_run_skill_manager(skill_id: str, action: str, extra_params: dict) -> bool:
    try:
        from butler.core.skill_manager import SkillManager
        sm = SkillManager()
        sm.load_skills()
        if skill_id not in sm.manifests:
            return False

        kwargs = {"entities": extra_params or {}}
        result = sm.execute(skill_id, action, **kwargs)
        _print_result(result)
        return True
    except Exception as e:
        logger.debug(f"SkillManager run failed for {skill_id}: {e}")
        return False


def _try_run_isolated(skill_id: str, skill_path: Path, entry_file: str, action: str, extra_params: dict) -> bool:
    if not entry_file.endswith('.py'):
        return False

    project_root = str(_get_project_root())
    skill_env = os.environ.copy()
    skill_env["PYTHONPATH"] = f"{project_root}{os.pathsep}{skill_env.get('PYTHONPATH', '')}"

    payload = {
        "action": action,
        "kwargs": extra_params or {},
    }

    import subprocess
    try:
        proc = subprocess.Popen(
            [sys.executable, entry_file],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=skill_env,
            cwd=str(skill_path),
            text=True,
            bufsize=1
        )
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()
        proc.stdin.close()

        stdout_lines = []
        for line in iter(proc.stdout.readline, ''):
            line = line.strip()
            if line:
                try:
                    msg = json.loads(line)
                    if isinstance(msg, dict) and "action" in msg:
                        act = msg.get("action")
                        pld = msg.get("payload", {})
                        if act == "result":
                            _print_result(pld)
                            return True
                        elif act == "speak":
                            print(f"🔊 {pld.get('text', '')}")
                        elif act == "ui_print":
                            print(f"📢 {pld.get('text', '')}")
                        continue
                except (json.JSONDecodeError, ValueError):
                    pass
                stdout_lines.append(line)

        stderr = proc.stderr.read()
        proc.wait()

        if proc.returncode != 0 and stderr:
            print(f"❌ 技能执行失败 (exit code {proc.returncode}):")
            print(stderr)
            return False

        if stdout_lines:
            print("\n".join(stdout_lines))
        else:
            print(f"✅ 技能 '{skill_id}' 执行完成。")
        return True

    except Exception as e:
        print(f"❌ 启动技能子进程失败: {e}")
        return False


def _print_result(result: Any):
    if result is None:
        print("✅ 技能执行完成，无返回结果。")
        return

    if isinstance(result, dict):
        status = result.get("status", "")
        if status == "pending_confirmation":
            print(f"⚠️  技能需要确认: {result.get('message', '')}")
            return
        if status == "pending_resource":
            print(f"⏳ 技能等待资源: {result.get('message', '')}")
            return

        output = json.dumps(result, ensure_ascii=False, indent=2)
        print(output if len(output) > 100 else str(result))
    elif isinstance(result, str):
        print(result)
    else:
        print(str(result))


def main():
    parser = argparse.ArgumentParser(
        prog="butler skill",
        description="🛠️  技能独立运行器 - 区分手动技能与 Agent 技能",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python butler_cli.py skill list
  python butler_cli.py skill list --type user     # 仅显示可调用技能
  python butler_cli.py skill list --type agent    # 仅显示 Agent 技能
  python butler_cli.py skill info butler_expert
  python butler_cli.py skill run butler_expert
  python butler_cli.py skill run butler_expert ask --query 架构
        """
    )

    subparsers = parser.add_subparsers(dest="action", help="子命令")

    list_parser = subparsers.add_parser("list", help="列出所有技能 (区分手动/Agent)")
    list_parser.add_argument("--type", choices=["user", "agent"], default=None,
                             help="过滤类型: user=可调用, agent=Agent技能")

    run_parser = subparsers.add_parser("run", help="运行指定技能 (仅支持手动技能)")
    run_parser.add_argument("skill_id", help="技能 ID (文件夹名)")
    run_parser.add_argument("skill_action", nargs="?", default="run", help="技能动作 (默认: run)")
    run_parser.add_argument("params", nargs=argparse.REMAINDER, help="参数 (格式: --key value)")

    info_parser = subparsers.add_parser("info", help="查看技能详情 (含类型标签)")
    info_parser.add_argument("skill_id", help="技能 ID (文件夹名)")

    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()

    if args.action == "list":
        list_skills(getattr(args, 'type', None))
    elif args.action == "info":
        info_skill(args.skill_id)
    elif args.action == "run":
        extra_params = {}
        if args.params:
            i = 0
            while i < len(args.params):
                arg = args.params[i]
                if arg.startswith("--"):
                    key = arg[2:]
                    if i + 1 < len(args.params) and not args.params[i + 1].startswith("--"):
                        extra_params[key] = args.params[i + 1]
                        i += 2
                    else:
                        extra_params[key] = True
                        i += 1
                else:
                    i += 1

        run_skill(args.skill_id, args.skill_action, extra_params)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()