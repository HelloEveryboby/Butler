"""
技能创作助手 (Skill Creator)

此技能集成了 Anthropic 的专业技能开发工作流，并保留了 Butler 基础模板生成功能。
主要功能：
1. 捕获意图并编写 SKILL.md
2. 运行自动化测试与基准测试 (Benchmark)
3. 使用 Eval Viewer 进行人工评估
4. 迭代优化技能质量
5. 快速生成符合 Butler 规范的新技能模板
"""
import logging
import os
import json
from pathlib import Path

logger = logging.getLogger("SkillCreator")

def create_skill(skill_id, name=None, description=None):
    """
    创建一个新的 Butler 技能模板。
    """
    if not skill_id:
        return "错误：必须提供 skill_id。"

    # 项目根目录通常是 skills/ 目录的父目录
    skill_root = Path(__file__).parent.resolve()
    project_root = skill_root.parent.parent
    skills_dir = project_root / "skills"
    skill_path = skills_dir / skill_id

    if skill_path.exists():
        return f"错误：技能目录 '{skill_id}' 已存在。"

    try:
        os.makedirs(skill_path, exist_ok=True)

        # 1. 创建 manifest.json
        manifest = {
            "skill_id": skill_id,
            "name": name or skill_id.replace("_", " ").title(),
            "description": description or f"这是 {skill_id} 技能的描述。",
            "version": "0.1.0",
            "actions": ["init"],
            "keywords": [skill_id]
        }
        with open(skill_path / "manifest.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=4, ensure_ascii=False)

        # 2. 创建 __init__.py
        init_content = f'''"""
{manifest["name"]} 技能入口
"""
import logging

logger = logging.getLogger("{skill_id}")

def handle_request(action, **kwargs):
    """
    处理技能请求的入口函数。
    :param action: 动作名称
    :param kwargs: 包含 jarvis_app, config, manifest 等上下文
    """
    logger.info(f"技能 {skill_id} 收到动作: {{action}}")

    if action == "init":
        return f"技能 {skill_id} 初始化成功！"

    return f"技能 {skill_id} 不支持动作: {{action}}"
'''
        with open(skill_path / "__init__.py", "w", encoding="utf-8") as f:
            f.write(init_content)

        # 3. 创建 README.md (默认使用中文)
        readme_content = f"""# {manifest["name"]}

{manifest["description"]}

## 安装
此技能已包含在 Butler 项目中。

## 使用方法
通过 Butler 调用此技能。支持的动作包括：
- `init`: 初始化技能。

## 开发指南
技能代码位于 `__init__.py`。
"""
        with open(skill_path / "README.md", "w", encoding="utf-8") as f:
            f.write(readme_content)

        # 4. 创建 requirements.txt
        with open(skill_path / "requirements.txt", "w", encoding="utf-8") as f:
            f.write("# 在此列出技能所需的 Python 依赖\n")

        # 5. 更新 skills-lock.json
        lock_file = project_root / "skills-lock.json"
        if lock_file.exists():
            try:
                with open(lock_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                enabled_skills = data.get("enabled_skills", [])
                if skill_id not in enabled_skills:
                    enabled_skills.append(skill_id)
                    data["enabled_skills"] = enabled_skills
                    with open(lock_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                logger.error(f"更新 skills-lock.json 失败: {e}")

        return f"✅ 技能 '{skill_id}' 已成功创建并激活！目录: {skill_path}"

    except Exception as e:
        logger.error(f"创建技能失败: {e}", exc_info=True)
        return f"❌ 创建技能失败: {str(e)}"

def handle_request(action, **kwargs):
    """
    Butler 技能处理入口。

    支持 'create' (生成模板) 动作，其他高级开发动作通过阅读 SKILL.md 指引执行。
    """
    logger.info(f"技能创作助手收到动作: {action}")

    if action == "create":
        skill_id = kwargs.get("skill_id")
        if not skill_id and "entities" in kwargs:
            skill_id = kwargs["entities"].get("skill_id")

        if not skill_id:
            return "错误：缺少必要的参数 'skill_id'。"

        name = kwargs.get("name")
        description = kwargs.get("description")
        return create_skill(skill_id, name, description)

    if action == "init":
        return "技能创作助手已就绪。您可以创建新技能模板，或参考 SKILL.md 进行高级技能开发与优化。"

    return f"动作 '{action}' 已通过 SKILL.md 指引加载或由 create 逻辑处理。请直接在工作流中执行相关指令。"
