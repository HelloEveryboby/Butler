"""统一版本门面 — 文本走 Git，图片/视频走内容寻址快照。

对外四个动作：snapshot（建版本点）、list_versions（版本列表）、diff（前后对比）、
restore（回滚）。文本文件若在 Git 仓库内则就地提交，否则镜像到影子仓
data/system_data/version_repo；其他文件由 ArtifactStore 去重保存。
"""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Any

from butler.core.artifact_store import ArtifactStore, artifact_store
from butler.core.constants import DATA_DIR

logger = logging.getLogger("VersionStore")

TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".html", ".css", ".xml", ".sql", ".sh",
}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target TEXT,
    kind TEXT,
    backend TEXT,
    ref TEXT,
    size INTEGER DEFAULT 0,
    message TEXT,
    author TEXT,
    created_at TEXT,
    meta_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_versions_target ON versions(target);
"""


def classify(path: str | Path) -> str:
    """按扩展名判定版本类型。"""
    suffix = Path(path).suffix.lower()
    if suffix in TEXT_EXTS:
        return "text"
    if suffix in IMAGE_EXTS:
        return "image"
    if suffix in VIDEO_EXTS:
        return "video"
    if suffix in AUDIO_EXTS:
        return "audio"
    return "binary"


class VersionStore:
    """版本记录门面。失败只抛异常，由调用方决定是否降级为告警。"""

    def __init__(
        self,
        db_path: Path | None = None,
        shadow_repo: Path | None = None,
        artifact: ArtifactStore | None = None,
    ):
        self.db_path = (
            Path(db_path) if db_path else DATA_DIR / "system_data" / "version_store.db"
        )
        self.shadow_repo = (
            Path(shadow_repo) if shadow_repo else DATA_DIR / "system_data" / "version_repo"
        )
        self.artifact = artifact or artifact_store
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── 基础设施 ────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def _run_git(
        args: list[str], cwd: Path, check: bool = False, binary: bool = False
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=not binary,
            timeout=60,
            check=False if binary else check,
        )

    @staticmethod
    def _find_repo_root(start: Path) -> Path | None:
        current = start.resolve()
        while True:
            if (current / ".git").exists():
                return current
            if current.parent == current:
                return None
            current = current.parent

    def _ensure_shadow_repo(self) -> Path:
        repo = self.shadow_repo
        repo.mkdir(parents=True, exist_ok=True)
        if not (repo / ".git").exists():
            self._run_git(["init"], repo)
            self._run_git(["config", "user.name", "Butler"], repo)
            self._run_git(["config", "user.email", "butler@local"], repo)
        return repo

    @staticmethod
    def _mirror_rel(path: Path) -> Path:
        parts = [p for p in path.parts if p not in ("/", "\\", "")]
        return Path(*parts) if parts else Path(path.name)

    def _commit_path(self, repo: Path, rel: str, message: str) -> tuple[str, bool]:
        self._run_git(["add", "--", rel], repo)
        proc = self._run_git(["commit", "-m", message, "--", rel], repo)
        changed = proc.returncode == 0
        head = self._run_git(["rev-parse", "HEAD"], repo).stdout.strip()
        return head, changed

    # ── 创建版本点 ──────────────────────────────────────────

    def snapshot(
        self, target: str | Path, message: str = "", author: str = "auto"
    ) -> dict[str, Any]:
        path = Path(target).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"文件不存在: {path}")

        kind = classify(path)
        message = message or f"butler: 保存 {path.name}"
        size = path.stat().st_size

        if kind == "text":
            record = self._snapshot_text(path, message, author, size)
        else:
            record = self._snapshot_binary(path, message, author, kind, size)

        self._insert(record)
        return record

    def _snapshot_text(
        self, path: Path, message: str, author: str, size: int
    ) -> dict[str, Any]:
        repo_root = self._find_repo_root(path.parent)
        if repo_root is not None:
            rel = path.relative_to(repo_root).as_posix()
            backend = "git"
        else:
            repo_root = self._ensure_shadow_repo()
            mirrored = repo_root / "files" / self._mirror_rel(path)
            mirrored.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, mirrored)
            rel = mirrored.relative_to(repo_root).as_posix()
            backend = "shadow"

        ref, changed = self._commit_path(repo_root, rel, message)
        return {
            "target": str(path),
            "kind": "text",
            "backend": backend,
            "ref": ref,
            "size": size,
            "message": message,
            "author": author,
            "meta": {"repo": str(repo_root), "rel": rel, "changed": changed},
        }

    def _snapshot_binary(
        self, path: Path, message: str, author: str, kind: str, size: int
    ) -> dict[str, Any]:
        max_mb = self._max_artifact_mb()
        sha = self.artifact.put_file(path, max_mb=max_mb)
        meta: dict[str, Any] = {"sha": sha, "size": size}
        if kind == "image":
            try:
                from PIL import Image

                with Image.open(path) as img:
                    meta.update({"width": img.width, "height": img.height, "mode": img.mode})
            except Exception:
                pass
        return {
            "target": str(path),
            "kind": kind,
            "backend": "artifact",
            "ref": sha,
            "size": size,
            "message": message,
            "author": author,
            "meta": meta,
        }

    def _max_artifact_mb(self) -> int | None:
        try:
            from package.core_utils.config_loader import config_loader

            value = config_loader.get("versioning.max_artifact_mb", 512)
            return int(value) if value else None
        except Exception:
            return 512

    def _insert(self, record: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO versions
                    (target, kind, backend, ref, size, message, author, created_at, meta_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["target"],
                    record["kind"],
                    record["backend"],
                    record["ref"],
                    record["size"],
                    record["message"],
                    record["author"],
                    time.strftime("%Y-%m-%d %H:%M:%S"),
                    json.dumps(record["meta"], ensure_ascii=False),
                ),
            )

    # ── 查询 ────────────────────────────────────────────────

    def list_versions(self, target: str | Path) -> list[dict[str, Any]]:
        path = str(Path(target).expanduser().resolve())
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM versions WHERE target = ? ORDER BY id DESC", (path,)
            ).fetchall()
        result = []
        for row in rows:
            data = dict(row)
            try:
                data["meta"] = json.loads(data.pop("meta_json") or "{}")
            except json.JSONDecodeError:
                data["meta"] = {}
            result.append(data)
        return result

    def _resolve_record(self, target: str | Path, rev: str | int) -> dict[str, Any] | None:
        versions = self.list_versions(target)
        rev_text = str(rev)
        for item in versions:
            if item["ref"] == rev_text or str(item["id"]) == rev_text:
                return item
        return None

    # ── 对比 ────────────────────────────────────────────────

    def diff(
        self, target: str | Path, rev_a: str | int | None = None,
        rev_b: str | int | None = None,
    ) -> str:
        versions = self.list_versions(target)
        if not versions:
            return ""

        if rev_a or rev_b:
            left = self._resolve_record(target, rev_a) if rev_a else None
            right = self._resolve_record(target, rev_b) if rev_b else None
        elif len(versions) >= 2:
            left, right = versions[1], versions[0]
        else:
            left, right = versions[0], None

        if left is None:
            return ""

        if left["backend"] in ("git", "shadow") and (
            right is None or right["backend"] in ("git", "shadow")
        ):
            return self._diff_text(left, right)

        return self._diff_binary(left, right)

    def _diff_text(
        self, left: dict[str, Any], right: dict[str, Any] | None
    ) -> str:
        repo = Path(left["meta"].get("repo", ""))
        rel = left["meta"].get("rel", "")
        if not repo or not rel:
            return ""
        if right is None:
            args = ["diff", left["ref"], "--", rel]
        elif right["ref"] and right["ref"] != left["ref"]:
            args = ["diff", left["ref"], right["ref"], "--", rel]
        else:
            args = ["diff", left["ref"], "--", rel]
        proc = self._run_git(args, repo)
        return proc.stdout

    def _diff_binary(
        self, left: dict[str, Any], right: dict[str, Any] | None
    ) -> str:
        lines = [f"# 二进制版本对比: {left['target']}", f"- 旧: {left['ref']}"]
        if right:
            lines.append(f"- 新: {right['ref']}")
        else:
            lines.append("- 新: (工作区)")
        for label, item in (("旧", left), ("新", right)):
            if not item:
                continue
            meta = item.get("meta", {})
            detail = ", ".join(f"{k}={v}" for k, v in meta.items() if k != "sha")
            lines.append(f"{label}尺寸: {item.get('size')} 字节 {detail}".rstrip())
        return "\n".join(lines)

    # ── 回滚 ────────────────────────────────────────────────

    def restore(self, target: str | Path, rev: str | int) -> bool:
        path = Path(target).expanduser().resolve()
        record = self._resolve_record(path, rev)
        if not record:
            raise ValueError(f"未找到版本: {rev}")

        if record["backend"] == "artifact":
            artifact_path = self.artifact.get_path(record["ref"])
            shutil.copyfile(artifact_path, path)
            return True

        repo = Path(record["meta"].get("repo", ""))
        rel = record["meta"].get("rel", "")
        if not repo or not rel:
            raise ValueError("版本记录缺少仓库信息")
        proc = self._run_git(["show", f"{record['ref']}:{rel}"], repo, binary=True)
        if proc.returncode != 0:
            raise RuntimeError(f"读取历史版本失败: {proc.stderr.decode('utf-8', 'ignore')}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(proc.stdout)
        return True

    # ── 清理 ────────────────────────────────────────────────

    def prune(self, keep: int | None = None) -> dict[str, Any]:
        if keep is None:
            try:
                from package.core_utils.config_loader import config_loader

                keep = int(config_loader.get("versioning.prune_keep", 50))
            except Exception:
                keep = 50
        keep = max(1, keep)

        deleted = 0
        with self._connect() as conn:
            targets = [
                row[0] for row in conn.execute("SELECT DISTINCT target FROM versions")
            ]
            for target in targets:
                ids = [
                    row[0]
                    for row in conn.execute(
                        "SELECT id FROM versions WHERE target = ? ORDER BY id DESC",
                        (target,),
                    )
                ]
                stale = ids[keep:]
                if stale:
                    conn.executemany(
                        "DELETE FROM versions WHERE id = ?", [(i,) for i in stale]
                    )
                    deleted += len(stale)

            referenced = {
                row[0]
                for row in conn.execute(
                    "SELECT ref FROM versions WHERE backend = 'artifact'"
                )
            }
        freed = self.artifact.prune(referenced)
        return {"deleted_records": deleted, "freed_bytes": freed}


version_store = VersionStore()
