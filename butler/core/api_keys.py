# -*- coding: utf-8 -*-
"""统一 API Key 注册表与读写工具。

- 注册表：把 AI 服务商（PROVIDER_KEY_PATHS）与语音/内部 Token 统一成
  ``service -> (环境变量名, 展示名, 分组)``，供 CLI / GUI / 文档共用。
- 读写：默认写入项目根目录 ``.env``（可用 ``BUTLER_ENV_FILE`` 覆盖），
  写入后同步更新当前进程环境变量。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import dotenv_values, load_dotenv, set_key, unset_key

from butler.core.config_model import PROVIDER_DEFAULTS, PROVIDER_KEY_PATHS

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def env_file() -> Path:
    """当前使用的 .env 路径（支持 BUTLER_ENV_FILE 覆盖，便于多环境/测试）。"""
    override = os.getenv("BUTLER_ENV_FILE")
    return Path(override) if override else PROJECT_ROOT / ".env"


# service -> (env_name, display_name, group)
SERVICE_KEYS: Dict[str, Tuple[str, str, str]] = {
    service: (env_name, PROVIDER_DEFAULTS[service]["display_name"], "ai")
    for service, (_path, env_name, _field) in PROVIDER_KEY_PATHS.items()
}

SERVICE_KEYS.update({
    # 语音服务
    "baidu_app_id": ("BAIDU_APP_ID", "百度语音 App ID", "voice"),
    "baidu": ("BAIDU_API_KEY", "百度语音 API Key", "voice"),
    "baidu_secret": ("BAIDU_SECRET_KEY", "百度语音 Secret Key", "voice"),
    "picovoice": ("PICOVOICE_ACCESS_KEY", "Picovoice AccessKey", "voice"),
    # 内部凭据
    "runner_token": ("BUTLER_RUNNER_TOKEN", "Runner 节点 Token", "internal"),
    "api_token": ("BUTLER_API_TOKEN", "REST API Token", "internal"),
})

GROUP_LABELS = {
    "ai": "AI 模型服务商",
    "voice": "语音服务（可选）",
    "internal": "内部凭据",
}

# 常见别名 → 服务 id（方便按中文/厂商名配置）
SERVICE_ALIASES = {
    "方舟": "ark",
    "火山": "ark",
    "火山方舟": "ark",
    "fangzhou": "ark",
    "volcengine": "ark",
    "volc": "ark",
    "huoshan": "ark",
    "doubao": "ark",
    "豆包": "ark",
}


def resolve_service(name: str) -> Optional[str]:
    """把用户输入解析为服务 id：支持 id、环境变量名（大小写不敏感）。"""
    if not name:
        return None
    key = name.strip()
    if key in SERVICE_KEYS:
        return key
    lowered = key.lower()
    if lowered in SERVICE_ALIASES:
        return SERVICE_ALIASES[lowered]
    for service, (env_name, _label, _group) in SERVICE_KEYS.items():
        if env_name.lower() == lowered:
            return service
    return None


def mask(value: str) -> str:
    """密钥脱敏显示。"""
    if not value:
        return "未配置"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}***{value[-4:]}"


def _is_placeholder(value: str) -> bool:
    return not value or "YOUR_" in value


def status(path: Optional[Path] = None) -> List[Dict[str, object]]:
    """返回全部服务的密钥配置状态（不含明文）。"""
    path = path or env_file()
    file_values = dotenv_values(path) if path.exists() else {}
    rows: List[Dict[str, object]] = []
    for service, (env_name, label, group) in SERVICE_KEYS.items():
        env_val = os.getenv(env_name, "")
        file_val = file_values.get(env_name, "") or ""
        value = env_val or file_val
        source = "-"
        if not _is_placeholder(value):
            source = "env" if env_val else ".env"
        rows.append({
            "service": service,
            "env": env_name,
            "label": label,
            "group": group,
            "configured": not _is_placeholder(value),
            "masked": mask(value),
            "source": source,
        })
    return rows


def set_key_value(service: str, value: str, path: Optional[Path] = None) -> Tuple[str, str]:
    """写入密钥到 .env，并同步当前进程环境变量。返回 (env_name, 脱敏值)。"""
    service_id = resolve_service(service)
    if service_id is None:
        raise KeyError(f"未知服务: {service}")
    value = (value or "").strip()
    if not value:
        raise ValueError("密钥不能为空。")
    env_name = SERVICE_KEYS[service_id][0]
    path = path or env_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    set_key(str(path), env_name, value)
    os.environ[env_name] = value
    return env_name, mask(value)


def remove_key_value(service: str, path: Optional[Path] = None) -> str:
    """从 .env 删除密钥，并清除当前进程环境变量。返回环境变量名。"""
    service_id = resolve_service(service)
    if service_id is None:
        raise KeyError(f"未知服务: {service}")
    env_name = SERVICE_KEYS[service_id][0]
    path = path or env_file()
    if path.exists():
        unset_key(str(path), env_name)
    os.environ.pop(env_name, None)
    return env_name


def set_env_var(name: str, value: str, path: Optional[Path] = None) -> None:
    """写入任意环境变量到 .env（如 MODEL_NAME / API_BASE_URL）。"""
    path = path or env_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    set_key(str(path), name, value)
    os.environ[name] = value


def use_provider(service: str, path: Optional[Path] = None) -> str:
    """切换当前 AI 提供商（写 AI_PROVIDER），返回 provider id。"""
    service_id = resolve_service(service)
    if service_id not in PROVIDER_DEFAULTS:
        raise KeyError(f"不是 AI 服务商: {service}")
    path = path or env_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)
    set_key(str(path), "AI_PROVIDER", service_id)
    os.environ["AI_PROVIDER"] = service_id
    return service_id


def load_env(path: Optional[Path] = None) -> None:
    """加载 .env 到当前进程（override=True，保证最新值生效）。"""
    path = path or env_file()
    if path.exists():
        load_dotenv(path, override=True)
