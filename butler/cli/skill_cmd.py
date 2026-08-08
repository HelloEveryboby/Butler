# -*- coding: utf-8 -*-
import os
import sys
import json
import importlib
import importlib.util
import argparse
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("SkillCLI")

IS_TTY = sys.stdout.isatty()
HAS_COLOR = IS_TTY and not os.environ.get("NO_COLOR")
TERM_WIDTH = shutil.get_terminal_size((120, 24)).columns


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_GRAY = "\033[100m"


def _c(text: str, *codes: str) -> str:
    if not HAS_COLOR:
        return text
    return "".join(codes) + text + C.RESET


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


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 1] + "…"


# ── Linux-style commands ──────────────────────────────────────────

def cmd_list(args) -> int:
    all_skills = _collect_all_skills()

    if getattr(args, 'type', None) == 'user':
        filtered = [(s, p, m) for s, p, m in all_skills if m.get('access_level') == 'user']
    elif getattr(args, 'type', None) == 'agent':
        filtered = [(s, p, m) for s, p, m in all_skills if m.get('access_level') == 'agent']
    else:
        filtered = all_skills

    if getattr(args, 'format', False):
        output = []
        for sid, path, meta in filtered:
            output.append({
                'id': sid,
                'name': meta.get('name', sid),
                'version': meta.get('version', ''),
                'description': meta.get('description', ''),
                'access_level': meta.get('access_level', 'agent'),
                'path': str(path),
            })
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    if not filtered:
        label = {"user": "可调用", "agent": "Agent"}.get(getattr(args, 'type', None), '')
        print(_c("⚠ 未发现任何" + label + "技能。", C.YELLOW))
        return 0

    user_skills = [(s, p, m) for s, p, m in filtered if m.get('access_level') == 'user']
    agent_skills = [(s, p, m) for s, p, m in filtered if m.get('access_level') == 'agent']

    if getattr(args, 'quiet', False):
        for sid, _, _ in filtered:
            print(sid)
        return 0

    if getattr(args, 'long', False):
        return _list_long(user_skills, agent_skills)

    return _list_table(user_skills, agent_skills)


def _list_table(user_skills, agent_skills) -> int:
    col_id = max(max(len(s) for s, _, _ in user_skills + agent_skills) if user_skills or agent_skills else [0], 20)
    col_id = min(col_id, 30)
    col_ver = 8
    col_desc = max(20, TERM_WIDTH - col_id - col_ver - 18)

    print(_c("One Folder = One Skill  |  Butler 技能注册中心", C.BOLD, C.CYAN))
    print()

    if user_skills:
        tag = _c("USER", C.BG_GREEN, C.WHITE)
        print(f"  {tag}  {_c('可调用技能 - 用户可直接使用', C.BOLD)}")
        print(f"  {'─' * (TERM_WIDTH - 4)}")
        for sid, path, meta in user_skills:
            ver = _truncate(str(meta.get('version', '')), col_ver)
            desc = _truncate(meta.get('description', '无描述'), col_desc)
            actions = meta.get('actions', [])
            action_str = _c(" [" + ",".join(actions) + "]", C.CYAN) if actions else ""
            print(f"  {_c('🐍', C.GREEN)}  {_c(_truncate(sid, col_id), C.BOLD)}  {_c(ver, C.DIM)}  {desc}{action_str}")
        print()

    if agent_skills:
        tag = _c("AGENT", C.BG_BLUE, C.WHITE)
        print(f"  {tag}  {_c('Agent 技能 - 仅供 AI 大模型使用', C.BOLD)}")
        print(f"  {'─' * (TERM_WIDTH - 4)}")
        for sid, path, meta in agent_skills:
            ver = _truncate(str(meta.get('version', '')), col_ver)
            desc = _truncate(meta.get('description', '无描述'), col_desc)
            keywords = meta.get('keywords', [])
            kw_str = _c(" [" + ",".join(keywords[:3]) + "]", C.DIM) if keywords else ""
            print(f"  {_c('📖', C.BLUE)}  {_c(_truncate(sid, col_id), C.BOLD)}  {_c(ver, C.DIM)}  {desc}{kw_str}")
        print()

    total = len(user_skills) + len(agent_skills)
    parts = []
    if user_skills:
        parts.append(_c(f"🐍 {len(user_skills)} 可调用", C.GREEN))
    if agent_skills:
        parts.append(_c(f"📖 {len(agent_skills)} Agent", C.BLUE))
    parts.insert(0, str(total))
    summary = "  |  ".join(parts)
    print(f"  {_c('TOTAL', C.DIM)}  {summary}")
    print(f"  {_c('list --help', C.DIM)}  显示更多选项  |  {_c('run <id>', C.DIM)}  运行技能  |  {_c('info <id>', C.DIM)}  查看详情")
    return 0


def _list_long(user_skills, agent_skills) -> int:
    def _print_group(title, color_code, skills, details_fn):
        if not skills:
            return
        print(_c(f"\n  ╔══ {title} ══╗", color_code, C.BOLD))
        print(_c(f"  ╠{'═' * (TERM_WIDTH - 8)}╣", color_code))
        for sid, path, meta in skills:
            print(_c(f"  ║ ", color_code) + _c(f" {sid} ", C.BOLD) + _c(f" v{meta.get('version', '?')} ", C.DIM))
            for k, v in details_fn(meta):
                if v:
                    print(_c(f"  ║   {k:<10} ", C.DIM) + f"{v}")
            print(_c(f"  ╠{'─' * (TERM_WIDTH - 8)}╣", color_code))
        print()

    _print_group("🐍  可调用技能 (USER)", C.GREEN, user_skills, lambda m: [
        ("名称", m.get('name', '')),
        ("描述", m.get('description', '')),
        ("动作", ", ".join(m.get('actions', []))),
        ("入口", m.get('entry_file', '')),
        ("路径", m.get('path', '')),
    ])

    _print_group("📖  Agent 技能 (AGENT)", C.BLUE, agent_skills, lambda m: [
        ("名称", m.get('name', '')),
        ("描述", m.get('description', '')),
        ("关键词", ", ".join(m.get('keywords', []))),
        ("格式", m.get('format', '')),
        ("路径", m.get('path', '')),
    ])

    total = len(user_skills) + len(agent_skills)
    print(f"  {total} 个技能 ({len(user_skills)} 可调用 + {len(agent_skills)} Agent)")
    return 0


def cmd_run(args) -> int:
    skills = _discover_skill_folders()
    skill_id = args.skill_id

    if skill_id not in skills:
        print(_c(f"❌ 技能 '{skill_id}' 未找到", C.RED), file=sys.stderr)
        available = sorted(skills.keys())
        if len(available) <= 10:
            print(f"  可用技能: {', '.join(available)}", file=sys.stderr)
        else:
            print(f"  可用技能 ({len(available)} 个): python butler_cli.py skill list", file=sys.stderr)
        return 1

    skill_path = skills[skill_id]
    meta = _load_skill_metadata(skill_id, skill_path)
    access_level = meta.get('access_level', 'agent')
    action = getattr(args, 'skill_action', 'run') or 'run'

    if access_level == 'agent':
        print(_c(f"\n❌ 技能 '{skill_id}' 是 Agent 技能", C.RED), file=sys.stderr)
        print(f"  类型: {_c('仅 AI 大模型可用', C.DIM)}", file=sys.stderr)
        print(f"  无法直接运行，请通过 AI 对话使用。", file=sys.stderr)
        print(f"  查看指令: {_c(f'python butler_cli.py skill info {skill_id}', C.CYAN)}", file=sys.stderr)
        print(f"  转为手动技能: 在 {skill_path} 中添加 main.py 或 __init__.py", file=sys.stderr)
        return 2

    entry_file = meta.get('entry_file')
    if not entry_file:
        print(_c(f"⚠ 技能 '{skill_id}' 无 Python 入口", C.YELLOW), file=sys.stderr)
        print(f"  这是纯指令集技能 (SKILL.md only)，仅支持 AI 调用。", file=sys.stderr)
        print(f"  如需独立运行，请在技能目录下添加 main.py 或 __init__.py。", file=sys.stderr)
        return 2

    if not getattr(args, 'quiet', False):
        print(_c(f"▶ 运行: {skill_id} (action={action})", C.BOLD, C.GREEN))
        print(_c(f"  路径: {skill_path}", C.DIM))

    extra_params = {}
    raw_params = getattr(args, 'params', None)
    if raw_params:
        i = 0
        while i < len(raw_params):
            arg = raw_params[i]
            if arg.startswith('--'):
                key = arg[2:]
                if i + 1 < len(raw_params) and not raw_params[i + 1].startswith('--'):
                    extra_params[key] = raw_params[i + 1]
                    i += 2
                else:
                    extra_params[key] = True
                    i += 1
            else:
                i += 1

    sys.path.insert(0, str(_get_project_root()))

    result = None
    if not getattr(args, 'iso', False):
        result = _try_run_direct(skill_id, skill_path, entry_file, action, extra_params)

    if result is None:
        result = _try_run_skill_manager(skill_id, action, extra_params)

    if result is None:
        result = _try_run_isolated(skill_id, skill_path, entry_file, action, extra_params)

    if result is None or result is False:
        print(_c(f"❌ 技能运行失败", C.RED), file=sys.stderr)
        return 1

    if isinstance(result, dict) and result.get("status") == "pending_confirmation":
        print(_c(f"⚠ 需要确认: {result.get('message', '')}", C.YELLOW))
        return 0

    if getattr(args, 'format', False) or getattr(args, 'output', None):
        if isinstance(result, (dict, list)):
            output_text = json.dumps(result, ensure_ascii=False, indent=2)
        elif result is None:
            output_text = ""
        else:
            output_text = str(result)
        if getattr(args, 'output', None):
            out_path = args.output
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(output_text)
            print(_c(f"✅ 结果已写入 {out_path}", C.GREEN))
        else:
            print(output_text)
    else:
        _print_result_nice(result)

    return 0


def cmd_info(args) -> int:
    skills = _discover_skill_folders()
    skill_id = args.skill_id

    if skill_id not in skills:
        print(_c(f"❌ 技能 '{skill_id}' 未找到", C.RED), file=sys.stderr)
        print(f"  可用技能: {', '.join(sorted(skills.keys()))}", file=sys.stderr)
        return 1

    skill_path = skills[skill_id]
    meta = _load_skill_metadata(skill_id, skill_path)
    access_level = meta.get('access_level', 'agent')

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

    if getattr(args, 'format', False):
        output = {
            'id': skill_id,
            'name': meta.get('name', skill_id),
            'version': meta.get('version', 'N/A'),
            'author': meta.get('author', 'N/A'),
            'access_level': access_level,
            'description': meta.get('description', '无描述'),
            'path': str(skill_path),
            'entry_file': meta.get('entry_file'),
            'actions': meta.get('actions', []),
            'keywords': meta.get('keywords', []),
            'provides': meta.get('provides', []),
            'requires': meta.get('requires', {}),
            'has_python': meta.get('has_python', False),
            'skill_md_content': contents[:2000] if contents else '',
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0

    print(_c(f"┌─ 技能详情: {skill_id} {'─' * max(0, TERM_WIDTH - 22 - len(skill_id))}", C.BOLD, C.CYAN))

    tag_color = C.GREEN if access_level == 'user' else C.BLUE
    tag_label = "🐍 可调用 (USER)" if access_level == 'user' else "📖 Agent (AGENT)"
    print(f"│  {_c('类型', C.DIM)}: {_c(tag_label, tag_color, C.BOLD)}")

    rows = [
        ("名称", meta.get('name', skill_id)),
        ("版本", meta.get('version', 'N/A')),
        ("作者", meta.get('author', 'N/A')),
        ("格式", meta.get('format', 'unknown')),
        ("描述", meta.get('description', '无描述')),
        ("路径", str(skill_path)),
    ]
    if meta.get('entry_file'):
        rows.append(("入口", meta['entry_file']))
    else:
        rows.append(("入口", _c("(无 Python 入口)", C.DIM)))

    for label, value in rows:
        print(f"│  {_c(f'{label:<8}', C.DIM)} {value}")

    actions = meta.get('actions', [])
    if actions:
        print(f"│  {_c('动作', C.DIM)}   {', '.join(actions)}")

    keywords = meta.get('keywords', [])
    if keywords:
        print(f"│  {_c('关键词', C.DIM)} {', '.join(keywords)}")

    provides = meta.get('provides', [])
    if provides:
        print(f"│  {_c('提供', C.DIM)}   {', '.join(provides)}")

    requires = meta.get('requires', {})
    if requires:
        req_str = json.dumps(requires, ensure_ascii=False)
        print(f"│  {_c('依赖', C.DIM)}   {req_str}")

    if contents:
        preview = contents[:getattr(args, 'preview', 600)]
        print(f"│")
        print(f"│  {_c('SKILL.md 指令预览:', C.BOLD)}")
        for line in preview.split('\n'):
            print(f"│  {line}")
        if len(contents) > len(preview):
            print(f"│  {_c(f'... ({len(contents)} 字符总, 已截断)', C.DIM)}")

    print(f"└{'─' * (TERM_WIDTH - 2)}")

    print()
    if access_level == 'user':
        print(_c("  ▶ 运行", C.GREEN) + f": python butler_cli.py skill run {skill_id} [action]")
        print(_c("  💬 Chat", C.CYAN) + f": /skill {skill_id} [action]")
    else:
        print(_c("  ℹ  ", C.YELLOW) + f" 此技能是 Agent 技能，仅能通过 AI 对话使用。")
        print(f"     AI 会自动读取 SKILL.md 指令来完成任务。")
        print(_c("  🔧 转换", C.BLUE) + f": 在 {skill_path} 中添加 main.py 或 __init__.py")
    return 0


def cmd_run_shell(args) -> int:
    if args.skill_id == 'help':
        _print_man_page()
        return 0
    return cmd_run(args)


def _print_man_page():
    lines = [
        _c("BUTLER-SKILL(1)                    User Commands                   BUTLER-SKILL(1)", C.BOLD),
        "",
        _c("NAME", C.BOLD),
        "     butler skill - Butler 技能管理与运行工具",
        "",
        _c("SYNOPSIS", C.BOLD),
        "     python butler_cli.py skill <command> [options] [args...]",
        "",
        _c("DESCRIPTION", C.BOLD),
        "     Butler 采用 \"One Folder = One Skill\" 架构。每个技能存放在 skills/ 目录下的",
        "     独立文件夹中，支持两种类型:",
        "",
        _c("     🐍 USER 技能", C.GREEN) + "  有 Python 入口 (main.py/__init__.py)，用户可直接调用",
        _c("     📖 AGENT 技能", C.BLUE) + "  纯 SKILL.md 指令集，仅供 AI 大模型使用",
        "",
        _c("COMMANDS", C.BOLD),
        _c("     list, ls", C.CYAN, C.BOLD) + " [-t|--type user|agent] [-l|--long] [-j|--json] [-q|--quiet]",
        "           列出所有技能 (自动区分 USER/AGENT)",
        "",
        _c("     run", C.CYAN, C.BOLD) + " <skill-id> [action] [--key value] [-o output] [-j|--json]",
        "           运行指定的可调用技能 (仅 USER 类型)",
        "",
        _c("     info", C.CYAN, C.BOLD) + " <skill-id> [-j|--json] [-p|--preview N]",
        "           查看技能详情 (含类型标签和 SKILL.md 预览)",
        "",
        _c("OPTIONS", C.BOLD),
        _c("     -t, --type <type>", C.CYAN) + "    过滤技能类型: user 或 agent",
        _c("     -l, --long", C.CYAN) + "          详细列表模式 (显示全部元数据)",
        _c("     -j, --json", C.CYAN) + "          以 JSON 格式输出 (适合脚本处理)",
        _c("     -q, --quiet", C.CYAN) + "        仅输出 ID (适合管道处理)",
        _c("     -o, --output <file>", C.CYAN) + "  输出到文件 (仅 run 命令)",
        _c("     -p, --preview <N>", C.CYAN) + "    SKILL.md 预览字符数 (默认 600)",
        _c("     -h, --help", C.CYAN) + "         显示帮助信息",
        _c("     -v, --verbose", C.CYAN) + "       详细输出",
        "",
        _c("EXIT CODES", C.BOLD),
        "     0   成功",
        "     1   错误 (技能未找到、执行失败)",
        "     2   用法错误 (Agent 技能不可直接运行)",
        "",
        _c("EXAMPLES", C.BOLD),
        "     # 列出所有技能",
        "     python butler_cli.py skill list",
        "",
        "     # 仅显示可调用技能",
        "     python butler_cli.py skill list -t user",
        "",
        "     # JSON 输出 (供脚本使用)",
        "     python butler_cli.py skill list -j",
        "",
        "     # 运行技能",
        "     python butler_cli.py skill run butler_expert ask --query 架构",
        "",
        "     # 查看 Agent 技能指令",
        "     python butler_cli.py skill info wps-office-expert",
        "",
        "     # 管道: 过滤技能列表",
        "     python butler_cli.py skill list -q | grep -i docx",
        "",
        "     # 保存运行结果",
        "     python butler_cli.py skill run format_convert -o result.txt",
        "",
        _c("SEE ALSO", C.BOLD),
        "     butler, butler tui, butler chat",
        "",
    ]
    print("\n".join(lines))


def _print_result_nice(result):
    if result is None:
        print(_c("✅ 技能执行完成，无返回结果。", C.GREEN))
        return

    if isinstance(result, dict):
        status = result.get("status", "")
        if status == "pending_confirmation":
            print(_c(f"⚠ 需要确认: {result.get('message', '')}", C.YELLOW))
            return
        if status == "pending_resource":
            print(_c(f"⏳ 等待资源: {result.get('message', '')}", C.YELLOW))
            return

        output = json.dumps(result, ensure_ascii=False, indent=2)
        if len(output) > 100:
            print(output)
        else:
            print(_c(str(result), C.CYAN))
    elif isinstance(result, str):
        print(result)
    else:
        print(str(result))


def _try_run_direct(skill_id: str, skill_path: Path, entry_file: str, action: str, extra_params: dict) -> Optional[Any]:
    if not entry_file.endswith('.py'):
        return None

    module_name = f"skills.{skill_id}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, entry_file)
        if not spec or not spec.loader:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if hasattr(module, "handle_request"):
            kwargs = {"entities": extra_params or {}}
            return module.handle_request(action, **kwargs)

        if hasattr(module, "main") and callable(module.main):
            kwargs = extra_params or {}
            result = module.main(**kwargs)
            return result if result is not None else True

        if entry_file.endswith("__init__.py") or entry_file.endswith("main.py"):
            print(_c(f"⚠ 技能 '{skill_id}' 缺少 handle_request 或 main 函数", C.YELLOW), file=sys.stderr)
            print(f"   请确保入口文件定义了 handle_request(action, **kwargs) 或 main(**kwargs)。", file=sys.stderr)
            return False

        return None
    except Exception as e:
        logger.debug(f"Direct run failed for {skill_id}: {e}")
        return None


def _try_run_skill_manager(skill_id: str, action: str, extra_params: dict) -> Optional[Any]:
    try:
        from butler.core.skill_manager import SkillManager
        sm = SkillManager()
        sm.load_skills()
        if skill_id not in sm.manifests:
            return None
        kwargs = {"entities": extra_params or {}}
        return sm.execute(skill_id, action, **kwargs)
    except Exception as e:
        logger.debug(f"SkillManager run failed for {skill_id}: {e}")
        return None


def _try_run_isolated(skill_id: str, skill_path: Path, entry_file: str, action: str, extra_params: dict) -> Optional[Any]:
    if not entry_file.endswith('.py'):
        return None

    project_root = str(_get_project_root())
    skill_env = os.environ.copy()
    skill_env["PYTHONPATH"] = f"{project_root}{os.pathsep}{skill_env.get('PYTHONPATH', '')}"

    payload = {"action": action, "kwargs": extra_params or {}}

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
                            return pld
                        elif act == "speak":
                            print(_c(f"🔊 {pld.get('text', '')}", C.CYAN))
                        elif act == "ui_print":
                            print(_c(f"📢 {pld.get('text', '')}", C.DIM))
                        continue
                except (json.JSONDecodeError, ValueError):
                    pass
                stdout_lines.append(line)

        stderr = proc.stderr.read()
        proc.wait()

        if proc.returncode != 0 and stderr:
            print(_c(f"❌ 执行失败 (exit code {proc.returncode}):", C.RED), file=sys.stderr)
            print(stderr, file=sys.stderr)
            return False

        if stdout_lines:
            print("\n".join(stdout_lines))
        else:
            print(_c(f"✅ 技能 '{skill_id}' 执行完成。", C.GREEN))
        return True

    except Exception as e:
        print(_c(f"❌ 启动子进程失败: {e}", C.RED), file=sys.stderr)
        return False


# ── Argparse setup ─────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="butler skill",
        description=_c("Butler 技能管理与运行工具 - Linux 风格命令行", C.BOLD, C.CYAN),
        add_help=False,
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # ── list ──
    p_ls = sub.add_parser("list", add_help=False, aliases=["ls"])
    p_ls.add_argument("-t", "--type", choices=["user", "agent"], default=None)
    p_ls.add_argument("-l", "--long", action="store_true")
    p_ls.add_argument("-j", "--json", action="store_true", dest="format")
    p_ls.add_argument("-q", "--quiet", action="store_true")
    p_ls.add_argument("-h", "--help", action="store_true")
    p_ls.set_defaults(func=cmd_list)

    # ── run ──
    p_run = sub.add_parser("run", add_help=False)
    p_run.add_argument("skill_id")
    p_run.add_argument("skill_action", nargs="?", default="run")
    p_run.add_argument("params", nargs=argparse.REMAINDER)
    p_run.add_argument("-o", "--output", default=None)
    p_run.add_argument("-j", "--json", action="store_true", dest="format")
    p_run.add_argument("--iso", action="store_true", help="跳过直接加载, 强制隔离运行")
    p_run.add_argument("-q", "--quiet", action="store_true")
    p_run.add_argument("-h", "--help", action="store_true")
    p_run.set_defaults(func=cmd_run)

    # ── info ──
    p_info = sub.add_parser("info", add_help=False)
    p_info.add_argument("skill_id")
    p_info.add_argument("-j", "--json", action="store_true", dest="format")
    p_info.add_argument("-p", "--preview", type=int, default=600)
    p_info.add_argument("-h", "--help", action="store_true")
    p_info.set_defaults(func=cmd_info)

    # ── help as subcommand ──
    p_help = sub.add_parser("help", add_help=False)
    p_help.add_argument("skill_id", nargs="?", default=None)
    p_help.set_defaults(func=lambda args: _print_man_page() or 0)

    parser.set_defaults(func=None)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.help:
        _print_man_page()
        return 0

    if not args.command:
        parser.print_help()
        print()
        _print_man_page()
        return 0

    func = getattr(args, 'func', None)
    if func:
        return func(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main() or 0)