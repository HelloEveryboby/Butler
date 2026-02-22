import asyncio
import os
from typing import ClassVar, Literal

from anthropic.types.beta import BetaToolBash20241022Param

from .base import BaseAnthropicTool, CLIResult, ToolError, ToolResult


class _BashSession:
    """bash shell的一个会话."""

    _started: bool
    _process: asyncio.subprocess.Process

    command: str = "/bin/bash"
    _output_delay: float = 0.2  # 秒
    _timeout: float = 120.0  # 秒
    _sentinel: str = "<<exit>>"

    def __init__(self):
        self._started = False
        self._timed_out = False

    async def start(self):
        if self._started:
            return

        self._process = await asyncio.create_subprocess_exec(
            self.command,
            preexec_fn=os.setsid,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._started = True

    def stop(self):
        """终止bash shell."""
        if not self._started:
            raise ToolError("会话尚未启动.")
        if self._process.returncode is not None:
            return
        self._process.terminate()

    async def run(self, command: str):
        """在bash shell中执行命令."""
        # 在执行命令前请求用户许可
        print(f"是否要执行以下命令？\n{command}")
        user_input = input("输入“yes ”以继续，要取消其他选项: ")

        if user_input.lower() != "yes":
            return ToolResult(
                system="命令执行被用户取消",
                error="用户未提供执行命令的权限.",
            )
        if not self._started:
            raise ToolError("会话尚未启动.")
        if self._process.returncode is not None:
            return ToolResult(
                system="必须重新启动工具",
                error=f"bash已退出，返回代码为 {self._process.returncode}",
            )
        if self._timed_out:
            raise ToolError(
                f"超时：bash尚未返回 {self._timeout} 秒，必须重新启动",
            )

        # 我们知道这些不是“无”，因为我们用PIPE创建了流程
        assert self._process.stdin
        assert self._process.stdout
        assert self._process.stderr

        # 向进程发送命令
        self._process.stdin.write(
            command.encode() + f"; echo '{self._sentinel}'\n".encode()
        )
        await self._process.stdin.drain()

        # 读取进程的输出，直到找到哨兵
        try:
            async with asyncio.timeout(self._timeout):
                while True:
                    await asyncio.sleep(self._output_delay)
                    # 如果我们直接从stdout/stderr读取，它将永远等待
                    # EOF.而是直接使用StreamReader缓冲区
                    output = (
                        self._process.stdout._buffer.decode()
                    )  # pyright: ignore[reportAttributeAccessIssue]
                    if self._sentinel in output:
                        # 剥去哨兵的衣服打破
                        output = output[: output.index(self._sentinel)]
                        break
        except asyncio.TimeoutError:
            self._timed_out = True
            raise ToolError(
                f"超时：bash尚未返回 {self._timeout} 秒，必须重新启动",
            ) from None

        if output.endswith("\n"):
            output = output[:-1]

        error = (
            self._process.stderr._buffer.decode()
        )  # pyright: ignore[reportAttributeAccessIssue]
        if error.endswith("\n"):
            error = error[:-1]

        # 清除缓冲区，以便可以正确读取下一个输出
        self._process.stdout._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]
        self._process.stderr._buffer.clear()  # pyright: ignore[reportAttributeAccessIssue]

        return CLIResult(output=output, error=error)


class BashTool(BaseAnthropicTool):
    """
    允许代理运行bash命令的工具。
    刀具参数由Anthropic定义，不可编辑。.
    """

    _session: _BashSession | None
    name: ClassVar[Literal["bash"]] = "bash"
    api_type: ClassVar[Literal["bash_20241022"]] = "bash_20241022"

    def __init__(self):
        self._session = None
        super().__init__()

    async def __call__(
        self, command: str | None = None, restart: bool = False, **kwargs
    ):
        if restart:
            if self._session:
                self._session.stop()
            self._session = _BashSession()
            await self._session.start()

            return ToolResult(system="tool has been restarted.")

        if self._session is None:
            self._session = _BashSession()
            await self._session.start()

        if command is not None:
            return await self._session.run(command)

        raise ToolError("未提供命令.")

    def to_params(self) -> BetaToolBash20241022Param:
        return {
            "type": self.api_type,
            "name": self.name,
        }
