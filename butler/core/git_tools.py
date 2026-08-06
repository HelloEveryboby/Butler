"""
Git 工具模块 — 内置 Git 功能支持。

提供：
- Diff 面板：显示 Git 差异、内联注释、暂存/还原
- 提交 (Commit)：快速提交变更
- 推送 (Push)：推送到远程仓库
- Pull Request：创建 PR
- Worktree 管理：创建、列出、清理 worktree
- 状态查询：仓库状态、分支信息
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)


@dataclass
class GitDiffHunk:
    """Diff hunk 数据。"""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    content: str
    changes: list[str] = field(default_factory=list)


@dataclass
class GitDiffFile:
    """单文件 Diff 数据。"""

    file_path: str
    status: str  # M, A, D, R, C, U
    hunks: list[GitDiffHunk] = field(default_factory=list)
    old_path: Optional[str] = None
    is_binary: bool = False

    @property
    def has_changes(self) -> bool:
        return len(self.hunks) > 0 or self.status in ("A", "D", "R")


@dataclass
class GitDiffResult:
    """Diff 结果汇总。"""

    files: list[GitDiffFile] = field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0
    is_staged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "files": [
                {
                    "file_path": f.file_path,
                    "status": f.status,
                    "old_path": f.old_path,
                    "is_binary": f.is_binary,
                    "hunks": [
                        {
                            "old_start": h.old_start,
                            "old_count": h.old_count,
                            "new_start": h.new_start,
                            "new_count": h.new_count,
                            "content": h.content,
                            "changes": h.changes,
                        }
                        for h in f.hunks
                    ],
                }
                for f in self.files
            ],
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "is_staged": self.is_staged,
        }


@dataclass
class GitStatus:
    """仓库状态。"""

    branch: str = ""
    is_clean: bool = True
    modified: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "is_clean": self.is_clean,
            "modified": self.modified,
            "added": self.added,
            "deleted": self.deleted,
            "untracked": self.untracked,
            "ahead": self.ahead,
            "behind": self.behind,
        }


@dataclass
class WorktreeInfo:
    """Worktree 信息。"""

    path: str
    branch: str
    is_detached: bool = False
    is_locked: bool = False
    prune_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "branch": self.branch,
            "is_detached": self.is_detached,
            "is_locked": self.is_locked,
            "prune_reason": self.prune_reason,
        }


class GitTools:
    """
    Git 工具集。

    提供 Diff、Commit、Push、PR、Worktree 等完整 Git 功能。
    """

    GIT_EXECUTABLE = "git"

    def __init__(self, repo_path: str = ""):
        self._repo_path = repo_path

    def _run_git(
        self,
        args: list[str],
        cwd: Optional[str] = None,
        check: bool = True,
        timeout: int = 30,
    ) -> subprocess.CompletedProcess:
        """执行 Git 命令。"""
        cmd = [self.GIT_EXECUTABLE] + args
        target_cwd = cwd or self._repo_path or os.getcwd()

        try:
            result = subprocess.run(
                cmd,
                cwd=target_cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if check and result.returncode != 0:
                raise RuntimeError(
                    f"Git 命令失败 (exit {result.returncode}): {result.stderr.strip()}"
                )
            return result
        except FileNotFoundError:
            raise RuntimeError("Git 未安装或不在 PATH 中")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Git 命令超时: {' '.join(cmd)}")

    def is_git_repo(self, path: str = "") -> bool:
        """检查路径是否在 Git 仓库中。"""
        try:
            self._run_git(["rev-parse", "--git-dir"], cwd=path or self._repo_path)
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------------

    def get_status(self, path: str = "") -> GitStatus:
        """获取仓库状态。"""
        target = path or self._repo_path
        if not target:
            return GitStatus()

        try:
            branch_result = self._run_git(
                ["rev-parse", "--abbrev-ref", "HEAD"], cwd=target, check=False
            )
            branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
        except RuntimeError:
            branch = "unknown"

        status = GitStatus(branch=branch)

        try:
            result = self._run_git(["status", "--porcelain"], cwd=target, check=False)
            if result.returncode != 0:
                return status

            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                code = line[:2]
                filepath = line[3:].strip()
                if code == "??":
                    status.untracked.append(filepath)
                elif code.startswith("M") or code.endswith("M"):
                    status.modified.append(filepath)
                    status.is_clean = False
                elif code.startswith("A") or code.endswith("A"):
                    status.added.append(filepath)
                    status.is_clean = False
                elif code.startswith("D") or code.endswith("D"):
                    status.deleted.append(filepath)
                    status.is_clean = False
                elif code.startswith("R") or code.endswith("R"):
                    status.modified.append(filepath)
                    status.is_clean = False

            if not result.stdout.strip():
                status.is_clean = True

        except RuntimeError:
            pass

        try:
            ahead_result = self._run_git(
                ["rev-list", "--count", "@{u}..HEAD"], cwd=target, check=False
            )
            status.ahead = int(ahead_result.stdout.strip() or "0")
        except (RuntimeError, ValueError):
            pass

        try:
            behind_result = self._run_git(
                ["rev-list", "--count", "HEAD..@{u}"], cwd=target, check=False
            )
            status.behind = int(behind_result.stdout.strip() or "0")
        except (RuntimeError, ValueError):
            pass

        return status

    # ------------------------------------------------------------------
    # Diff 面板
    # ------------------------------------------------------------------

    def get_diff(
        self,
        path: str = "",
        staged: bool = False,
        file_filter: Optional[str] = None,
    ) -> GitDiffResult:
        """
        获取 Git Diff。

        参数:
            path: 仓库路径
            staged: 是否显示暂存区 diff
            file_filter: 只显示指定文件
        """
        target = path or self._repo_path
        result = GitDiffResult(is_staged=staged)

        args = ["diff", "--unified=3", "--no-color"]
        if staged:
            args.insert(0, "--cached")
        if file_filter:
            args.append("--")
            args.append(file_filter)

        try:
            proc = self._run_git(args, cwd=target, check=False)
            if proc.returncode != 0 or not proc.stdout.strip():
                return result
        except RuntimeError:
            return result

        result.files = self._parse_diff(proc.stdout)
        result.total_additions = sum(
            sum(1 for line in h.changes if line.startswith("+"))
            for f in result.files
            for h in f.hunks
        )
        result.total_deletions = sum(
            sum(1 for line in h.changes if line.startswith("-"))
            for f in result.files
            for h in f.hunks
        )
        return result

    def _parse_diff(self, diff_text: str) -> list[GitDiffFile]:
        """解析 Git diff 输出。"""
        files: list[GitDiffFile] = []
        current_file: Optional[GitDiffFile] = None
        current_hunk: Optional[GitDiffHunk] = None

        file_pattern = re.compile(r"^diff --git a/(.*?) b/(.*)$")
        binary_pattern = re.compile(r"^Binary files .* differ")
        hunk_pattern = re.compile(
            r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
        )
        old_pattern = re.compile(r"^--- (?:a/|/dev/null)(.*)$")
        new_pattern = re.compile(r"^\+\+\+ (?:b/|/dev/null)(.*)$")

        for line in diff_text.split("\n"):
            fm = file_pattern.match(line)
            if fm:
                if current_file:
                    files.append(current_file)
                current_file = GitDiffFile(
                    file_path=fm.group(2),
                    status="M",
                )
                current_hunk = None
                continue

            if current_file is None:
                continue

            if binary_pattern.match(line):
                current_file.is_binary = True
                continue

            hm = hunk_pattern.match(line)
            if hm:
                old_start = int(hm.group(1))
                old_count = int(hm.group(2) or "1")
                new_start = int(hm.group(3))
                new_count = int(hm.group(4) or "1")
                current_hunk = GitDiffHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    content=line,
                    changes=[],
                )
                current_file.hunks.append(current_hunk)
                continue

            if current_hunk is not None:
                if line.startswith("+") or line.startswith("-"):
                    current_hunk.changes.append(line)

        if current_file:
            files.append(current_file)

        return files

    def stage_file(self, file_path: str, path: str = "") -> bool:
        """暂存文件。"""
        target = path or self._repo_path
        try:
            self._run_git(["add", file_path], cwd=target)
            logger.info(f"文件已暂存: {file_path}")
            return True
        except RuntimeError as e:
            logger.error(f"暂存失败: {e}")
            return False

    def unstage_file(self, file_path: str, path: str = "") -> bool:
        """取消暂存文件。"""
        target = path or self._repo_path
        try:
            self._run_git(["reset", "HEAD", "--", file_path], cwd=target)
            return True
        except RuntimeError:
            try:
                self._run_git(["restore", "--staged", file_path], cwd=target)
                return True
            except RuntimeError as e:
                logger.error(f"取消暂存失败: {e}")
                return False

    def discard_changes(self, file_path: str, path: str = "") -> bool:
        """丢弃文件的工作区变更。"""
        target = path or self._repo_path
        try:
            self._run_git(["checkout", "--", file_path], cwd=target)
            return True
        except RuntimeError:
            try:
                self._run_git(["restore", file_path], cwd=target)
                return True
            except RuntimeError as e:
                logger.error(f"丢弃变更失败: {e}")
                return False

    # ------------------------------------------------------------------
    # 提交与推送
    # ------------------------------------------------------------------

    def commit(
        self,
        message: str,
        path: str = "",
        files: Optional[list[str]] = None,
        amend: bool = False,
    ) -> dict[str, Any]:
        """
        提交变更。

        参数:
            message: 提交信息
            path: 仓库路径
            files: 指定提交的文件（空则提交所有已暂存变更）
            amend: 是否修改上一次提交
        """
        target = path or self._repo_path

        try:
            if files:
                for f in files:
                    self._run_git(["add", f], cwd=target)

            args = ["commit", "-m", message]
            if amend:
                args.append("--amend")
            else:
                args.append("--allow-empty")

            result = self._run_git(args, cwd=target)
            commit_hash = result.stdout.strip() or self._get_last_commit_hash(target)

            logger.info(f"提交成功: {commit_hash}")
            return {
                "success": True,
                "commit_hash": commit_hash,
                "message": message,
            }
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

    def push(
        self,
        remote: str = "origin",
        branch: str = "",
        path: str = "",
        force: bool = False,
        upstream: bool = False,
    ) -> dict[str, Any]:
        """
        推送到远程仓库。

        参数:
            remote: 远程名称
            branch: 分支名（空则推送当前分支）
            path: 仓库路径
            force: 强制推送
            upstream: 设置上游分支
        """
        target = path or self._repo_path

        try:
            args = ["push", remote]
            if branch:
                args.append(branch)
            if force:
                args.append("--force")
            if upstream:
                args.append("--set-upstream")

            self._run_git(args, cwd=target, timeout=60)
            logger.info(f"推送成功: {remote}/{branch or 'current'}")
            return {"success": True}
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

    def _get_last_commit_hash(self, path: str = "") -> str:
        """获取最近一次提交的哈希。"""
        try:
            result = self._run_git(
                ["rev-parse", "--short", "HEAD"], cwd=path or self._repo_path
            )
            return result.stdout.strip()
        except RuntimeError:
            return ""

    # ------------------------------------------------------------------
    # Pull Request
    # ------------------------------------------------------------------

    def create_pr(
        self,
        title: str,
        body: str = "",
        base_branch: str = "main",
        head_branch: str = "",
        path: str = "",
        remote: str = "origin",
    ) -> dict[str, Any]:
        """
        创建 Pull Request。

        尝试使用 GitHub CLI，如果不可用则生成 PR URL。
        """
        target = path or self._repo_path
        head = head_branch or self._get_current_branch(target)

        if not head:
            return {"success": False, "error": "无法获取当前分支"}

        try:
            result = subprocess.run(
                ["gh", "pr", "create", "--title", title, "--body", body,
                 "--base", base_branch, "--head", head, "--json", "url"],
                cwd=target,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                pr_url = result.stdout.strip()
                logger.info(f"PR 已创建: {pr_url}")
                return {"success": True, "pr_url": pr_url, "method": "gh_cli"}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        pr_url = self._construct_pr_url(target, base_branch, head, title)
        logger.info(f"已生成 PR URL: {pr_url}")
        return {"success": True, "pr_url": pr_url, "method": "url"}

    def _get_current_branch(self, path: str = "") -> str:
        """获取当前分支名。"""
        try:
            result = self._run_git(
                ["rev-parse", "--abbrev-ref", "HEAD"], cwd=path
            )
            return result.stdout.strip()
        except RuntimeError:
            return ""

    def _construct_pr_url(
        self, repo_path: str, base: str, head: str, title: str
    ) -> str:
        """构造 PR 创建 URL。"""
        try:
            result = self._run_git(
                ["remote", "get-url", "origin"], cwd=repo_path, check=False
            )
            remote_url = result.stdout.strip() if result.returncode == 0 else ""
        except RuntimeError:
            remote_url = ""

        github_match = re.match(
            r"https://github\.com/([^/]+)/([^/.]+?)(?:\.git)?$", remote_url
        )
        if github_match:
            owner, repo = github_match.groups()
            encoded_title = quote(title, safe="")
            return (
                f"https://github.com/{owner}/{repo}/pull/"
                f"?base={base}&head={head}&title={encoded_title}"
            )

        return f"# PR 创建链接 (请手动访问远程仓库): {remote_url}/pull/new/{head}"

    # ------------------------------------------------------------------
    # Worktree 管理
    # ------------------------------------------------------------------

    def list_worktrees(self, path: str = "") -> list[WorktreeInfo]:
        """列出所有 worktree。"""
        target = path or self._repo_path
        worktrees: list[WorktreeInfo] = []

        try:
            result = self._run_git(
                ["worktree", "list", "--porcelain"], cwd=target, check=False
            )
            if result.returncode != 0:
                return worktrees

            current: dict[str, str] = {}
            for line in result.stdout.strip().split("\n"):
                if line.startswith("worktree "):
                    if current:
                        worktrees.append(WorktreeInfo(
                            path=current.get("worktree", ""),
                            branch=current.get("branch", ""),
                            is_detached=current.get("detached", "") == "true",
                            is_locked=current.get("locked", "") == "true",
                            prune_reason=current.get("prune", ""),
                        ))
                    current = {"worktree": line[9:]}
                elif line.startswith("branch "):
                    current["branch"] = line[7:]
                elif line.startswith("detached"):
                    current["detached"] = "true"
                elif line.startswith("locked"):
                    current["locked"] = "true"
                elif line.startswith("prune"):
                    current["prune"] = line[6:]

            if current:
                worktrees.append(WorktreeInfo(
                    path=current.get("worktree", ""),
                    branch=current.get("branch", ""),
                    is_detached=current.get("detached", "") == "true",
                    is_locked=current.get("locked", "") == "true",
                    prune_reason=current.get("prune", ""),
                ))

        except RuntimeError:
            pass

        return worktrees

    def create_worktree(
        self,
        branch_name: str,
        worktree_path: str,
        base_branch: str = "HEAD",
        path: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        """
        创建 worktree。

        参数:
            branch_name: 新分支名
            worktree_path: worktree 目录路径
            base_branch: 基于哪个分支
            path: 仓库路径
            force: 强制创建
        """
        target = path or self._repo_path

        wt_dir = Path(worktree_path)
        if wt_dir.exists():
            if force:
                import shutil
                shutil.rmtree(wt_dir, ignore_errors=True)
            else:
                return {"success": False, "error": f"目录已存在: {worktree_path}"}

        try:
            args = ["worktree", "add"]
            if force:
                args.append("--force")
            args.extend([str(wt_dir), "-b", branch_name, base_branch])

            self._run_git(args, cwd=target, timeout=30)
            logger.info(f"Worktree 已创建: {wt_dir} (分支: {branch_name})")
            return {
                "success": True,
                "worktree_path": str(wt_dir),
                "branch": branch_name,
            }
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

    def remove_worktree(
        self,
        worktree_path: str,
        path: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        """移除 worktree。"""
        target = path or self._repo_path

        try:
            args = ["worktree", "remove"]
            if force:
                args.append("--force")
            args.append(worktree_path)

            self._run_git(args, cwd=target, check=False)
            logger.info(f"Worktree 已移除: {worktree_path}")
            return {"success": True}
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

    def prune_worktrees(self, path: str = "") -> dict[str, Any]:
        """清理失效的 worktree。"""
        target = path or self._repo_path
        try:
            self._run_git(["worktree", "prune"], cwd=target, check=False)
            return {"success": True}
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # 分支管理
    # ------------------------------------------------------------------

    def list_branches(self, path: str = "", remote: bool = False) -> list[str]:
        """列出分支。"""
        target = path or self._repo_path
        try:
            args = ["branch"]
            if remote:
                args.append("-r")
            result = self._run_git(args, cwd=target)
            branches = []
            for line in result.stdout.strip().split("\n"):
                branch = line.strip().lstrip("* ")
                if branch:
                    branches.append(branch)
            return branches
        except RuntimeError:
            return []

    def checkout_branch(self, branch: str, path: str = "", create: bool = False) -> bool:
        """切换分支。"""
        target = path or self._repo_path
        try:
            args = ["checkout"]
            if create:
                args.append("-b")
            args.append(branch)
            self._run_git(args, cwd=target)
            return True
        except RuntimeError:
            return False

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------

    def get_log(
        self,
        path: str = "",
        max_count: int = 20,
        format_str: str = "%h %s",
    ) -> list[dict[str, str]]:
        """获取提交历史。"""
        target = path or self._repo_path
        try:
            result = self._run_git(
                ["log", f"--oneline", "-n", str(max_count), "--format=%H|%h|%an|%s|%ai"],
                cwd=target,
            )
            commits = []
            for line in result.stdout.strip().split("\n"):
                parts = line.split("|", 4)
                if len(parts) == 5:
                    commits.append({
                        "hash": parts[0],
                        "short_hash": parts[1],
                        "author": parts[2],
                        "message": parts[3],
                        "date": parts[4],
                    })
            return commits
        except RuntimeError:
            return []


# 全局实例
git_tools = GitTools()
