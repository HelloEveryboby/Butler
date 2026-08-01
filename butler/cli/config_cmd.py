# -*- coding: utf-8 -*-
"""交互式 AI 提供商配置命令 (`butler config`).

在终端中以问答方式选择 AI 服务商、填写 API 地址/模型/密钥，
并持久化写入 .env。与 GUI 向导、安装脚本共享同一套 PROVIDER_DEFAULTS。
"""
import os
import getpass
from pathlib import Path

from dotenv import set_key, load_dotenv

from butler.core.config_model import PROVIDER_DEFAULTS, PROVIDER_KEY_PATHS


# 终端配色
_CY = "\033[36m"
_GR = "\033[32m"
_YE = "\033[33m"
_BD = "\033[1m"
_NC = "\033[0m"


def _env_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / ".env"


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


def run_config(subaction: str = ""):
    """运行交互式配置向导。

    Args:
        subaction: 可选子命令。`show` 仅显示当前配置。
    """
    env = _env_path()
    # 确保 .env 存在
    if not env.exists():
        env.parent.mkdir(parents=True, exist_ok=True)
        env.touch()
    load_dotenv(env, override=True)

    if subaction == "show":
        _show_current()
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
