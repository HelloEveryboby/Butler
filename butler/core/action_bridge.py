import requests
import json
import logging
from typing import Dict, Any, Optional
from package.core_utils.log_manager import LogManager

logger = LogManager.get_logger("ActionBridge")

class ActionBridge:
    """
    Butler Action Bridge: Handles Webhooks and REST API templates.
    Allows Butler to connect to external services like IFTTT, Make.com, or custom APIs.
    """

    def __init__(self):
        self.templates = {
            "ifttt": "https://maker.ifttt.com/trigger/{event}/with/key/{key}",
            "webhook_generic": "{url}"
        }

    def call_api(self, url: str, method: str = "POST", data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generic REST API caller."""
        try:
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
        url_template = config.get("url")
        if not url_template:
            return {"success": False, "error": "No URL provided for webhook."}

        # Simple template replacement
        url = url_template.format(**config)
        method = config.get("method", "POST")
        headers = config.get("headers", {})

        return self.call_api(url, method, data=payload, headers=headers)

action_bridge = ActionBridge()
