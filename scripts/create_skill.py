import os
import json

def quick_create():
    name = input("输入新技能 ID (如 hardware_ctrl): ").strip()
    path = os.path.join("skills", name)
    os.makedirs(path, exist_ok=True)

    # 写入初始文件
    with open(os.path.join(path, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({
            "skill_id": name,
            "name": name.replace("_", " ").title(),
            "description": f"Skill for {name}",
            "actions": ["init"],
            "keywords": [name]
        }, f, indent=4, ensure_ascii=False)

    with open(os.path.join(path, "__init__.py"), "w", encoding="utf-8") as f:
        f.write('def handle_request(action, **kwargs):\n    return f"Skill {action} executed"')

    # 更新 lock 文件
    lock = "skills-lock.json"
    data = {"enabled_skills": []}
    if os.path.exists(lock):
        with open(lock, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if "enabled_skills" not in data:
                    data = {"enabled_skills": []}
            except:
                data = {"enabled_skills": []}

    if name not in data["enabled_skills"]:
        data["enabled_skills"].append(name)
        with open(lock, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"✨ 技能 {name} 已创建并激活！")

if __name__ == "__main__": quick_create()
