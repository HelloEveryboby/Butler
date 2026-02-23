import json
import os
from .task import Task

class TaskManager:
    """
    负责处理所有任务数据的加载、保存和管理。
    """
    def __init__(self, data_file="tasks.json"):
        """
        初始化任务管理器。

        :param data_file: 用于存储任务数据的JSON文件名。
        """
        # 将数据文件定位在模块的目录内
        self.data_file = os.path.join(os.path.dirname(__file__), data_file)
        self.tasks = self._load_tasks()

    def _load_tasks(self):
        """从JSON文件中加载任务。如果文件不存在，则返回一个空列表。"""
        if not os.path.exists(self.data_file):
            return []
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                tasks_data = json.load(f)
            return [Task.from_dict(data) for data in tasks_data]
        except (json.JSONDecodeError, IOError):
            # 如果文件损坏或无法读取，返回空列表
            return []

    def _save_tasks(self):
        """将所有任务数据保存到JSON文件中。"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump([task.to_dict() for task in self.tasks], f, indent=4, ensure_ascii=False)

    def add_task(self, task, parent_id=None):
        """
        添加一个新任务或子任务。

        :param task: 要添加的 Task 对象。
        :param parent_id: 如果是子任务，则为父任务的ID。
        """
        if parent_id:
            parent_task = self.find_task(parent_id)
            if parent_task:
                parent_task.add_subtask(task)
            else:
                # 如果找不到父任务，就作为一个主任务添加
                self.tasks.append(task)
        else:
            self.tasks.append(task)
        self._save_tasks()

    def find_task(self, task_id):
        """
        递归查找具有指定ID的任务。

        :param task_id: 要查找的任务的ID。
        :return: 找到的 Task 对象，或 None。
        """
        def search(tasks):
            for task in tasks:
                if task.id == task_id:
                    return task
                found = search(task.subtasks)
                if found:
                    return found
            return None
        return search(self.tasks)

    def update_task(self, task_id, title=None, description=None, status=None):
        """
        更新一个现有任务的属性。

        :param task_id: 要更新的任务的ID。
        :param title: 新的任务标题。
        :param description: 新的任务描述。
        :param status: 新的任务状态。
        """
        task = self.find_task(task_id)
        if task:
            if title is not None:
                task.title = title
            if description is not None:
                task.description = description
            if status is not None:
                task.status = status
            self._save_tasks()
            return True
        return False

    def delete_task(self, task_id):
        """
        删除一个任务及其所有子任务。

        :param task_id: 要删除的任务的ID。
        """
        def remove_from(tasks):
            for i, task in enumerate(tasks):
                if task.id == task_id:
                    del tasks[i]
                    return True
                if remove_from(task.subtasks):
                    return True
            return False

        if remove_from(self.tasks):
            self._save_tasks()
            return True
        return False

    def get_all_tasks(self):
        """返回所有主任务的列表。"""
        return self.tasks