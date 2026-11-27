# -*- coding: utf-8 -*-
"""统一 API Key 注册表与读写工具。

- 注册表：把 AI 服务商（PROVIDER_KEY_PATHS）与语音/内部 Token 统一成
  ``service -> (环境变量名, 展示名, 分组)``，供 CLI / GUI / 文档共用。
- 读写：默认写入项目根目录 ``.env``（可用 ``BUTLER_ENV_FILE`` 覆盖），
  写入后同步更新当前进程环境变量。
"""
from __future__ import annotations

import json
import os
import re
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


# ---------------------------------------------------------------------------
# 粘贴内容解析（CLI / HTTP 配置界面共用）
# ---------------------------------------------------------------------------
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


def detect_provider(base_url: str = "", model: str = "") -> str:
    """根据地址/模型推断提供商 id，无法判断时返回空串。"""
    url = (base_url or "").lower()
    for marker, provider in _URL_HINTS:
        if marker in url:
            return provider
    name = (model or "").lower()
    for marker, provider in _MODEL_HINTS:
        if name.startswith(marker) or marker in name:
            return provider
    return ""


def normalize_base_url(url: str) -> str:
    """把完整接口地址收敛为 base_url（去掉 /chat/completions 等后缀）。"""
    url = (url or "").strip().rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/embeddings"):
        if url.endswith(suffix):
            url = url[:-len(suffix)]
    return url.rstrip("/")


def parse_paste(text: str) -> Dict[str, str]:
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
            service = resolve_service(env_name)
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


def apply_paste(text: str, hint_provider: str = "") -> Dict[str, str]:
    """解析粘贴内容并写入 .env，返回结果摘要；无法识别 Key 时抛 ValueError。"""
    parsed = parse_paste(text)
    if not parsed["key"]:
        raise ValueError("未能从粘贴内容中识别到 API Key")

    provider = (parsed["provider"] or hint_provider
                or detect_provider(parsed["base_url"], parsed["model"]))
    if not provider:
        # 无法从内容推断时：沿用当前已配置的服务商，否则按自定义处理
        load_env()
        provider = os.getenv("AI_PROVIDER", "") or "custom"
    service = parsed["service"] or provider or "custom"

    if provider:
        use_provider(provider)
    if parsed["base_url"]:
        parsed["base_url"] = normalize_base_url(parsed["base_url"])
        set_env_var("API_BASE_URL", parsed["base_url"])
    if parsed["model"]:
        set_env_var("MODEL_NAME", parsed["model"])
    if parsed["name"]:
        set_env_var("CUSTOM_PROVIDER_NAME", parsed["name"])

    env_name, masked = set_key_value(service, parsed["key"])
    return {
        "provider": provider,
        "service": service,
        "env": env_name,
        "masked": masked,
        "base_url": parsed["base_url"],
        "model": parsed["model"],
        "name": parsed["name"],
    }
