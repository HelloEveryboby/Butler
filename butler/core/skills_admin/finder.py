"""技能发现/搜索（原 find-skills 能力）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from butler.core.skill_registry import discover_skills, load_skill_metadata


def find(query: str = "", limit: int = 20, skills_dir: Path | None = None) -> dict[str, Any]:
    """按关键词搜索已发现技能，返回 ``{query, skills, count}``。"""
    keyword = (query or "").strip().lower()
    results: list[dict[str, Any]] = []
    for skill_id, skill_path in sorted(discover_skills(skills_dir).items()):
        try:
            meta = load_skill_metadata(skill_id, skill_path)
        except Exception:  # noqa: BLE001 - 单个技能元数据损坏不影响整体搜索
            meta = {}
        haystack = " ".join(
            str(meta.get(key, "")) for key in ("id", "name", "description", "when_to_use")
        ).lower()
        haystack = f"{skill_id.lower()} {haystack}"
        if keyword and keyword not in haystack:
            continue
        results.append(
            {
                "id": skill_id,
                "name": meta.get("name") or skill_id,
                "description": meta.get("description", ""),
                "path": str(skill_path),
            }
        )
    return {"query": keyword, "skills": results[:limit], "count": len(results)}
