import os
import json
import logging
from datetime import datetime
from .abstract_plugin import AbstractPlugin

class Task:
    def __init__(self, description, due_date=None, tags=None, priority=1, completed=False):
        self.description = description
        self.due_date = due_date
        self.tags = tags if tags else []
        self.priority = priority
        self.completed = completed

    def to_dict(self):
        return {
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "tags": self.tags,
            "priority": self.priority,
            "completed": self.completed,
        }

    @staticmethod
    def from_dict(data):
        due_date_str = data.get("due_date")
        due_date = datetime.fromisoformat(due_date_str) if due_date_str else None
        return Task(
            description=data.get("description", ""),
            due_date=due_date,
            tags=data.get("tags", []),
            priority=data.get("priority", 1),
            completed=data.get("completed", False)
        )

    def __str__(self):
        status = "✓" if self.completed else " "
        due_str = self.due_date.strftime('%Y-%m-%d') if self.due_date else "No due date"
        return f"[{status}] {self.description} (Priority: {self.priority}, Due: {due_str})"

class TodoPlugin(AbstractPlugin):
    def __init__(self):
        self.todo_file = "todolist.json"
        self.tasks = []

    def get_name(self) -> str:
        return "TodoPlugin"

    def valid(self) -> bool:
        return True

    def init(self, logger: logging.Logger):
        self.logger = logger
        self.load_tasks()
        self.logger.info("TodoPlugin initialized.")

    def load_tasks(self):
        if os.path.exists(self.todo_file):
            try:
                with open(self.todo_file, 'r', encoding='utf-8') as f:
                    tasks_data = json.load(f)
                    self.tasks = [Task.from_dict(data) for data in tasks_data]
            except Exception as e:
                self.logger.error(f"Failed to load todo list: {e}")

    def save_tasks(self):
        try:
            with open(self.todo_file, 'w', encoding='utf-8') as f:
                json.dump([task.to_dict() for task in self.tasks], f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save todo list: {e}")

    def get_commands(self) -> list[str]:
        return ["todo", "待办事项"]

    def run(self, command: str, args: dict) -> str:
        action = args.get("action", "list")
        description = args.get("description")
        
        if action == "add":
            if not description:
                return "Error: Please provide a description for the task."
            self.tasks.append(Task(description, priority=args.get("priority", 1)))
            self.save_tasks()
            return f"Added task: '{description}'"

        elif action == "list":
            if not self.tasks:
                return "Your todo list is empty."
            return "Your todo list:\n" + "\n".join(f"  {i}: {task}" for i, task in enumerate(self.tasks))

        elif action == "complete":
            try:
                index = int(args.get("index"))
                if 0 <= index < len(self.tasks):
                    self.tasks[index].completed = True
                    self.save_tasks()
                    return f"Completed task: '{self.tasks[index].description}'"
                return f"Error: Invalid index {index}."
            except (ValueError, TypeError, KeyError):
                return "Error: Please provide a valid index to complete."

        elif action == "delete":
            try:
                index = int(args.get("index"))
                if 0 <= index < len(self.tasks):
                    deleted = self.tasks.pop(index)
                    self.save_tasks()
                    return f"Deleted task: '{deleted.description}'"
                return f"Error: Invalid index {index}."
            except (ValueError, TypeError, KeyError):
                return "Error: Please provide a valid index to delete."

        else:
            return "Usage: todo --action [add|list|complete|delete] --description <text> --index <number>"

    def stop(self):
        pass

    def cleanup(self):
        self.save_tasks()
        self.logger.info("TodoPlugin cleaned up and tasks saved.")

    def status(self) -> str:
        pending_tasks = sum(1 for task in self.tasks if not task.completed)
        return f"active - {pending_tasks} pending tasks out of {len(self.tasks)}"
