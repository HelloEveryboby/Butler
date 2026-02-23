import uuid
from datetime import datetime

class Task:
    """
    表示一个任务或子任务的数据类。
    """
    def __init__(self, title, description="", status="todo", parent_id=None):
        """
        初始化一个新任务。

        :param title: 任务的标题 (必需)。
        :param description: 任务的详细描述 (可选)。
        :param status: 任务的当前状态 (例如, 'todo', 'in_progress', 'done')。
        :param parent_id: 父任务的ID (如果是子任务)。
        """
        self.id = str(uuid.uuid4())
        self.title = title
        self.description = description
        self.status = status
        self.parent_id = parent_id
        self.created_at = datetime.now().isoformat()
        self.subtasks = []  # 存放子任务对象的列表

    def add_subtask(self, subtask):
        """向任务中添加一个子任务。"""
        if isinstance(subtask, Task):
            subtask.parent_id = self.id
            self.subtasks.append(subtask)
        else:
            raise TypeError("Subtask must be an instance of Task class.")

    def to_dict(self):
        """将任务对象（包括其子任务）序列化为字典。"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "subtasks": [subtask.to_dict() for subtask in self.subtasks]
        }

    @staticmethod
    def from_dict(data):
        """从字典中创建一个任务对象（包括其子任务）。"""
        task = Task(
            title=data.get("title"),
            description=data.get("description"),
            status=data.get("status"),
            parent_id=data.get("parent_id")
        )
        task.id = data.get("id")
        task.created_at = data.get("created_at")
        task.subtasks = [Task.from_dict(sub_data) for sub_data in data.get("subtasks", [])]
        return task