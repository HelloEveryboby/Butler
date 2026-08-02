import requests
import json
import logging
import socket
import ipaddress
from urllib.parse import urlparse
from typing import Dict, Any, Optional
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger("ActionBridge")


def _validate_safe_url(url: str) -> None:
    """校验 URL 安全性，防止 SSRF 攻击。

    - 仅允许 http/https 协议
    - 解析主机名并拒绝内网/本机/链路本地/保留/组播地址
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"不允许的协议: {parsed.scheme}，仅支持 http/https")
    if not parsed.hostname:
        raise ValueError("URL 缺少主机名")

    try:
        addr_info = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        raise ValueError(f"无法解析主机名: {parsed.hostname}")

    for _, _, _, _, sockaddr in addr_info:
        ip = ipaddress.ip_address(sockaddr[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise ValueError(f"不允许访问内网/本机地址: {ip}")

class ActionBridge:
    """
    Butler Action Bridge: Handles Webhooks and REST API templates.
    Allows Butler to connect to external services like IFTTT, Make.com, or custom APIs.
    """

    def __init__(self):
        self.templates = {
            "ifttt": "https://maker.ifttt.com/trigger/{event}/with/key/{key}",
            "feishu": "https://open.feishu.cn/open-apis/bot/v2/hook/{token}",
            "notion": "https://api.notion.com/v1/pages",
            "webhook_generic": "{url}"
        }

    def call_api(self, url: str, method: str = "POST", data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generic REST API caller."""
        try:
            _validate_safe_url(url)
            logger.info(f"Calling API: {method} {url}")
            if method.upper() == "GET":
                response = requests.get(url, params=data, headers=headers, timeout=10)
            elif method.upper() == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=10)
            else:
                return {"success": False, "error": f"Unsupported method: {method}"}

            response.raise_for_status()
            try:
                result = response.json()
            except:
                result = {"text": response.text}

            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return {"success": False, "error": str(e)}

    def trigger_webhook(self, name: str, payload: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Triggers a pre-configured or ad-hoc webhook."""
        template_name = config.get("template")
        url_template = self.templates.get(template_name) if template_name else config.get("url")

        if not url_template:
            return {"success": False, "error": "No URL or valid template provided for webhook."}

        # Simple template replacement
        try:
            url = url_template.format(**config)
        except KeyError as e:
            return {"success": False, "error": f"Missing required parameter for template '{template_name}': {e}"}
        method = config.get("method", "POST")
        headers = config.get("headers", {})

        return self.call_api(url, method, data=payload, headers=headers)

action_bridge = ActionBridge()
