import json
import logging
import asyncio
import websockets
from typing import Dict, Any, Optional

logger = logging.getLogger("StorageBridge")

class StorageBridge:
    """Python bridge to communicate with butler_runner's storage methods via Butler server"""

    def __init__(self):
        # In Butler, skills usually don't talk directly to WS, they use RPC through the core.
        # But for high-perf IO, we might want a direct route or use the existing RunnerServer bridge.
        pass

    async def transfer(self, src_url: str, dst_url: str, method: str = "PUT", src_headers: Dict[str, str] = None, dst_headers: Dict[str, str] = None):
        """Delegate transfer to Go Runner"""
        from butler.core.runner_server import runner_server

        payload = {
            "src_url": src_url,
            "src_headers": src_headers or {},
            "dst_url": dst_url,
            "method": method,
            "dst_headers": dst_headers or {}
        }

        success, msg = runner_server.send_command(
            "default_runner",
            "storage_transfer",
            payload=json.dumps(payload)
        )
        return success, msg

    async def start_oauth_listen(self, port: int = 8421):
        """Start OAuth listener on Go Runner"""
        from butler.core.runner_server import runner_server

        success, code = runner_server.send_command(
            "default_runner",
            "storage_oauth_listen",
            payload=str(port)
        )
        return success, code

storage_bridge = StorageBridge()
