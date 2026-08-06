"""
跨项目多任务管理器 — 支持在单个 Butler 窗口中管理多个项目。

功能：
- 添加/移除项目
- 项目切换
- 项目配置持久化
- 沙箱隔离（每个项目独立环境）
- 并行任务执行
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProjectConfig:
    """项目配置。"""

    project_id: str
    name: str
    path: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: float = 0.0
    last_accessed: float = 0.0
    is_active: bool = False
    git_remote: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "path": self.path,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "is_active": self.is_active,
            "git_remote": self.git_remote,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectConfig:
        return cls(
            project_id=data["project_id"],
            name=data["name"],
            path=data["path"],
            description=data.get("description", ""),
            tags=data.get("tags", []),
            created_at=data.get("created_at", 0.0),
            last_accessed=data.get("last_accessed", 0.0),
            is_active=data.get("is_active", False),
            git_remote=data.get("git_remote", ""),
        )


class ProjectManager:
    """
    跨项目多任务管理器。

    允许用户在 Butler 中添加多个项目，并在它们之间切换。
    每个项目独立维护自己的配置、会话和沙箱环境。
    """

    def __init__(self, storage_path: str = ""):
        self._projects: dict[str, ProjectConfig] = {}
        self._active_project_id: Optional[str] = None
        self._lock = threading.RLock()
        self._storage_path = storage_path or self._default_storage_path()
        self._load_projects()

    def _default_storage_path(self) -> str:
        data_dir = Path(os.getenv("BUTLER_DATA_DIR", "data"))
        return str(data_dir / "projects.json")

    def _load_projects(self):
        """从磁盘加载项目列表。"""
        path = Path(self._storage_path)
        if not path.exists():
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for proj_data in data.get("projects", []):
                config = ProjectConfig.from_dict(proj_data)
                self._projects[config.project_id] = config
            self._active_project_id = data.get("active_project_id")
            logger.info(f"已加载 {len(self._projects)} 个项目")
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"加载项目配置失败: {e}")

    def _save_projects(self):
        """保存项目列表到磁盘。"""
        path = Path(self._storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "active_project_id": self._active_project_id,
            "projects": [p.to_dict() for p in self._projects.values()],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # CRUD 操作
    # ------------------------------------------------------------------

    def add_project(
        self,
        name: str,
        path: str,
        description: str = "",
        tags: Optional[list[str]] = None,
    ) -> ProjectConfig:
        """
        添加新项目。

        参数:
            name: 项目名称
            path: 项目路径
            description: 项目描述
            tags: 标签列表
        """
        with self._lock:
            project_path = Path(path).resolve()
            if not project_path.is_dir():
                raise ValueError(f"项目路径不存在: {path}")

            project_id = f"proj-{int(time.time())}-{abs(hash(name)) % 10000:04d}"

            config = ProjectConfig(
                project_id=project_id,
                name=name,
                path=str(project_path),
                description=description,
                tags=tags or [],
                created_at=time.time(),
                last_accessed=time.time(),
                is_active=False,
            )

            self._projects[project_id] = config
            self._save_projects()
            logger.info(f"项目已添加: {name} ({project_id})")
            return config

    def remove_project(self, project_id: str) -> bool:
        """移除项目。"""
        with self._lock:
            project = self._projects.pop(project_id, None)
            if not project:
                return False

            if self._active_project_id == project_id:
                self._active_project_id = None

            self._save_projects()
            logger.info(f"项目已移除: {project.name}")
            return True

    def get_project(self, project_id: str) -> Optional[ProjectConfig]:
        """获取指定项目。"""
        return self._projects.get(project_id)

    def list_projects(self) -> list[ProjectConfig]:
        """列出所有项目。"""
        return sorted(
            self._projects.values(),
            key=lambda p: p.last_accessed,
            reverse=True,
        )

    def search_projects(self, query: str = "") -> list[ProjectConfig]:
        """搜索项目。"""
        if not query:
            return self.list_projects()

        query_lower = query.lower()
        results = []
        for proj in self._projects.values():
            if (
                query_lower in proj.name.lower()
                or query_lower in proj.description.lower()
                or query_lower in proj.path.lower()
                or any(query_lower in tag.lower() for tag in proj.tags)
            ):
                results.append(proj)
        return sorted(results, key=lambda p: p.last_accessed, reverse=True)

    # ------------------------------------------------------------------
    # 项目切换
    # ------------------------------------------------------------------

    def set_active_project(self, project_id: str) -> Optional[ProjectConfig]:
        """切换到指定项目。"""
        with self._lock:
            project = self._projects.get(project_id)
            if not project:
                return None

            if self._active_project_id:
                old = self._projects.get(self._active_project_id)
                if old:
                    old.is_active = False

            self._active_project_id = project_id
            project.is_active = True
            project.last_accessed = time.time()
            self._save_projects()

            logger.info(f"已切换到项目: {project.name}")
            return project

    def get_active_project(self) -> Optional[ProjectConfig]:
        """获取当前活跃项目。"""
        if self._active_project_id:
            return self._projects.get(self._active_project_id)
        return None

    def update_project(self, project_id: str, **kwargs: Any) -> Optional[ProjectConfig]:
        """更新项目属性。"""
        with self._lock:
            project = self._projects.get(project_id)
            if not project:
                return None

            for key, value in kwargs.items():
                if hasattr(project, key) and key not in ("project_id", "created_at"):
                    setattr(project, key, value)

            self._save_projects()
            return project

    # ------------------------------------------------------------------
    # 批量操作
    # ------------------------------------------------------------------

    def get_parallel_contexts(self) -> list[dict[str, Any]]:
        """
        获取所有可并行执行的项目上下文。

        用于在多个项目中同时运行任务。
        """
        contexts = []
        for project in self._projects.values():
            contexts.append({
                "project_id": project.project_id,
                "name": project.name,
                "path": project.path,
                "tags": project.tags,
            })
        return contexts

    def export_config(self) -> dict[str, Any]:
        """导出所有项目配置。"""
        return {
            "active_project_id": self._active_project_id,
            "projects": [p.to_dict() for p in self._projects.values()],
        }

    def import_config(self, data: dict[str, Any]) -> int:
        """导入项目配置，返回新增数量。"""
        count = 0
        with self._lock:
            for proj_data in data.get("projects", []):
                project_id = proj_data.get("project_id", "")
                if project_id and project_id not in self._projects:
                    self._projects[project_id] = ProjectConfig.from_dict(proj_data)
                    count += 1

            if data.get("active_project_id") and not self._active_project_id:
                self._active_project_id = data["active_project_id"]

            self._save_projects()
        return count


project_manager = ProjectManager()
