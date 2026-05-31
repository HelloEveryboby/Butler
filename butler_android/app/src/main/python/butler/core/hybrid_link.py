import os
import subprocess
import json
import threading
import uuid
import logging
import time
from typing import Dict, Any, Optional, Callable, List
from .hybrid_fallbacks import dispatch_fallback

class HybridLinkClient:
    """
    Client for communicating with multi-language modules via the BHL protocol.
    """
    def __init__(self, executable_path: str, cwd: Optional[str] = None, fallback_enabled: bool = True):
        self.executable_path = executable_path
        self.cwd = cwd
        self.process = None
        self.logger = logging.getLogger(f"HybridLink.{uuid.uuid4().hex[:8]}")
        self._lock = threading.Lock()
        self._pending_requests: Dict[str, threading.Event] = {}
        self._responses: Dict[str, Any] = {}
        self._running = False
        self._event_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.fallback_enabled = fallback_enabled

    def register_event_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Registers a callback for asynchronous events (messages without an ID)."""
        self._event_callbacks.append(callback)

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
        if self.process:
            self._running = False
            try:
                # Try graceful exit if possible
                try:
                    self.call("exit", {}, wait=False, timeout=0.1)
                except:
                    pass

                time.sleep(0.1)
                if self.process.stdin:
                    try:
                        self.process.stdin.close()
                    except:
                        pass

                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            except Exception as e:
                self.logger.error(f"Error while stopping process: {e}")
                if self.process:
                    try:
                        self.process.kill()
                    except:
                        pass
            finally:
                self.process = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def _listen_stdout(self):
        """Reads responses from the module."""
        while self._running and self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
            except Exception as e:
                if self._running:
                    self.logger.error(f"Error reading from stdout: {e}")
                break
            if not line:
                break
            try:
                msg = json.loads(line.strip())
                req_id = msg.get("id")

                if req_id and req_id in self._pending_requests:
                    self._responses[req_id] = msg
                    self._pending_requests[req_id].set()
                elif not req_id:
                    # Treat as an event
                    for callback in self._event_callbacks:
                        try:
                            callback(msg)
                        except Exception as e:
                            self.logger.error(f"Error in event callback: {e}")
                else:
                    self.logger.debug(f"Received message with unknown id: {req_id}")
            except json.JSONDecodeError:
                # Sometimes modules might print non-JSON for debugging (though discouraged)
                self.logger.warning(f"Non-JSON from module: {line.strip()}")

    def _listen_stderr(self):
        """Logs errors from the module."""
        while self._running and self.process and self.process.stderr:
            line = self.process.stderr.readline()
            if not line:
                break
            self.logger.error(f"Module Stderr: {line.strip()}")

    def call(self, method: str, params: Dict[str, Any], timeout: float = 10.0, wait: bool = True, priority: int = 5) -> Any:
        """
        调用远程模块中的方法。
        :param method: 方法名
        :param params: 参数字典
        :param timeout: 超时时间（秒）
        :param wait: 是否等待响应
        :param priority: 任务优先级（由支持优先级队列的后端处理）
        """
        if not self.process or not self._running:
            if self.fallback_enabled:
                self.logger.info(f"正在为方法 {method} 使用 Python 回退方案")
                return dispatch_fallback(method, params)
            return {"error": {"message": "进程未启动且已禁用回退方案"}}

        req_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": req_id,
            "priority": priority
        }

        if wait:
            event = threading.Event()
            self._pending_requests[req_id] = event

        with self._lock:
            try:
                if self.process and self.process.stdin:
                    self.process.stdin.write(json.dumps(request) + "\n")
                    self.process.stdin.flush()
                else:
                    return {"error": {"message": "Stdin not available"}}
            except Exception as e:
                if wait: self._pending_requests.pop(req_id, None)
                return {"error": {"message": f"Failed to send request: {e}"}}

        if not wait:
            return None

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
