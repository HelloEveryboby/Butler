import os
import json
import csv
from datetime import datetime

class Task:
    def __init__(self, description, due_date=None, tags=None, priority=1):
        self.description = description
        self.due_date = due_date
        self.completed = False
        self.tags = tags if tags else []
        self.priority = priority

    def mark_completed(self):
        self.completed = True

    def __str__(self):
        return f"{self.description} (Due: {self.due_date}, Completed: {self.completed}, Tags: {', '.join(self.tags)}, Priority: {self.priority})"

def load_todo_list():
    todo_list = []
    if os.path.exists('todo_list.json'):
        try:
            with open('todo_list.json', 'r', encoding='utf-8') as f:
                tasks = json.load(f)
                for task in tasks:
                    due_date = datetime.fromisoformat(task["due_date"]) if task["due_date"] else None
                    task_obj = Task(task["description"], due_date, task["tags"], task["priority"])
                    task_obj.completed = task["completed"]
                    todo_list.append(task_obj)
        except:
            pass
    return todo_list

def save_todo_list(todo_list):
    with open('todo_list.json', 'w', encoding='utf-8') as f:
        json.dump([{"description": task.description,
                     "due_date": task.due_date.isoformat() if task.due_date else None,
                     "completed": task.completed,
                     "tags": task.tags,
                     "priority": task.priority} for task in todo_list], f, ensure_ascii=False, indent=2)

def handle_request(action, **kwargs):
    entities = kwargs.get("entities", {})
    task_description = entities.get("task") or kwargs.get("task")
    priority = int(entities.get("priority") or kwargs.get("priority", 1))

    todo_list = load_todo_list()
    result = ""

    if action == "add" or "添加" in action:
        if not task_description: return "请提供任务描述。"
        new_task = Task(task_description, priority=priority)
        todo_list.append(new_task)
        result = f"任务 '{task_description}' 已添加。"
    elif action == "list" or "列出" in action:
        result = "待办事项列表:\n" + "\n".join(str(task) for task in todo_list) if todo_list else "列表为空。"
    elif action == "remove" or "删除" in action:
        if not task_description: return "请提供要删除的任务描述。"
        for task in todo_list:
            if task.description == task_description:
                todo_list.remove(task)
                result = f"任务 '{task_description}' 已删除。"
                break
        else: result = "未找到该任务。"
    elif action == "complete" or "完成" in action:
        if not task_description: return "请提供要完成的任务描述。"
        for task in todo_list:
            if task.description == task_description:
                task.mark_completed()
                result = f"任务 '{task_description}' 已标记为完成。"
                break
        else: result = "未找到该任务。"
    elif action == "export" or "导出" in action:
        with open('todo_list.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Description', 'Due Date', 'Completed', 'Tags', 'Priority'])
            for task in todo_list:
                writer.writerow([task.description, task.due_date.isoformat() if task.due_date else '', task.completed, ', '.join(task.tags), task.priority])
        result = "已导出到 todo_list.csv。"
    else:
        result = "未知操作。"

    save_todo_list(todo_list)
    return result
