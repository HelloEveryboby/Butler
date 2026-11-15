# -*- coding: utf-8 -*-
"""`butler init` — 三分钟首次配置向导。

流程（一个问题一屏，能默认的绝不问）：
    Step 1  选择 AI 服务商（复用 butler config 的交互向导）
    Step 2  填写 API Key（自动做一次轻量连通性校验）
    Step 3  展示「你可以对 Butler 说…」示例任务 + 下一步指引

设计原则：init 不重复造轮子 —— 配置交互复用 config_cmd.run_config，
校验失败输出统一错误码（butler.core.errors）。
"""
import os
import sys
from pathlib import Path

_CY = "\033[36m"
_GR = "\033[32m"
_YE = "\033[33m"
_BD = "\033[1m"
_NC = "\033[0m"

EXAMPLE_TASKS = [
    "把这份 PDF 转成 Word：butler tool run convert --input a.pdf --output a.docx",
    "查一下北京天气：butler weather 北京",
    "让我管理 Excel：对 Butler 说「帮我做一张月度开支表」",
]


def _check_api_key() -> None:
    """对已配置的 Key 做一次轻量连通性校验（尽力而为，绝不阻断）。"""
    import urllib.request
    import json as _json

    from dotenv import load_dotenv
    from butler.core.config_model import PROVIDER_DEFAULTS

    env = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env.exists():
        from butler.core.errors import format_error
        print(format_error("BTL-2002"))
        return
    load_dotenv(env, override=True)

    provider = os.getenv("AI_PROVIDER", "deepseek") or "deepseek"
    defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS.get("deepseek", {}))
    base_url = (os.getenv("API_BASE_URL") or defaults.get("base_url") or "").rstrip("/")
    key_env = defaults.get("key_env", "DEEPSEEK_API_KEY")
    api_key = os.getenv(key_env, "") or ""

    if not api_key or "YOUR_" in api_key:
        from butler.core.errors import format_error
        print(format_error("BTL-2001", detail=f"{key_env} 未配置"))
        return

    print(f"\n{_BD}🔍 正在校验 API 连通性{_NC} ({provider} → {base_url}) ...")
    # OpenAI 兼容接口统一用 /models 探活；Anthropic 用 /v1/models
    url = base_url + "/models"
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "butler-init"}
    if "anthropic" in provider:
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                print(f"{_GR}✅ 连通性校验通过，Key 有效。{_NC}")
            else:
                print(f"{_YE}⚠️ 接口返回 HTTP {resp.status}，请确认 Key/地址配置。{_NC}")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            from butler.core.errors import format_error
            print(format_error("BTL-2001", detail=f"HTTP {e.code}"))
        else:
            print(f"{_YE}⚠️ 接口返回 HTTP {e.code}（服务可达，可能模型名/路径不同，可先继续）。{_NC}")
    except Exception as e:  # 网络不通不阻断流程
        print(f"{_YE}⚠️ 无法连接到 API 地址: {e}")
        print(f"   （可稍后用 butler doctor 排查；本地 Ollama 请确认服务已启动）{_NC}")


def run_init(skip_check: bool = False) -> None:
    print(f"""
{_BD}╔══════════════════════════════════════════╗
║   🤵 Butler 首次配置向导 (约 3 分钟)      ║
╚══════════════════════════════════════════╝{_NC}

我们将完成 3 件事：
  1️⃣  选择 AI 服务商
  2️⃣  配置并校验 API Key
  3️⃣  给你 3 个可以直接上手的示例任务
""")

    # Step 1 & 2: 复用交互式配置向导
    try:
        from butler.cli.config_cmd import run_config
    except ImportError as e:
        from butler.core.errors import format_error
        print(format_error("BTL-1002", detail=str(e)))
        return
    run_config()

    # Step 2b: 连通性校验
    if not skip_check:
        _check_api_key()

    # Step 3: 示例任务 + 下一步
    print(f"""
{_BD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎉 配置完成！你可以对 Butler 说 / 尝试：{_NC}""")
    for i, t in enumerate(EXAMPLE_TASKS, 1):
        print(f"   {i}. {t}")

    print(f"""
{_BD}下一步：{_NC}
   • butler tui        进入终端交互界面（或 butler web / butler gui）
   • butler start      启动核心服务（REST API 网关）
   • butler skills     浏览 50+ 内置技能，发现更多玩法
   • butler doctor     系统体检（出问题时先跑它）

{_CY}提示：所有配置保存在 .env，可随时用 butler config show 查看、butler config 重新配置。{_NC}
""")


if __name__ == "__main__":
    run_init(skip_check="--skip-check" in sys.argv)
