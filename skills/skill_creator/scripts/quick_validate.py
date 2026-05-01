#!/usr/bin/env python3
"""
技能快速验证脚本 - 精简版
"""

import sys
import os
import re
import yaml
from pathlib import Path

def validate_skill(skill_path):
    """对技能进行基础验证"""
    skill_path = Path(skill_path)

    # 检查 SKILL.md 是否存在
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, "未找到 SKILL.md"

    # 读取并验证前置元数据
    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith('---'):
        return False, "未找到 YAML 前置元数据"

    # 提取前置元数据
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, "前置元数据格式无效"

    frontmatter_text = match.group(1)

    # 解析 YAML 前置元数据
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            return False, "前置元数据必须是一个 YAML 字典"
    except yaml.YAMLError as e:
        return False, f"前置元数据中的 YAML 无效: {e}"

    # 定义允许的属性
    ALLOWED_PROPERTIES = {'name', 'description', 'license', 'allowed-tools', 'metadata', 'compatibility'}

    # 检查是否存在意外属性（排除 metadata 下的嵌套键）
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"SKILL.md 前置元数据中存在意外键: {', '.join(sorted(unexpected_keys))}。 "
            f"允许的属性有: {', '.join(sorted(ALLOWED_PROPERTIES))}"
        )

    # 检查必填字段
    if 'name' not in frontmatter:
        return False, "前置元数据中缺失 'name'"
    if 'description' not in frontmatter:
        return False, "前置元数据中缺失 'description'"

    # 提取并验证名称
    name = frontmatter.get('name', '')
    if not isinstance(name, str):
        return False, f"名称必须是字符串，得到的是 {type(name).__name__}"
    name = name.strip()
    if name:
        # 检查命名规范 (kebab-case: 小写字母加连字符)
        if not re.match(r'^[a-z0-9-]+$', name):
            return False, f"名称 '{name}' 应符合 kebab-case 规范（仅限小写字母、数字和连字符）"
        if name.startswith('-') or name.endswith('-') or '--' in name:
            return False, f"名称 '{name}' 不能以连字符开头/结尾，也不能包含连续的连字符"
        # 检查名称长度（规范最大 64 字符）
        if len(name) > 64:
            return False, f"名称太长（{len(name)} 字符）。最大限制为 64 字符。"

    # 提取并验证描述
    description = frontmatter.get('description', '')
    if not isinstance(description, str):
        return False, f"描述必须是字符串，得到的是 {type(description).__name__}"
    description = description.strip()
    if description:
        # 检查尖括号
        if '<' in description or '>' in description:
            return False, "描述不能包含尖括号 (< 或 >)"
        # 检查描述长度（规范最大 1024 字符）
        if len(description) > 1024:
            return False, f"描述太长（{len(description)} 字符）。最大限制为 1024 字符。"

    # 验证 compatibility 字段（可选）
    compatibility = frontmatter.get('compatibility', '')
    if compatibility:
        if not isinstance(compatibility, str):
            return False, f"兼容性信息必须是字符串，得到的是 {type(compatibility).__name__}"
        if len(compatibility) > 500:
            return False, f"兼容性信息太长（{len(compatibility)} 字符）。最大限制为 500 字符。"

    return True, "技能有效！"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python quick_validate.py <技能目录>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
