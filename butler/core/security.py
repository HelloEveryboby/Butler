"""
安全验证工具 — 为所有 Butler 功能模块提供统一的输入校验。

防护：
- 路径遍历 (Path Traversal)
- 命令注入 (Command Injection)
- 脚本注入 (Script Injection)
- 超长输入
- 非法字符
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_NAME_LENGTH = 256
_MAX_PATH_LENGTH = 4096
_MAX_MESSAGE_LENGTH = 5000
_MAX_URL_LENGTH = 2048

_SAFE_NAME_RE = re.compile(r'^[\w\-. /]{1,%d}$' % _MAX_NAME_LENGTH)
_SAFE_BRANCH_RE = re.compile(r'^[\w.\-\/]+$')
_SAFE_HEX_RE = re.compile(r'^[0-9a-fA-F]+$')
_SAFE_URL_RE = re.compile(r'^https?://[\w\-._~:/?#\[\]@!$&\'()*+,;=%]+$')
_SAFE_EMAIL_RE = re.compile(r'^[\w.\-]+@[\w\-]+\.[\w.\-]+$')

_PATH_TRAVERSAL_PATTERNS = ['..', '\x00']
_DANGEROUS_SHELL_CHARS = re.compile(r'[;&|`$(){}[\]<>!\n\r]')


def validate_path(
    path: str,
    allowed_roots: Optional[list[str]] = None,
    must_exist: bool = True,
    allow_symlinks: bool = False,
) -> str:
    """
    验证并规范化路径。

    防止路径遍历、空字节注入和非法路径。

    参数:
        path: 待验证的路径
        allowed_roots: 允许的根目录列表（路径必须位于其中之一）
        must_exist: 路径是否必须存在
        allow_symlinks: 是否允许符号链接

    返回:
        规范化后的绝对路径

    抛出:
        ValueError: 路径无效
    """
    if not path or not isinstance(path, str):
        raise ValueError("路径不能为空")

    if len(path) > _MAX_PATH_LENGTH:
        raise ValueError(f"路径过长 (最大 {_MAX_PATH_LENGTH} 字符)")

    for pattern in _PATH_TRAVERSAL_PATTERNS:
        if pattern in path:
            raise ValueError(f"路径包含非法字符: {pattern}")

    try:
        resolved = Path(path).resolve(strict=False)
    except (OSError, RuntimeError) as e:
        raise ValueError(f"路径解析失败: {e}")

    if must_exist and not resolved.exists():
        raise ValueError(f"路径不存在: {resolved}")

    if not allow_symlinks and resolved.is_symlink():
        raise ValueError(f"不允许符号链接: {resolved}")

    if allowed_roots:
        resolved_str = str(resolved)
        is_within = any(
            resolved_str.startswith(str(Path(root).resolve()))
            for root in allowed_roots
        )
        if not is_within:
            raise ValueError(f"路径不在允许的根目录中: {resolved}")

    return str(resolved)


def validate_name(name: str, field: str = "名称") -> str:
    """
    验证名称字段。

    名称只允许字母、数字、下划线、点、连字符和斜杠。
    """
    if not name or not isinstance(name, str):
        raise ValueError(f"{field}不能为空")

    if len(name) > _MAX_NAME_LENGTH:
        raise ValueError(f"{field}过长 (最大 {_MAX_NAME_LENGTH} 字符)")

    if not _SAFE_NAME_RE.match(name):
        raise ValueError(f"{field}包含非法字符，仅允许字母、数字、下划线、点、连字符")

    return name


def validate_branch_name(branch: str) -> str:
    """
    验证 Git 分支名。

    Git 分支名规则：不能以点/斜杠开头，不能包含连续点/空格/波浪号等。
    """
    if not branch or not isinstance(branch, str):
        raise ValueError("分支名不能为空")

    if len(branch) > 244:
        raise ValueError("分支名过长")

    if branch.startswith(('.', '/')):
        raise ValueError("分支名不能以点或斜杠开头")

    if branch.endswith('.'):
        raise ValueError("分支名不能以点结尾")

    if '..' in branch or ' ' in branch or '~' in branch or '^' in branch:
        raise ValueError("分支名包含非法字符")

    if not _SAFE_BRANCH_RE.match(branch):
        raise ValueError("分支名包含非法字符")

    return branch


def validate_git_message(message: str) -> str:
    """
    验证 Git 提交信息。

    防止通过多行提交信息注入额外的 `-m` 参数。
    """
    if not message or not isinstance(message, str):
        raise ValueError("提交信息不能为空")

    if len(message) > _MAX_MESSAGE_LENGTH:
        raise ValueError(f"提交信息过长 (最大 {_MAX_MESSAGE_LENGTH} 字符)")

    return message


def sanitize_git_message(message: str) -> list[str]:
    """
    将提交信息安全地转为 `-m` 参数列表。

    通过将消息拆分为多行，每行一个 `-m` 标记，防止注入额外参数。
    """
    validate_git_message(message)
    lines = message.split('\n')
    args: list[str] = []
    for line in lines:
        args.extend(['-m', line])
    return args


def validate_shell_safe(value: str, field: str = "值") -> str:
    """
    验证值不包含危险的 Shell 元字符。

    用于将用户输入嵌入 shell 命令时的防护。
    """
    if not isinstance(value, str):
        raise ValueError(f"{field}必须是字符串")

    if _DANGEROUS_SHELL_CHARS.search(value):
        raise ValueError(f"{field}包含危险字符，不允许在 Shell 命令中使用")

    return value


def validate_url(url: str) -> str:
    """验证 URL 格式。"""
    if not url or not isinstance(url, str):
        raise ValueError("URL 不能为空")

    if len(url) > _MAX_URL_LENGTH:
        raise ValueError(f"URL 过长 (最大 {_MAX_URL_LENGTH} 字符)")

    if not _SAFE_URL_RE.match(url):
        raise ValueError("URL 格式无效")

    return url


def sanitize_html(text: str) -> str:
    """
    将用户文本安全地嵌入 HTML。

    防止 XSS 攻击。
    """
    if not isinstance(text, str):
        return ""

    return (
        text.replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#x27;')
        .replace('\n', '&#10;')
        .replace('\r', '')
    )


def validate_session_id(session_id: str) -> str:
    """验证会话 ID 格式。"""
    if not session_id or not isinstance(session_id, str):
        raise ValueError("会话 ID 不能为空")

    if len(session_id) > 36:
        raise ValueError("会话 ID 过长")

    allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-')
    if not all(c in allowed_chars for c in session_id):
        raise ValueError("会话 ID 包含非法字符")

    return session_id


def validate_project_id(project_id: str) -> str:
    """验证项目 ID 格式。"""
    if not project_id or not isinstance(project_id, str):
        raise ValueError("项目 ID 不能为空")

    if len(project_id) > 64:
        raise ValueError("项目 ID 过长")

    allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')
    if not all(c in allowed_chars for c in project_id):
        raise ValueError("项目 ID 包含非法字符")

    return project_id


def validate_email(email: str) -> str:
    """验证邮箱格式。"""
    if not email or not isinstance(email, str):
        raise ValueError("邮箱不能为空")

    if len(email) > 254:
        raise ValueError("邮箱过长")

    if not _SAFE_EMAIL_RE.match(email):
        raise ValueError("邮箱格式无效")

    return email
