"""
技能创建脚本 (CLI 包装器)
调用 skills/skill_creator 逻辑来创建新技能。
"""
import sys
import os
from pathlib import Path

# 将项目根目录添加到 sys.path 以便导入 butler 模块
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from skills.skill_creator import handle_request

def main():
    print("=== Butler 技能创建助手 ===")
    skill_id = input("输入新技能 ID (例如: hardware_ctrl): ").strip()
    if not skill_id:
        print("错误: 技能 ID 不能为空。")
        return

    name = input("输入显示名称 (直接回车默认使用 ID): ").strip() or None
    description = input("输入描述 (直接回车默认生成): ").strip() or None

    # 直接调用 skill_creator 的 handle_request
    result = handle_request("create", skill_id=skill_id, name=name, description=description)
    print(result)

if __name__ == "__main__":
    main()
