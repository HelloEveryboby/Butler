import os
import subprocess
import json
import threading
import uuid
import logging
import time
from typing import Dict, Any, Optional

class HybridLinkClient:
    """
    Client for communicating with multi-language modules via the BHL protocol.
    """
    def __init__(self, executable_path: str, cwd: Optional[str] = None):
        self.executable_path = executable_path
        self.cwd = cwd
        self.process = None
        self.logger = logging.getLogger(f"HybridLink.{uuid.uuid4().hex[:8]}")
        self._lock = threading.Lock()
        self._pending_requests: Dict[str, threading.Event] = {}
        self._responses: Dict[str, Any] = {}
        self._running = False

    def start(self):
        """Starts the external process."""
        if not os.path.isfile(self.executable_path):
            self.logger.error(f"Executable not found: {self.executable_path}")
            return False

        try:
            # Use shell=False (default) for security. Arguments are passed as a list.
            self.process = subprocess.Popen(
                [self.executable_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # Line buffered
                cwd=self.cwd,
                shell=False
            )
            self._running = True
            threading.Thread(target=self._listen_stdout, daemon=True).start()
            threading.Thread(target=self._listen_stderr, daemon=True).start()
            return True
        except Exception as e:
            self.logger.error(f"Failed to start hybrid module: {e}")
            return False

    def stop(self):
        """Stops the external process."""
        self._running = False
        if self.process:
            try:
                self.call("exit", {}, wait=False)
                time.sleep(0.1)
                if self.process.stdin:
                    self.process.stdin.close()
                if self.process.stdout:
                    self.process.stdout.close()
                if self.process.stderr:
                    self.process.stderr.close()
                self.process.terminate()
                self.process.wait(timeout=1)
            except:
                pass
            self.process = None

    def _listen_stdout(self):
        """Reads responses from the module."""
        while self._running and self.process and self.process.stdout:
            line = self.process.stdout.readline()
            if not line:
                break
            try:
                response = json.loads(line.strip())
                req_id = response.get("id")
                if req_id in self._pending_requests:
                    self._responses[req_id] = response
                    self._pending_requests[req_id].set()
            except json.JSONDecodeError:
                self.logger.warning(f"Invalid JSON from module: {line.strip()}")

    def _listen_stderr(self):
        """Logs errors from the module."""
        while self._running and self.process and self.process.stderr:
            line = self.process.stderr.readline()
            if not line:
                break
            self.logger.error(f"Module Stderr: {line.strip()}")

    def call(self, method: str, params: Dict[str, Any], timeout: float = 10.0, wait: bool = True) -> Any:
        """Calls a method in the remote module."""
        if not self.process:
            return {"error": {"message": "Process not started"}}

        req_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": req_id
        }

        with self._lock:
            try:
                self.process.stdin.write(json.dumps(request) + "\n")
                self.process.stdin.flush()
            except Exception as e:
                return {"error": {"message": f"Failed to send request: {e}"}}

        if not wait:
            return None

        event = threading.Event()
        self._pending_requests[req_id] = event

        try:
            if event.wait(timeout):
                response = self._responses.pop(req_id)
                if "error" in response:
                    return {"error": response["error"]}
                return response.get("result")
            else:
                return {"error": {"message": "Request timed out"}}
        finally:
            self._pending_requests.pop(req_id, None)

if __name__ == "__main__":
    # Test would go here, but we need a server first.
    pass
