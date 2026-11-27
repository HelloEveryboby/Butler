# -*- coding: utf-8 -*-
"""交互式 AI 提供商配置命令 (`butler config`).

在终端中以问答方式选择 AI 服务商、填写 API 地址/模型/密钥，
并持久化写入 .env。与 GUI 向导、安装脚本共享同一套 PROVIDER_DEFAULTS。
"""
import os
import re
import sys
import json
import getpass
from pathlib import Path

from dotenv import set_key, load_dotenv

from butler.core import api_keys
from butler.core.config_model import PROVIDER_DEFAULTS, PROVIDER_KEY_PATHS


# 终端配色
_CY = "\033[36m"
_GR = "\033[32m"
_YE = "\033[33m"
_BD = "\033[1m"
_NC = "\033[0m"


def _env_path() -> Path:
    return api_keys.env_file()


def _show_current():
    """打印当前 .env 中的 AI 提供商配置状态。"""
    env = _env_path()
    if not env.exists():
        print(f"{_YE}未检测到 .env 文件，将创建新文件。{_NC}\n")
        return
    load_dotenv(env, override=True)

    provider = os.getenv("AI_PROVIDER", "deepseek") or "deepseek"
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["deepseek"])
    label = os.getenv("CUSTOM_PROVIDER_NAME", "") or ""
    base_url = os.getenv("API_BASE_URL", "") or defaults["base_url"]
    model = os.getenv("MODEL_NAME", "") or defaults["model_name"]
    key_env = defaults["key_env"]
    key_val = os.getenv(key_env, "") or ""
    masked = (key_val[:4] + "***" + key_val[-4:]) if len(key_val) > 10 else ("***" if key_val else "未配置")

    name = f"{defaults['display_name']}" + (f"（{label}）" if label else "")
    print(f"{_BD}─── 当前 AI 配置 ───{_NC}")
    print(f"  提供商    : {provider}  ({name})")
    print(f"  API 地址  : {base_url}")
    print(f"  模型      : {model}")
    print(f"  密钥变量  : {key_env} = {masked}")
    print()


def _pick_provider() -> str:
    """交互选择提供商，返回 provider id。"""
    print(f"{_BD}请选择 AI 模型服务商：{_NC}")
    items = list(PROVIDER_DEFAULTS.items())
    for idx, (pid, cfg) in enumerate(items, 1):
        tag = "（需自定义地址）" if pid == "custom" else ""
        print(f"  {idx}) {cfg['display_name']} {tag}")
    while True:
        choice = input(f"请输入编号 [1-{len(items)}，默认 1]: ").strip() or "1"
        try:
            idx = int(choice)
            if 1 <= idx <= len(items):
                return items[idx - 1][0]
        except ValueError:
            pass
        print(f"{_YE}无效输入，请重试。{_NC}")


def _check_config():
    """配置健康检查：文件清单、重复键冲突、密钥缺失（butler config check）。"""
    from butler.core.errors import format_error

    root = Path(__file__).resolve().parent.parent.parent
    cfg_dir = root / "config"
    print(f"{_BD}─── 配置健康检查 ───{_NC}")

    # ① 配置文件清单与职责
    files = [
        (root / ".env", "密钥与服务商选择（唯一密钥源）"),
        (cfg_dir / "config.yaml", "行为配置（权威源）"),
        (cfg_dir / "settings.yaml", "历史遗留配置（待合并，勿新增键）"),
        (cfg_dir / "system_config.json", "系统内部配置"),
        (cfg_dir / "portable_config.json", "便携模式配置"),
    ]
    print(f"  📁 配置文件清单:")
    for f, role in files:
        mark = "✅" if f.exists() else "—"
        print(f"     {mark} {f.relative_to(root)}  {role}")

    # ② 重复键检测：config.yaml vs settings.yaml（历史上同键双写）
    conflicts = []
    c1, c2 = cfg_dir / "config.yaml", cfg_dir / "settings.yaml"
    if c1.exists() and c2.exists():
        try:
            import yaml  # PyYAML（项目依赖，缺失时降级为跳过）

            def _flat(d, prefix=""):
                out = set()
                if isinstance(d, dict):
                    for k, v in d.items():
                        key = f"{prefix}.{k}" if prefix else str(k)
                        if isinstance(v, dict):
                            out |= _flat(v, key)
                        else:
                            out.add(key)
                return out

            k1 = _flat(yaml.safe_load(c1.read_text(encoding="utf-8")) or {})
            k2 = _flat(yaml.safe_load(c2.read_text(encoding="utf-8")) or {})
            conflicts = sorted(k1 & k2)
        except Exception as e:
            print(f"  {_YE}⚠️ 跳过重复键检测（YAML 解析不可用）: {e}{_NC}")

    print(f"\n  🔍 重复键冲突 (config.yaml ∩ settings.yaml):")
    if conflicts:
        for k in conflicts:
            print(f"     ⚠️ {k}")
        print(f"     {_YE}处理原则：一律以 config.yaml 为准；settings.yaml 中的同名键将被忽略。{_NC}")
    else:
        print("     ✅ 无冲突")

    # ③ 密钥状态
    print(f"\n  🔑 AI 密钥状态:")
    env = _env_path()
    if not env.exists():
        print("     ❌ 未找到 .env")
    else:
        load_dotenv(env, override=True)
        provider = os.getenv("AI_PROVIDER", "deepseek") or "deepseek"
        defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["deepseek"])
        key_env = defaults["key_env"]
        key_val = os.getenv(key_env, "") or ""
        if key_val and "YOUR_" not in key_val:
            print(f"     ✅ {key_env} 已配置（{defaults['display_name']}）")
        else:
            print(f"     ❌ {key_env} 未配置")

    # ④ 下一步建议
    fixes = []
    if not (root / ".env").exists():
        fixes.append(".env 缺失 → 运行 butler init（3 分钟配置向导）")
    if conflicts:
        fixes.append("配置文件重复键 → 以 config.yaml 为准，清理 settings.yaml 同名键（或删除 settings.yaml 中已废弃段落）")
    if not (root / ".env").exists() or not key_val or "YOUR_" in key_val:
        fixes.append("AI 密钥未配置 → 运行 butler init 或 butler config")

    print(f"\n{_BD}🔧 下一步建议:{_NC}")
    if fixes:
        for i, f in enumerate(fixes, 1):
            print(f"   {i}. {f}")
    else:
        print("   ✅ 配置健康。可随时用 butler config 重新配置、butler config show 查看。")


def _print_keys():
    """打印全部服务的密钥状态（分组、脱敏、来源）。"""
    rows = api_keys.status()
    print(f"{_BD}─── API Key 配置状态 ───{_NC}")
    print(f"  文件: {api_keys.env_file()}")
    for group, label in api_keys.GROUP_LABELS.items():
        group_rows = [r for r in rows if r["group"] == group]
        if not group_rows:
            continue
        print(f"\n  [{label}]")
        for r in group_rows:
            mark = "✅" if r["configured"] else "—"
            source = f" ({r['source']})" if r["source"] != "-" else ""
            print(f"     {mark} {r['service']:<14} {r['env']:<22} {r['masked']}{source}")
    print(f"\n  设置: {_CY}butler config set <服务> [密钥]{_NC}   "
          f"删除: {_CY}butler config remove <服务>{_NC}   "
          f"切换: {_CY}butler config use <服务商>{_NC}")


def _set_key(args):
    """butler config set <服务> [密钥]；省略密钥时隐藏输入。"""
    if not args:
        print(f"{_YE}用法: butler config set <服务> [密钥]{_NC}")
        print("可用服务: " + ", ".join(sorted(api_keys.SERVICE_KEYS)))
        return
    service = args[0]
    value = args[1] if len(args) > 1 else getpass.getpass(
        f"输入 {service} 的密钥（隐藏）: ").strip()
    try:
        env_name, masked = api_keys.set_key_value(service, value)
    except KeyError as e:
        print(f"{_YE}{e}{_NC}")
        return
    except ValueError as e:
        print(f"{_YE}{e}{_NC}")
        return
    print(f"{_GR}✅ 已写入 {env_name} = {masked}  ({api_keys.env_file()}){_NC}")


def _remove_key(args):
    """butler config remove <服务>"""
    if not args:
        print(f"{_YE}用法: butler config remove <服务>{_NC}")
        return
    try:
        env_name = api_keys.remove_key_value(args[0])
    except KeyError as e:
        print(f"{_YE}{e}{_NC}")
        return
    print(f"{_GR}✅ 已删除 {env_name}{_NC}")


def _use_provider(args):
    """butler config use <服务商> [--model M] [--base-url URL]：切换 AI_PROVIDER。"""
    if not args:
        print(f"{_YE}用法: butler config use <服务商> [--model <模型/接入点>] [--base-url <URL>]{_NC}")
        print("可选: " + ", ".join(PROVIDER_DEFAULTS))
        return
    provider_name = None
    model = base_url = label = None
    i = 0
    while i < len(args):
        item = args[i]
        if item in ("--model", "-m") and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif item in ("--base-url", "-b") and i + 1 < len(args):
            base_url = args[i + 1]
            i += 2
        elif item in ("--name", "-n") and i + 1 < len(args):
            label = args[i + 1]
            i += 2
        else:
            if provider_name is None:
                provider_name = item
            i += 1
    try:
        provider = api_keys.use_provider(provider_name or "")
    except KeyError as e:
        print(f"{_YE}{e}{_NC}")
        return
    if model:
        api_keys.set_env_var("MODEL_NAME", model)
    if base_url:
        api_keys.set_env_var("API_BASE_URL", base_url)
    if label is not None:
        api_keys.set_env_var("CUSTOM_PROVIDER_NAME", label)
    display = label or PROVIDER_DEFAULTS.get(provider, {}).get("display_name", provider)
    print(f"{_GR}✅ 当前 AI 提供商已切换为: {provider}（{display}）{_NC}")
    if model:
        print(f"   模型: {model}")
    if base_url:
        print(f"   地址: {base_url}")
    if label:
        print(f"   自定义名称: {label}")
    api_keys.load_env()
    if not os.getenv(api_keys.SERVICE_KEYS[provider][0]):
        print(f"{_YE}⚠️ 尚未配置 {api_keys.SERVICE_KEYS[provider][0]}，"
              f"可运行: butler config set {provider} <密钥>{_NC}")


_URL_HINTS = (
    ("ark.cn-beijing.volces.com", "ark"),
    ("volces.com", "ark"),
    ("api.deepseek.com", "deepseek"),
    ("api.openai.com", "openai"),
    ("bigmodel.cn", "zhipu"),
    ("anthropic.com", "anthropic"),
    ("generativelanguage.googleapis.com", "gemini"),
    ("dashscope.aliyuncs.com", "dashscope"),
    ("qianfan.baidubce.com", "qianfan"),
    ("localhost", "ollama"),
    ("127.0.0.1", "ollama"),
)
_MODEL_HINTS = (
    ("ep-", "ark"), ("doubao", "ark"),
    ("deepseek", "deepseek"), ("gpt-", "openai"), ("claude", "anthropic"),
    ("gemini", "gemini"), ("glm", "zhipu"), ("qwen", "dashscope"),
    ("ernie", "qianfan"), ("llama", "ollama"),
)
_MODEL_LIKE = re.compile(r"^(ep-|gpt-|claude-|gemini-|qwen|glm|ernie|doubao|llama)", re.I)


def _detect_provider(base_url: str = "", model: str = "") -> str:
    """根据地址/模型推断提供商 id。"""
    url = (base_url or "").lower()
    for marker, provider in _URL_HINTS:
        if marker in url:
            return provider
    name = (model or "").lower()
    for marker, provider in _MODEL_HINTS:
        if name.startswith(marker) or marker in name:
            return provider
    return ""


def _parse_paste(text: str) -> dict:
    """从粘贴文本中提取 key / base_url / model / provider / name。"""
    text = (text or "").strip()
    found = {"key": "", "service": "", "base_url": "", "model": "",
             "provider": "", "name": ""}
    if not text:
        return found

    # ① JSON
    if text.startswith("{"):
        try:
            data = json.loads(text)
            found["key"] = str(data.get("api_key") or data.get("key") or data.get("token") or "")
            found["base_url"] = str(data.get("base_url") or data.get("endpoint") or "")
            found["model"] = str(data.get("model") or "")
            found["provider"] = str(data.get("provider") or "")
            found["name"] = str(data.get("name") or data.get("label") or "")
            if found["key"]:
                return found
        except Exception:  # noqa: BLE001
            pass

    # ② KEY=VALUE / 控制台 "API Key: xxx" 形式
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        m = re.match(r"^([A-Z][A-Z0-9_]+)\s*=\s*(.+)$", line)
        if m:
            env_name, value = m.group(1), m.group(2).strip().strip("'\"")
            service = api_keys.resolve_service(env_name)
            if service:
                found["service"] = service
                if not found["key"]:
                    found["key"] = value
            elif env_name == "AI_PROVIDER":
                found["provider"] = value
            elif env_name == "API_BASE_URL":
                found["base_url"] = value
            elif env_name == "MODEL_NAME":
                found["model"] = value
            elif env_name == "CUSTOM_PROVIDER_NAME":
                found["name"] = value
    if found["key"]:
        return found

    m = re.search(r"(?i)\b(?:api[_ ]?key|secret[_ ]?key|access[_ ]?key)\b\s*[:=]\s*['\"]?([A-Za-z0-9\-_\.]{8,})", text)
    if m:
        found["key"] = m.group(1)
    m = re.search(r"(?i)\b(?:base[_ ]?url|endpoint)\b\s*[:=]\s*['\"]?(https?://[^\s'\"]+)", text)
    if m:
        found["base_url"] = m.group(1)
    m = re.search(r"(?i)\bmodel\b\s*[:=]\s*['\"]?([A-Za-z0-9\-_\./]+)", text)
    if m:
        found["model"] = m.group(1)
    if not found["key"]:
        m = re.search(r"(?i)bearer\s+([A-Za-z0-9\-_\.]{8,})", text)
        if m:
            found["key"] = m.group(1)
    if not found["base_url"]:
        m = re.search(r"https?://[^\s'\"]+", text)
        if m:
            found["base_url"] = m.group(0).rstrip("\\'\"")
    if not found["model"]:
        m = re.search(r'"model"\s*:\s*"([^"]+)"', text)
        if m:
            found["model"] = m.group(1)
    if not found["key"]:
        # ③ 裸 Key：找到第一个既不像 URL/模型、又不是纯数字的长令牌
        for token in re.findall(r"[A-Za-z0-9\-_\.]{16,}", text):
            if token.startswith("http") or _MODEL_LIKE.match(token) or token.isdigit():
                continue
            found["key"] = token
            break
    return found


def _normalize_base_url(url: str) -> str:
    """把完整接口地址收敛为 base_url（去掉 /chat/completions 等后缀）。"""
    url = (url or "").strip().rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/embeddings"):
        if url.endswith(suffix):
            url = url[:-len(suffix)]
    return url.rstrip("/")


def _cmd_paste(args):
    """butler config paste [服务商]：粘贴一次即可完成配置。"""
    hint_provider = args[0] if args else ""
    if sys.stdin.isatty():
        print(f"{_BD}请粘贴 API Key / 配置内容（支持裸 Key、KEY=VALUE、JSON、curl），回车结束：{_NC}")
        text = input()
    else:
        text = sys.stdin.read()

    parsed = _parse_paste(text)
    if not parsed["key"]:
        print(f"{_YE}未能从粘贴内容中识别到 API Key，请检查后重试。{_NC}")
        return

    provider = (parsed["provider"] or hint_provider
                or _detect_provider(parsed["base_url"], parsed["model"]))
    if not provider:
        # 无法从内容推断时：沿用当前已配置的服务商，否则按自定义处理
        api_keys.load_env()
        provider = os.getenv("AI_PROVIDER", "") or "custom"
    service = parsed["service"] or provider or "custom"

    try:
        if provider:
            api_keys.use_provider(provider)
        if parsed["base_url"]:
            parsed["base_url"] = _normalize_base_url(parsed["base_url"])
            api_keys.set_env_var("API_BASE_URL", parsed["base_url"])
        if parsed["model"]:
            api_keys.set_env_var("MODEL_NAME", parsed["model"])
        if parsed["name"]:
            api_keys.set_env_var("CUSTOM_PROVIDER_NAME", parsed["name"])
        env_name, masked = api_keys.set_key_value(service, parsed["key"])
    except (KeyError, ValueError) as e:
        print(f"{_YE}{e}{_NC}")
        return

    print(f"{_GR}✅ 配置完成（{api_keys.env_file()}）{_NC}")
    if provider:
        print(f"   提供商: {provider}")
    print(f"   密钥  : {env_name} = {masked}")
    if parsed["base_url"]:
        print(f"   地址  : {parsed['base_url']}")
    if parsed["model"]:
        print(f"   模型  : {parsed['model']}")
    if parsed["name"]:
        print(f"   名称  : {parsed['name']}")


def run_config(rest=""):
    """运行配置命令。

    - 无参数：交互式向导
    - show / check：查看当前配置 / 配置健康检查
    - list / set / remove / use：统一 API Key 管理
    """
    args = [rest] if isinstance(rest, str) else list(rest or [])
    action = args[0] if args else ""
    tail = args[1:]

    if action == "list":
        _print_keys()
        return
    if action == "set":
        _set_key(tail)
        return
    if action in ("remove", "unset", "delete"):
        _remove_key(tail)
        return
    if action == "use":
        _use_provider(tail)
        return
    if action == "paste":
        _cmd_paste(tail)
        return

    env = _env_path()
    # 确保 .env 存在
    if not env.exists():
        env.parent.mkdir(parents=True, exist_ok=True)
        env.touch()
    load_dotenv(env, override=True)

    if action == "show":
        _show_current()
        return

    if action == "check":
        _check_config()
        return

    if not sys.stdin.isatty():
        print("非交互环境：请改用 butler config list / set / remove / use / show / check")
        return

    _show_current()

    # ① 选择服务商
    provider = _pick_provider()
    defaults = PROVIDER_DEFAULTS[provider]
    print(f"\n{_GR}已选择: {defaults['display_name']}{_NC}\n")

    # ② 自定义地址/模型/名称（custom 必填，其它可选覆盖）
    custom_name = ""
    if provider == "custom":
        custom_name = input("🏷️  自定义名称（用于区分，例如 我的Ollama）: ").strip()
        base_url = input("🌐 API 基础地址 (例如 http://localhost:11434/v1): ").strip()
        while not base_url:
            print(f"{_YE}API 地址不能为空。{_NC}")
            base_url = input("🌐 API 基础地址: ").strip()
        model_name = input("📋 模型名称 (例如 qwen2.5:7b): ").strip()
        while not model_name:
            print(f"{_YE}模型名称不能为空。{_NC}")
            model_name = input("📋 模型名称: ").strip()
    else:
        base_url = ""
        model_name = ""
        override = input(f"是否覆盖默认地址/模型？(默认 {defaults['base_url']} / {defaults['model_name']}) [y/N]: ").strip().lower()
        if override == "y":
            base_url = input("🌐 API 基础地址 (留空用默认): ").strip()
            model_name = input("📋 模型名称 (留空用默认): ").strip()

    # ③ 输入密钥
    key_env = defaults["key_env"]
    existing_key = os.getenv(key_env, "") or ""
    hint = f"（当前: {existing_key[:4]}***，直接回车保留）" if existing_key and "YOUR_" not in existing_key else ""
    print(f"\n{_BD}🔑 请输入 {defaults['display_name']} API Key{hint}：{_NC}")
    api_key = getpass.getpass("(输入内容将被隐藏): ").strip()
    if not api_key and existing_key and "YOUR_" not in existing_key:
        api_key = existing_key

    # ④ 写入 .env
    set_key(str(env), "AI_PROVIDER", provider)
    set_key(str(env), "API_BASE_URL", base_url)
    set_key(str(env), "MODEL_NAME", model_name)
    set_key(str(env), "CUSTOM_PROVIDER_NAME", custom_name)
    set_key(str(env), key_env, api_key)

    # ⑤ 确认
    print(f"\n{_GR}✅ 配置已保存到 {env}{_NC}")
    display = custom_name or defaults["display_name"]
    print(f"  AI_PROVIDER        = {provider}")
    print(f"  显示名称           = {display}")
    if base_url:
        print(f"  API_BASE_URL       = {base_url}")
    if model_name:
        print(f"  MODEL_NAME         = {model_name}")
    print(f"  {key_env} = {'***已设置***' if api_key else '(空)'}")
    print(f"\n运行 {_CY}butler config show{_NC} 可随时查看当前配置。")
