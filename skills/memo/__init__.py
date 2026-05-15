import os
import json
from datetime import datetime

MEMO_FILE = "memos.json"

def load_memos():
    if os.path.exists(MEMO_FILE):
        try:
            with open(MEMO_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []

def save_memos(memos):
    with open(MEMO_FILE, 'w', encoding='utf-8') as f:
        json.dump(memos, f, ensure_ascii=False, indent=2)

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    content = entities.get("content") or kwargs.get("content")
    memo_id = entities.get("memo_id") or kwargs.get("memo_id")
    show_all = entities.get("show_all") or kwargs.get("show_all", False)

    memos = load_memos()
    result = ""

    if "添加" in action:
        if not content: return "内容不能为空。"
        memos.append({
            "id": len(memos) + 1,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "completed": False
        })
        result = f"已添加: {content}"
    elif "列出" in action:
        if not memos: return "当前没有备忘录。"
        result = "备忘录列表:\n"
        for m in memos:
            if show_all or not m["completed"]:
                status = "✓" if m["completed"] else " "
                result += f"{m['id']}. [{status}] {m['content']} ({m['timestamp']})\n"
    elif "完成" in action:
        try:
            mid = int(memo_id)
            for m in memos:
                if m["id"] == mid:
                    m["completed"] = True
                    result = f"已标记完成: {m['content']}"
                    break
            else: result = "未找到 ID。"
        except: return "无效 ID。"
    elif "删除" in action:
        try:
            mid = int(memo_id)
            for i, m in enumerate(memos):
                if m["id"] == mid:
                    content = m["content"]
                    del memos[i]
                    result = f"已删除: {content}"
                    break
            else: result = "未找到 ID。"
        except: return "无效 ID。"
    else:
        result = "未知动作。"

    save_memos(memos)
    return result
