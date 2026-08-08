# -*- coding: utf-8 -*-
import os
import sys
import json
import importlib
import importlib.util
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("SkillCLI")


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _find_skills_dir() -> Path:
    root = _get_project_root()
    return root / "skills"


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


def _load_skill_metadata(skill_id: str, skill_path: Path) -> Dict[str, Any]:
    meta = {"id": skill_id, "path": str(skill_path)}

    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        try:
            import yaml
            content = skill_md.read_text(encoding='utf-8')
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
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

    return meta


def _find_entry_point(skill_id: str, skill_path: Path) -> Optional[Path]:
    candidates = ["main.py", "__init__.py", "run.py"]
    for name in candidates:
        p = skill_path / name
        if p.exists():
            return p
    return None


def list_skills():
    skills = _discover_skill_folders()
    if not skills:
        print("🛠️  当前 skills/ 目录下未发现任何技能。")
        print("   将包含 SKILL.md 或 manifest.json 的文件夹放入 skills/ 即可。")
        return

    print("\n" + "=" * 60)
    print("  🛠️  Butler 技能库 (One Folder = One Skill)")
    print("=" * 60)

    for skill_id, skill_path in sorted(skills.items()):
        meta = _load_skill_metadata(skill_id, skill_path)
        name = meta.get('name', skill_id)
        desc = meta.get('description', '无描述')
        fmt = meta.get('format', 'unknown')
        version = meta.get('version', '')
        has_py = "🐍" if meta.get('has_python') else "📝"

        print(f"\n  {has_py} {skill_id}")
        print(f"     名称: {name}")
        print(f"     描述: {desc}")
        if version:
            print(f"     版本: {version}")
        print(f"     格式: {fmt} | 路径: {skill_path}")

        actions = meta.get('actions', [])
        if actions:
            print(f"     可用动作: {', '.join(actions)}")

        keywords = meta.get('keywords', [])
        if keywords:
            print(f"     关键词: {', '.join(keywords)}")

    print("\n" + "=" * 60)
    print(f"  共发现 {len(skills)} 个技能")
    print("  使用 'python butler_cli.py skill run <ID> [action]' 来运行技能")
    print("=" * 60 + "\n")


def info_skill(skill_id: str):
    skills = _discover_skill_folders()
    if skill_id not in skills:
        print(f"❌ 技能 '{skill_id}' 未找到。")
        print(f"   可用技能: {', '.join(sorted(skills.keys()))}")
        return

    skill_path = skills[skill_id]
    meta = _load_skill_metadata(skill_id, skill_path)

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

    print("\n" + "=" * 60)
    print(f"  📖 技能详情: {skill_id}")
    print("=" * 60)
    print(f"  名称: {meta.get('name', skill_id)}")
    print(f"  版本: {meta.get('version', 'N/A')}")
    print(f"  作者: {meta.get('author', 'N/A')}")
    print(f"  格式: {meta.get('format', 'unknown')}")
    print(f"  描述: {meta.get('description', '无描述')}")
    print(f"  路径: {skill_path}")

    entry_file = meta.get('entry_file')
    if entry_file:
        print(f"  入口: {entry_file}")

    actions = meta.get('actions', [])
    if actions:
        print(f"  可用动作: {', '.join(actions)}")

    keywords = meta.get('keywords', [])
    if keywords:
        print(f"  关键词: {', '.join(keywords)}")

    if contents:
        preview = contents[:500]
        print(f"\n  📋 SKILL.md 摘要:\n  {'─' * 50}")
        for line in preview.split('\n'):
            print(f"  {line}")
        if len(contents) > 500:
            print(f"  ... (共 {len(contents)} 字符，已截断)")

    print("=" * 60)
    print(f"  运行方式:")
    print(f"    python butler_cli.py skill run {skill_id} [action]")
    print(f"    python butler_cli.py skill run {skill_id} run --key value")
    print("=" * 60 + "\n")


def run_skill(skill_id: str, action: str = "run", extra_params: dict = None):
    skills = _discover_skill_folders()
    if skill_id not in skills:
        print(f"❌ 技能 '{skill_id}' 未找到。")
        print(f"   可用技能: {', '.join(sorted(skills.keys()))}")
        return False

    skill_path = skills[skill_id]
    meta = _load_skill_metadata(skill_id, skill_path)
    entry_file = meta.get('entry_file')

    print(f"\n🚀 正在运行技能: {skill_id} (action={action})")
    print(f"   路径: {skill_path}")

    if not entry_file:
        print(f"⚠️  技能 '{skill_id}' 无 Python 入口文件。")
        print(f"   这是一个纯指令集技能 (SKILL.md only)，仅支持 AI 调用。")
        print(f"   如需独立运行，请在技能目录下添加 main.py 或 __init__.py。")
        return False

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

        print(json.dumps(result, ensure_ascii=False, indent=2) if len(json.dumps(result, ensure_ascii=False)) > 100 else str(result))
    elif isinstance(result, str):
        print(result)
    else:
        print(str(result))


def main():
    parser = argparse.ArgumentParser(
        prog="butler skill",
        description="🛠️  技能独立运行器 - 让 One Folder = One Skill 真正独立可用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python butler_cli.py skill list
  python butler_cli.py skill info butler_expert
  python butler_cli.py skill run butler_expert
  python butler_cli.py skill run butler_expert ask --query 架构
  python butler_cli.py skill run format_convert run --input test.md --to DOCX
        """
    )

    subparsers = parser.add_subparsers(dest="action", help="子命令")

    subparsers.add_parser("list", help="列出所有可用技能")

    run_parser = subparsers.add_parser("run", help="运行指定技能")
    run_parser.add_argument("skill_id", help="技能 ID (文件夹名)")
    run_parser.add_argument("skill_action", nargs="?", default="run", help="技能动作 (默认: run)")
    run_parser.add_argument("params", nargs=argparse.REMAINDER, help="参数 (格式: --key value)")

    info_parser = subparsers.add_parser("info", help="查看技能详情")
    info_parser.add_argument("skill_id", help="技能 ID (文件夹名)")

    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()

    if args.action == "list":
        list_skills()
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