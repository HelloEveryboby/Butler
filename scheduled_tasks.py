import os
import sys
import time
import datetime
import subprocess
import shlex

# Add project root and local lib to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

lib_path = os.path.join(project_root, "lib_external")
if os.path.exists(lib_path) and lib_path not in sys.path:
    sys.path.insert(0, lib_path)

class ScheduledTask:
    def __init__(self, task_name, task_command, schedule_type, schedule_value, data_file_path="task_log.txt", task_function=None):
        """
        初始化定时任务对象

        Args:
            task_name (str): 任务名称
            task_command (str or list): 要执行的命令
            schedule_type (str): 定时类型，可选值：'second', 'minute', 'hour', 'day', 'month', 'year'
            schedule_value (int): 定时值
            data_file_path (str): 用于记录任务执行结果的文件路径
            task_function (function, optional): 要执行的任务函数
        """
        self.task_name = task_name
        self.task_function = task_function
        self.task_command = task_command
        self.schedule_type = schedule_type
        self.schedule_value = schedule_value
        self.last_run_time = None
        self.data_file_path = data_file_path
        self.temp_data_dir = "temp"  # 临时数据文件夹
        self.temp_data_file = os.path.join(self.temp_data_dir, f"{self.task_name}_temp_data.txt")
        
    def _load_last_run_time(self):
        """从文件加载上次运行时间"""
        try:
            with open(f"{self.task_name}_last_run.txt", "r") as f:
                last_run_str = f.read().strip()
                return datetime.datetime.strptime(last_run_str, "%Y-%m-%d %H:%M:%S.%f")
        except FileNotFoundError:
            return None

    def _save_last_run_time(self):
        """将上次运行时间保存到文件"""
        with open(f"{self.task_name}_last_run.txt", "w") as f:
            f.write(self.last_run_time.strftime("%Y-%m-%d %H:%M:%S.%f"))
        
    def get_next_run_time(self):
        """计算下次运行时间"""
        now = datetime.datetime.now()
        if self.last_run_time is None:
            self.last_run_time = now
            return now

        if self.schedule_type == 'second':
            next_run_time = self.last_run_time + datetime.timedelta(seconds=self.schedule_value)
        elif self.schedule_type == 'minute':
            next_run_time = self.last_run_time + datetime.timedelta(minutes=self.schedule_value)
        elif self.schedule_type == 'hour':
            next_run_time = self.last_run_time + datetime.timedelta(hours=self.schedule_value)
        elif self.schedule_type == 'day':
            next_run_time = self.last_run_time + datetime.timedelta(days=self.schedule_value)
        elif self.schedule_type == 'month':
            next_run_time = self.last_run_time + datetime.timedelta(days=30*self.schedule_value)
        elif self.schedule_type == 'year':
            next_run_time = self.last_run_time + datetime.timedelta(days=365*self.schedule_value)
        else:
            raise ValueError(f"Invalid schedule type: {self.schedule_type}")

        if next_run_time < now:
            next_run_time = self.get_next_run_time()

        return next_run_time

    def run(self):
        """执行任务"""
        try:
            if not os.path.exists(self.temp_data_dir):
                os.makedirs(self.temp_data_dir)

            cmd = self.task_command
            if isinstance(cmd, str):
                cmd = shlex.split(cmd)

            with open(self.temp_data_file, "w") as f:
                subprocess.run(cmd, check=True, capture_output=True, text=True, stdout=f)

            self.last_run_time = datetime.datetime.now()
            self._save_last_run_time()
            self._write_log(f"任务 {self.task_name} 执行成功，当前时间：{datetime.datetime.now()}")

            with open(self.data_file_path, "a") as f:
                with open(self.temp_data_file, "r") as temp_f:
                    f.write(f"{datetime.datetime.now()} - 任务 {self.task_name} 执行成功，输出：{temp_f.read()}\n")

        except subprocess.CalledProcessError as e:
            self._write_log(f"任务 {self.task_name} 执行失败，错误代码：{e.returncode}")
            with open(self.data_file_path, "a") as f:
                f.write(f"{datetime.datetime.now()} - 任务 {self.task_name} 执行失败，错误代码：{e.returncode}\n")
        except Exception as e:
            self._write_log(f"任务 {self.task_name} 执行失败：{e}")
            with open(self.data_file_path, "a") as f:
                f.write(f"{datetime.datetime.now()} - 任务 {self.task_name} 执行失败：{e}\n")
        finally:
            if os.path.exists(self.temp_data_file):
                os.remove(self.temp_data_file)

    def _write_log(self, message):
        """写入日志文件"""
        with open("scheduled_tasks.log", "a") as f:
            f.write(f"{datetime.datetime.now()} - {message}\n")

def main():
    tasks = [
        ScheduledTask(task_name='任务1', task_command=['python', 'task1.py'], schedule_type='minute', schedule_value=2),
        ScheduledTask(task_name='任务2', task_command=['python', 'task2.py'], schedule_type='hour', schedule_value=6),
        ScheduledTask(task_name='任务3', task_command=['python', 'task3.py'], schedule_type='day', schedule_value=1),
    ]

    while True:
        next_run_times = [task.get_next_run_time() for task in tasks]
        min_index = next_run_times.index(min(next_run_times))
        next_run_time = next_run_times[min_index]

        sleep_time = (next_run_time - datetime.datetime.now()).total_seconds()
        if sleep_time > 0:
            time.sleep(sleep_time)

        tasks[min_index].run()

if __name__ == '__main__':
    main()
