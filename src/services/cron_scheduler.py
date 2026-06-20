import os
import json
import time
import datetime
import threading
import random
from pathlib import Path
from package.core_utils.log_manager import LogManager
from butler.core.battery_manager import battery_manager

logger = LogManager.get_logger("cron_scheduler")

class CronScheduler:
    """
    Butler Cron 调度器 (Cron Scheduler)
    支持持久化任务、多实例锁、以及电池感知的抖动 (Jitter) 机制。
    """
    def __init__(self, tasks_file="data/scheduled_tasks.json", lock_file="data/.cron_lock"):
        self.tasks_file = Path(tasks_file)
        self.lock_file = Path(lock_file)
        self.tasks = {}
        self.running = False
        self._lock = threading.Lock()

        # 确保数据目录存在
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_tasks()

    def _load_tasks(self):
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file, 'r', encoding='utf-8') as f:
                    self.tasks = json.load(f)
            except Exception as e:
                logger.error(f"加载任务失败: {e}")
                self.tasks = {}

    def _save_tasks(self):
        try:
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(self.tasks, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存任务失败: {e}")

    def add_task(self, task_id, interval_seconds, permanent=False, recurring=True):
        """
        添加或更新任务。
        如果任务已存在，保持原有的下次运行时间，除非新间隔会导致下次运行时间失效。
        """
        with self._lock:
            now = time.time()
            if task_id in self.tasks:
                # 更新现有任务
                info = self.tasks[task_id]
                info["interval"] = interval_seconds
                info["permanent"] = permanent
                info["recurring"] = recurring
                # 如果当前 next_run 已经过去太久或未设置，重置它
                if info.get("next_run", 0) < now - (3600 * 24):
                    info["next_run"] = now + interval_seconds
            else:
                # 新建任务
                self.tasks[task_id] = {
                    "interval": interval_seconds,
                    "permanent": permanent,
                    "recurring": recurring,
                    "last_run": 0,
                    "next_run": now + interval_seconds
                }
            self._save_tasks()

    def _try_acquire_lock(self):
        """简单的文件锁机制，防止多进程冲突"""
        current_pid = str(os.getpid())
        if self.lock_file.exists():
            try:
                mtime = self.lock_file.stat().st_mtime
                if time.time() - mtime > 3600:
                    self.lock_file.unlink()
                else:
                    with open(self.lock_file, 'r') as f:
                        owner_pid = f.read().strip()
                        if owner_pid != current_pid:
                            import psutil
                            if not psutil.pid_exists(int(owner_pid)):
                                self.lock_file.unlink()
                            else:
                                return False
            except Exception:
                pass

        try:
            with open(self.lock_file, 'w') as f:
                f.write(current_pid)
            return True
        except Exception:
            return False

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("Cron 调度器已启动")

    def stop(self):
        self.running = False
        if self.lock_file.exists():
            try:
                with open(self.lock_file, 'r') as f:
                    if f.read().strip() == str(os.getpid()):
                        self.lock_file.unlink()
            except Exception: pass

    def _run_loop(self):
        while self.running:
            if self._try_acquire_lock():
                self._check_and_run_tasks()

            # 低功耗调整休眠间隔
            sleep_time = 60 * battery_manager.get_sleep_multiplier()
            time.sleep(sleep_time)

    def _check_and_run_tasks(self):
        now = time.time()
        with self._lock:
            tasks_modified = False
            for task_id, info in self.tasks.items():
                if now >= info.get("next_run", 0):
                    # 电池节流
                    if battery_manager.should_throttle() and not info.get("permanent"):
                        logger.info(f"低电量节流：跳过任务 {task_id}")
                        continue

                    # 执行任务 (触发事件总线)
                    from butler.core.event_bus import event_bus
                    logger.info(f"触发定时任务: {task_id}")
                    event_bus.emit(f"cron:{task_id}")

                    # 更新下次运行时间
                    info["last_run"] = now
                    jitter = info["interval"] * 0.1 * (random.random() * 2 - 1)
                    info["next_run"] = now + info["interval"] + jitter
                    tasks_modified = True

            if tasks_modified:
                self._save_tasks()

cron_scheduler = CronScheduler()
