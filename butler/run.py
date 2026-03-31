"""超时异步运行shell命令的实用程序."""

import asyncio
import shlex
import logging

logger = logging.getLogger(__name__)

TRUNCATED_MESSAGE: str = "<response clipped><NOTE>To save on context only part of this file has been shown to you. You should retry this tool after you have searched inside the file with `grep -n` in order to find the line numbers of what you are looking for.</NOTE>"
MAX_RESPONSE_LEN: int = 16000


def maybe_truncate(content: str, truncate_after: int | None = MAX_RESPONSE_LEN):
    """如果内容超过指定长度，则截断内容并附加通知."""
    return (
        content
        if not truncate_after or len(content) <= truncate_after
        else content[:truncate_after] + TRUNCATED_MESSAGE
    )


async def run(
    cmd: str,
    timeout: float | None = 120.0,  # 秒
    truncate_after: int | None = MAX_RESPONSE_LEN,
):
    """在超时的情况下异步运行Shell命令."""

    # Security Hardening: Prefer create_subprocess_exec for simple commands to avoid shell injection
    try:
        command_parts = shlex.split(cmd)
        shell_chars = {
            "|",
            "&",
            ";",
            "<",
            ">",
            "$",
            "*",
            "?",
            "(",
            ")",
            "[",
            "]",
            "!",
            "#",
            "~",
        }
        has_shell_meta = any(char in cmd for char in shell_chars)

        if command_parts and not has_shell_meta:
            logger.info(f"Executing secure command (no shell): {command_parts}")
            process = await asyncio.create_subprocess_exec(
                *command_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            logger.warning(
                f"Executing command with shell (meta-characters detected): {cmd}"
            )
            process = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
    except Exception as e:
        logger.error(f"Failed to split command, falling back to shell: {e}")
        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return (
            process.returncode or 0,
            maybe_truncate(stdout.decode(), truncate_after=truncate_after),
            maybe_truncate(stderr.decode(), truncate_after=truncate_after),
        )
    except asyncio.TimeoutError as exc:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        raise TimeoutError(
            f"Command '{cmd}' timed out after {timeout} seconds"
        ) from exc
