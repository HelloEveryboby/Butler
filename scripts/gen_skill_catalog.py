#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成技能目录 skills/CATALOG.md（供 butler skills 与文档站使用）。

用法:
    python scripts/gen_skill_catalog.py           # 生成并打印统计
    python scripts/gen_skill_catalog.py --check   # 仅检查是否需要重新生成 (CI 用)

解析规则（与 docs/dev/SKILL_FRONTMATTER.md 规范一致）：
    1. SKILL.md 的 YAML front-matter 中的 name / description / tags 优先；
    2. 缺失时降级：首个 `# 标题` 作为名称，首个正文段落作为描述。
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
OUTPUT = SKILLS_DIR / "CATALOG.md"


def parse_skill_md(path: Path) -> dict:
    """解析 SKILL.md，返回 {name, description, tags}（尽力而为）。"""
    info = {"name": path.parent.name, "description": "", "tags": []}
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return info

    # 1) YAML front-matter
    fm = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                fm = yaml.safe_load(parts[1]) or {}
            except Exception:
                # 降级：key: value 逐行解析
                for line in parts[1].splitlines():
                    m = re.match(r"^(\w[\w-]*)\s*:\s*(.+)$", line.strip())
                    if m:
                        fm[m.group(1)] = m.group(2).strip()
            body = parts[2]
        else:
            body = content
    else:
        body = content

    if isinstance(fm, dict):
        info["name"] = str(fm.get("name") or info["name"])
        info["description"] = str(fm.get("description") or "")
        tags = fm.get("tags") or []
        info["tags"] = [str(t) for t in tags] if isinstance(tags, list) else [str(tags)]

    # 2) 降级：首个标题 + 首个段落
    if not info["description"]:
        lines = [l.strip() for l in body.splitlines()]
        heading = next((l.lstrip("# ").strip() for l in lines if l.startswith("#")), "")
        if heading and not fm.get("name"):
            info["name"] = heading
        para = []
        for l in lines:
            if l.startswith("#") or l.startswith("```") or l.startswith("|"):
                if para:
                    break
                continue
            if l:
                para.append(l)
            elif para:
                break
        info["description"] = " ".join(para)[:120]

    return info


def build_catalog() -> str:
    skills = []
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        skills.append(parse_skill_md(skill_md))
    # 兼容扁平 .md 技能
    for flat_md in sorted(SKILLS_DIR.glob("*.md")):
        if flat_md.name != "CATALOG.md":
            skills.append(parse_skill_md(flat_md))

    rows = []
    for s in sorted(skills, key=lambda x: x["name"].lower()):
        tags = " ".join(f"`{t}`" for t in s["tags"]) if s["tags"] else "—"
        desc = s["description"].replace("|", "\\|") or "—"
        rows.append(f"| **{s['name']}** | {desc} | {tags} |")

    return f"""# 📖 Butler 技能目录（自动生成）

> ⚠️ 本文件由 `scripts/gen_skill_catalog.py` 自动生成，请勿手动编辑。
> 重新生成：`python scripts/gen_skill_catalog.py` 或 `butler skills catalog`
>
> 调用方式：`butler skill info <技能名>` 查看详情 / `butler skill run <技能名>` 运行

共 **{len(skills)}** 个技能：

| 技能 | 说明 | 标签 |
| :--- | :--- | :--- |
{chr(10).join(rows)}

---

想写自己的技能？一个文件夹 = 一个技能，参考 **[SKILL_FRONTMATTER 规范](../docs/dev/SKILL_FRONTMATTER.md)** 与 [贡献指南](../docs/SKILLS_GUIDE.md)。
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 skills/CATALOG.md")
    parser.add_argument("--check", action="store_true", help="仅检查是否需要重新生成")
    args = parser.parse_args()

    content = build_catalog()
    if args.check:
        old = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if old != content:
            print("❌ skills/CATALOG.md 已过期，请运行: python scripts/gen_skill_catalog.py")
            sys.exit(1)
        print("✅ skills/CATALOG.md 是最新的")
        return

    OUTPUT.write_text(content, encoding="utf-8")
    n = content.count("\n| **")
    print(f"✅ 已生成 {OUTPUT.relative_to(ROOT)}（{n} 个技能）")


if __name__ == "__main__":
    main()
