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
    用于通过 BHL 协议与多语言模块通信的客户端。
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
        """注册异步事件回调（不含 ID 的消息）。"""
        self._event_callbacks.append(callback)

    def start(self):
        """启动外部进程。"""
        if not os.path.isfile(self.executable_path):
            self.logger.error(f"找不到可执行文件: {self.executable_path}")
            return False

        try:
            # 为了安全起见，使用 shell=False（默认）。参数作为列表传递。
            self.process = subprocess.Popen(
                [self.executable_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # 行缓冲
                cwd=self.cwd,
                shell=False
            )
            self._running = True
            threading.Thread(target=self._listen_stdout, daemon=True).start()
            threading.Thread(target=self._listen_stderr, daemon=True).start()
            return True
        except Exception as e:
            self.logger.error(f"无法启动混合模块: {e}")
            return False

    def stop(self):
        """停止外部进程。"""
        if self.process:
            try:
                # 尽可能优雅地退出
                try:
                    self.call("exit", {}, wait=False, timeout=0.1)
                except:
                    pass

                self._running = False
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
                if self.process:
                    self.process.kill()
            self.process = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def _listen_stdout(self):
        """从模块读取响应。"""
        while self._running and self.process and self.process.stdout:
            line = self.process.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line.strip())
                req_id = msg.get("id")

                if req_id and req_id in self._pending_requests:
                    self._responses[req_id] = msg
                    self._pending_requests[req_id].set()
                elif not req_id:
                    # 视为事件
                    for callback in self._event_callbacks:
                        try:
                            callback(msg)
                        except Exception as e:
                            self.logger.error(f"事件回调出错: {e}")
                else:
                    self.logger.debug(f"收到具有未知 id 的消息: {req_id}")
            except json.JSONDecodeError:
                # 有时模块可能出于调试目的打印非 JSON 内容（尽管不鼓励这样做）
                self.logger.warning(f"模块输出非 JSON 内容: {line.strip()}")

    def _listen_stderr(self):
        """记录模块中的错误。"""
        while self._running and self.process and self.process.stderr:
            line = self.process.stderr.readline()
            if not line:
                break
            self.logger.error(f"模块标准错误输出: {line.strip()}")

    def call(self, method: str, params: Dict[str, Any], timeout: float = 10.0, wait: bool = True) -> Any:
        """调用远程模块中的方法。"""
        if not self.process or not self._running:
            if self.fallback_enabled:
                self.logger.info(f"对方法 {method} 使用 Python 降级方案")
                return dispatch_fallback(method, params)
            return {"error": {"message": "进程未启动且降级方案已禁用"}}

        req_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": req_id
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
                    return {"error": {"message": "标准输入不可用"}}
            except Exception as e:
                if wait: self._pending_requests.pop(req_id, None)
                return {"error": {"message": f"发送请求失败: {e}"}}

        if not wait:
            return None

        try:
            if event.wait(timeout):
                response = self._responses.pop(req_id)
                if "error" in response:
                    return {"error": response["error"]}
                return response.get("result")
            else:
                return {"error": {"message": "请求超时"}}
        finally:
            self._pending_requests.pop(req_id, None)

if __name__ == "__main__":
    # 此处应有测试代码，但需要先建立服务器。
    pass
