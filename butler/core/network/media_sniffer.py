"""媒体链接嗅探（原 ``skill_media_sniffer``）。"""

import json
import sys

SOURCES = ["GitHub Releases", "V2EX - Creative"]


def sniff() -> dict:
    """返回嗅探器当前监听的来源状态。"""
    return {"status": "monitoring", "sources": list(SOURCES)}


def handle_request(action: str = "status", **_kwargs) -> dict:
    if action in ("status", "sniff", "run"):
        return sniff()
    return {"error": f"未知动作: {action}"}


def main() -> None:
    print(json.dumps(sniff(), ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
