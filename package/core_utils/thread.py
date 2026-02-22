print("Reloading package/thread.py")
import threading
import queue
import os
import time
from package.log_manager import LogManager
import concurrent.futures

logging = LogManager.get_logger(__name__)

# 模拟处理任务的函数
def do_something(task):
    return task.upper()

# 获取大任务列表
def get_tasks():
    return ["task1", "task2", "task3", "task4", "task5", "task6", "task7", "task8", "task9", "task10"]

# 定义任务处理函数
def process_task(task, result_queue, stop_event):
    start_time = time.time()  # 记录任务开始时间
    try:
        task_result = do_something(task)
        result_queue.put(task_result)  # 将处理结果放入队列中
    except Exception as e:
        logging.error(f"处理任务 {task} 时发生错误: {e}")
    finally:
        end_time = time.time()  # 记录任务结束时间
        print(f"任务 {task} 执行完成，耗时 {end_time - start_time} 秒")
        logging.info(f"任务 {task} 执行完成，耗时 {end_time - start_time} 秒")
        # 检查是否需要停止线程
        if stop_event.is_set():
            logging.info("接收到停止信号，线程将退出。")
            return

# 工作线程函数
def worker(subtasks, result_queue, stop_event):
    for task in subtasks:
        if stop_event.is_set():
            break
        process_task(task, result_queue, stop_event)

# 定义任务分解函数
def divide_tasks(tasks, num_threads):
    batch_size = len(tasks) // num_threads
    if batch_size == 0:
        return [tasks]
    # 将大任务分解成多个小任务
    subtasks = []
    for i in range(0, len(tasks), batch_size):
        subtasks.append(tasks[i:i+batch_size])
    return subtasks

# 定义任务分发函数
def dispatch_tasks(tasks, num_threads):
    subtasks = divide_tasks(tasks, num_threads)
    result_queue = queue.Queue()
    stop_event = threading.Event()

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        # Submit tasks to the thread pool
        for subtask_list in subtasks:
            executor.submit(worker, subtask_list, result_queue, stop_event)

    # Collect results from the queue
    results = []
    while not result_queue.empty():
        results.append(result_queue.get())
    return results

def retry_task(task, max_retries=3):
    for i in range(max_retries):
        logging.info(f"第 {i + 1} 次尝试处理任务: {task}")
        try:
            # Create a dummy stop_event for this context
            result = process_task(task, queue.Queue(), threading.Event())
            return result
        except Exception as e:
            logging.error(f"处理任务 {task} 时发生错误: {e}")
            time.sleep(1)  # 等待 1 秒后重试
    logging.error(f"任务 {task} 在重试 {max_retries} 次后仍然失败")       
    return None  # 重试次数最多后任务失败

def dispatch_tasks_with_retry(tasks, num_threads):
    logging.info(f"分发任务并重试: {tasks}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for task in tasks:
            futures.append(executor.submit(retry_task, task))
        results = []
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)
        return results

# 主函数
def process_tasks():
    logging.info("开始任务处理")
    # 定义大任务
    tasks = get_tasks()

    # 定义线程数，根据CPU核心数动态设置
    num_threads = min(len(tasks), os.cpu_count() or 1)
    # 创建一个Event对象，用于控制线程退出
    stop_event = threading.Event()
    stop_event.set()
    # 分发任务并等待结果
    result = dispatch_tasks(tasks, num_threads)
    logging.info(f"任务处理完成，结果: {result}")
    print(result)

if __name__ == "__main__":
    process_tasks()
