import os
import json

NOTES_FILE = "notes.json"

def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return []

def save_notes(notes):
    with open(NOTES_FILE, 'w', encoding='utf-8') as f:
        json.dump(notes, f, ensure_ascii=False, indent=2)

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    note = entities.get("note") or kwargs.get("note")
    index = entities.get("index") or kwargs.get("index")

    notes = load_notes()
    result = ""

    if "添加" in action:
        if not note: return "内容不能为空。"
        notes.append(note)
        result = "笔记已添加。"
    elif "查看" in action:
        if not notes: return "没有笔记。"
        result = "\n".join(f"{i}: {n}" for i, n in enumerate(notes))
    elif "搜索" in action:
        if not note: return "提供关键字。"
        found = [n for n in notes if note in n]
        result = "\n".join(found) if found else "未找到。"
    elif "删除" in action:
        try:
            idx = int(index)
            if 0 <= idx < len(notes):
                del_note = notes.pop(idx)
                result = f"已删除: {del_note}"
            else: result = "无效索引。"
        except: return "无效索引。"
    else: result = "未知操作。"

    save_notes(notes)
    return result
