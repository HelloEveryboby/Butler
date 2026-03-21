import os
import json
import csv
from datetime import datetime
from package.core_utils.log_manager import LogManager
from plugin.plugin_interface import AbstractPlugin, PluginResult

logging = LogManager.get_logger(__name__)

# 任务类
class Task:
    def __init__(self, description, due_date=None, tags=None, priority=1):
        self.description = description  # 任务描述
        self.due_date = due_date  # 截止日期
        self.completed = False  # 完成状态
        self.tags = tags if tags else []  # 标签
        self.priority = priority  # 优先级

    def mark_completed(self):
        self.completed = True  # 标记为已完成

    def __str__(self):
        return f"{self.description} (Due: {self.due_date}, Completed: {self.completed}, Tags: {', '.join(self.tags)}, Priority: {self.priority})"

# 待办事项插件       
class TodoPlugin(AbstractPlugin):
    def __init__(self):
        self.name = "TodoPlugin"
        self.chinese_name = "待办事项"
        self.description = "管理简单的待办事项列表"
        self.parameters = {"action": "str", "task": "str", "priority": "int"}
        self.todo_list = []  # 待办事项列表
        self.load_todo_list()  # 加载待办事项

    def valid(self) -> bool:
        return True

    def init(self, logging):
        self.logger = LogManager.get_logger(self.name)
        
    def get_name(self):
        return self.name

    def get_chinese_name(self):
        return self.chinese_name

    def get_description(self):
        return self.description

    def get_parameters(self):
        return self.parameters

    def on_startup(self):
        self.logger.info("TodoPlugin 开始.")

    def on_shutdown(self):
        self.save_todo_list()  # 保存待办事项
        self.logger.info("TodoPlugin 关闭.")

    def on_pause(self):
        self.logger.info("TodoPlugin 停顿了一下.")

    def on_resume(self):
        self.logger.info("TodoPlugin 恢复.")

    def save_todo_list(self):
        # 保存待办事项到 JSON 文件
        with open('todo_list.json', 'w') as f:
            json.dump([{"description": task.description, 
                         "due_date": task.due_date.isoformat() if task.due_date else None, 
                         "completed": task.completed, 
                         "tags": task.tags,
                         "priority": task.priority} for task in self.todo_list], f)

    def load_todo_list(self):
        # 从 JSON 文件加载待办事项
        if os.path.exists('todo_list.json'):
            with open('todo_list.json', 'r') as f:
                tasks = json.load(f)
                for task in tasks:
                    due_date = datetime.fromisoformat(task["due_date"]) if task["due_date"] else None
                    task_obj = Task(task["description"], due_date, task["tags"], task["priority"])
                    task_obj.completed = task["completed"]
                    self.todo_list.append(task_obj)

    def export_to_csv(self):
        # 导出待办事项到 CSV 文件
        with open('todo_list.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Description', 'Due Date', 'Completed', 'Tags', 'Priority'])
            for task in self.todo_list:
                writer.writerow([task.description, 
                                 task.due_date.isoformat() if task.due_date else '', 
                                 task.completed, 
                                 ', '.join(task.tags),
                                 task.priority])

    def import_from_csv(self):
        # 从 CSV 文件导入待办事项
        with open('todo_list.csv', 'r') as f:
            reader = csv.reader(f)
            next(reader)  # 跳过表头
            for row in reader:
                task_obj = Task(row[0], datetime.fromisoformat(row[1]) if row[1] else None, row[3].split(', ') if row[3] else [], int(row[4]))
                task_obj.completed = row[2] == 'True'
                self.todo_list.append(task_obj)

    def get_commands(self) -> list[str]:
        return ["添加待办事项", "列出待办事项", "删除待办事项", "完成待办事项", "搜索待办事项", "导出待办事项", "导入待办事项"]

    def run(self, takecommand: str, args: dict) -> PluginResult:
        task_description = args.get("task")
        priority = args.get("priority", 1)
        
        if "add" in takecommand or "添加" in takecommand:
            # 添加任务
            if not task_description:
                return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="Task parameter is missing")
            new_task = Task(task_description, priority=priority)
            self.todo_list.append(new_task)
            result = f"任务 '{task_description}' 添加到待办事项列表"

        elif "list" in takecommand or "列出" in takecommand:
            # 列出任务
            result = "Todo list:\n" + "\n".join(str(task) for task in self.todo_list)
        
        elif "remove" in takecommand or "删除" in takecommand:
            if not task_description:
                return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="Task parameter is missing")
            for task in self.todo_list:
                if task.description == task_description:
                    self.todo_list.remove(task)
                    result = f"任务 '{task_description}' 从待办事项列表中删除"
                    break
            else:
                result = f"任务 '{task_description}' 未在待办事项列表中找到"
        
        elif "complete" in takecommand or "完成" in takecommand:
            # 标记任务为已完成
            if not task_description:
                return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="Task parameter is missing")
            for task in self.todo_list:
                if task.description == task_description:
                    task.mark_completed()
                    result = f"任务 '{task_description}' 标记为已完成"
                    break
            else:
                result = f"任务 '{task_description}' 未在待办事项列表中找到"

        elif "search" in takecommand or "搜索" in takecommand:
            # 搜索任务
            if not task_description:
                return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="Task parameter is missing")
            matching_tasks = [task.description for task in self.todo_list if task_description in task.description]
            result = "匹配的任务:\n" + "\n".join(matching_tasks) if matching_tasks else "未找到匹配的任务"

        elif "export" in takecommand or "导出" in takecommand:
            # 导出到 CSV 文件
            self.export_to_csv()
            result = "待办事项已导出到 todo_list.csv"

        elif "import" in takecommand or "导入" in takecommand:
            # 从 CSV 文件导入
            self.import_from_csv()
            result = "待办事项已从 todo_list.csv 导入"

        else:
            return PluginResult.new(result=None, need_call_brain=False, success=False, error_message="Invalid action")

        return PluginResult.new(result=result, need_call_brain=False, success=True)
