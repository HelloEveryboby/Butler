import os
import sys
import json
import time
import threading
import hashlib
import urllib.request
import urllib.parse
import http.server
import socket
import re
import shutil
import logging
import zipfile
from typing import Dict, List, Any

# Ensure BeautifulSoup4 and requests are available
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger("DownloaderSkill")

# Path Configuration
DOWNLOADER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(DOWNLOADER_DIR)
DATA_DIR = os.path.join(DOWNLOADER_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(DATA_DIR, "tasks.json")
LOCAL_CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
IS_STANDALONE = False

def get_standalone_status() -> bool:
    global IS_STANDALONE
    return IS_STANDALONE or os.environ.get("BUTLER_DOWNLOADER_STANDALONE") == "1"

def load_local_config() -> Dict[str, Any]:
    if not os.path.exists(LOCAL_CONFIG_PATH):
        return {}
    try:
        with open(LOCAL_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_local_config(config: Dict[str, Any]):
    try:
        with open(LOCAL_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

def get_downloads_dir() -> str:
    cfg = load_local_config()
    custom_path = cfg.get("download_path")
    if custom_path:
        custom_path = os.path.expanduser(custom_path)
        if not os.path.isabs(custom_path):
            custom_path = os.path.abspath(os.path.join(PROJECT_ROOT, custom_path))
        os.makedirs(custom_path, exist_ok=True)
        return custom_path

    # Defaults to ./download/ folder
    path = os.path.join(PROJECT_ROOT, "download")
    os.makedirs(path, exist_ok=True)
    return path

# Global variables
streaming_server_port = 8329
streaming_thread = None
scheduler_thread = None
scheduler_running = False

ACTIVE_DOWNLOADS = {}
active_lock = threading.Lock()

class SafeHTTPRangeHandler(http.server.BaseHTTPRequestHandler):
    """
    A high-fidelity Range-supporting HTTP Server for local streaming and UI serving.
    """
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ["/", "/ui/", "/ui/index.html"]:
            ui_file_path = os.path.join(DOWNLOADER_DIR, "ui", "index.html")
            if os.path.exists(ui_file_path):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(ui_file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "UI File Not Found")
            return

        self.handle_request()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.startswith("/api/"):
            action = parsed.path[5:] # strip "/api/"
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                params = json.loads(body)
            except Exception:
                params = {}

            result = handle_request(action, **params)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
            return

        self.send_error(404, "Not Found")

    def do_HEAD(self):
        self.handle_request(head_only=True)

    def handle_request(self, head_only=False):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/stream":
            self.send_error(404, "Not Found")
            return

        query = urllib.parse.parse_qs(parsed.query)
        task_id = query.get("task_id", [None])[0]
        if not task_id:
            self.send_error(400, "Missing task_id")
            return

        tasks = load_tasks()
        task = tasks.get(task_id)
        if not task:
            self.send_error(404, "Task not found")
            return

        file_path = task.get("file_path")
        if not file_path or not os.path.exists(file_path):
            part_path = file_path + ".part" if file_path else None
            if part_path and os.path.exists(part_path):
                file_path = part_path
            else:
                self.send_error(404, f"File does not exist on disk: {file_path}")
                return

        file_size = os.path.getsize(file_path)
        content_type = "video/mp4"
        if file_path.lower().endswith(".mp3"):
            content_type = "audio/mpeg"
        elif file_path.lower().endswith(".mkv"):
            content_type = "video/x-matroska"

        range_header = self.headers.get("Range")
        start, end = 0, file_size - 1

        is_partial = False
        if range_header:
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                is_partial = True
                start = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))

        if start >= file_size:
            self.send_response(416, "Range Not Satisfiable")
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.end_headers()
            return

        if end >= file_size:
            end = file_size - 1

        content_length = end - start + 1

        if is_partial:
            self.send_response(206, "Partial Content")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        else:
            self.send_response(200, "OK")

        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        if head_only:
            return

        try:
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                chunk_size = 1024 * 64
                while remaining > 0:
                    read_len = min(chunk_size, remaining)
                    data = f.read(read_len)
                    if not data:
                        break
                    self.wfile.write(data)
                    remaining -= len(data)
        except Exception:
            pass


def start_streaming_server():
    global streaming_server_port, streaming_thread
    server_address = ("", streaming_server_port)
    for port in range(8329, 8340):
        try:
            httpd = http.server.ThreadingHTTPServer(("", port), SafeHTTPRangeHandler)
            streaming_server_port = port
            logger.info(f"Stream Streaming Server launched on port {port}")

            def run_server():
                try:
                    httpd.serve_forever()
                except Exception:
                    pass

            streaming_thread = threading.Thread(target=run_server, daemon=True)
            streaming_thread.start()
            break
        except OSError:
            continue


def load_tasks() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load tasks: {e}")
        return {}


def save_tasks(tasks: Dict[str, Any]):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save tasks: {e}")


def calculate_eta(downloaded, total, speed_bytes) -> str:
    if not speed_bytes or speed_bytes <= 0 or total <= 0:
        return "未知"
    remaining_bytes = total - downloaded
    seconds = int(remaining_bytes / speed_bytes)
    if seconds < 60:
        return f"{seconds}秒"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}分{seconds % 60}秒"
    hours = minutes // 60
    return f"{hours}时{minutes % 60}分"


def format_bytes(bytes_count) -> str:
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.1f} GB"


class SegmentedDownloader:
    """
    Core Multi-threaded HTTP/HTTPS segment downloader.
    """
    def __init__(self, task_id: str, url: str, file_path: str, max_workers: int = 16, chunk_size: int = 1024 * 64):
        self.task_id = task_id
        self.url = url
        self.file_path = file_path
        self.max_workers = max_workers
        self.chunk_size = chunk_size

        self.total_size = 0
        self.downloaded_size = 0
        self.supports_range = False
        self.stop_event = threading.Event()
        self.error_message = ""

        self.start_time = 0.0
        self.speed = 0.0
        self.speed_limit = 0

    def precheck(self):
        try:
            req = urllib.request.Request(self.url, method="HEAD")
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            with urllib.request.urlopen(req, timeout=10) as response:
                self.total_size = int(response.headers.get("Content-Length", 0))
                accept_ranges = response.headers.get("Accept-Ranges", "")
                self.supports_range = "bytes" in accept_ranges or response.headers.get("Content-Range") is not None
        except Exception:
            try:
                req = urllib.request.Request(self.url)
                req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                req.add_header("Range", "bytes=0-0")
                with urllib.request.urlopen(req, timeout=10) as response:
                    self.supports_range = (response.status == 206)
                    content_range = response.headers.get("Content-Range", "")
                    if content_range and "/" in content_range:
                        self.total_size = int(content_range.split("/")[-1])
            except Exception as e:
                logger.error(f"Precheck failed: {e}")
                self.supports_range = False

    def download_segment(self, seg_index: int, start: int, end: int, part_path: str, progress_list: List[int]):
        retries = 3
        while retries > 0 and not self.stop_event.is_set():
            try:
                current_start = start
                mode = "wb"
                if os.path.exists(part_path):
                    current_start += os.path.getsize(part_path)
                    mode = "ab"
                    if current_start > end:
                        progress_list[seg_index] = end - start + 1
                        return

                if current_start > end:
                    return

                req = urllib.request.Request(self.url)
                req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                req.add_header("Range", f"bytes={current_start}-{end}")

                with urllib.request.urlopen(req, timeout=15) as conn, open(part_path, mode) as f:
                    while not self.stop_event.is_set():
                        t0 = time.time()
                        data = conn.read(self.chunk_size)
                        if not data:
                            break

                        f.write(data)
                        chunk_len = len(data)
                        self.downloaded_size += chunk_len
                        progress_list[seg_index] += chunk_len

                        if self.speed_limit > 0:
                            seg_speed_limit = self.speed_limit / min(self.max_workers, 4)
                            elapsed = time.time() - t0
                            expected_time = chunk_len / seg_speed_limit
                            if elapsed < expected_time:
                                time.sleep(expected_time - elapsed)

                return
            except Exception as e:
                retries -= 1
                logger.warning(f"Segment {seg_index} failed, retrying ({3-retries}/3). Error: {e}")
                time.sleep(1)

        if retries == 0 and not self.stop_event.is_set():
            self.error_message = f"分块 {seg_index} 下载重试失败"
            self.stop_event.set()

    def download_sequential(self):
        retries = 3
        part_path = self.file_path + ".part"
        while retries > 0 and not self.stop_event.is_set():
            try:
                current_start = 0
                mode = "wb"
                if os.path.exists(part_path):
                    current_start = os.path.getsize(part_path)
                    mode = "ab"

                req = urllib.request.Request(self.url)
                req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                if current_start > 0:
                    req.add_header("Range", f"bytes={current_start}-")

                with urllib.request.urlopen(req, timeout=20) as conn, open(part_path, mode) as f:
                    while not self.stop_event.is_set():
                        t0 = time.time()
                        data = conn.read(self.chunk_size)
                        if not data:
                            break

                        f.write(data)
                        chunk_len = len(data)
                        self.downloaded_size += chunk_len

                        if self.speed_limit > 0:
                            elapsed = time.time() - t0
                            expected_time = chunk_len / self.speed_limit
                            if elapsed < expected_time:
                                time.sleep(expected_time - elapsed)

                if not self.stop_event.is_set():
                    shutil.move(part_path, self.file_path)
                return
            except Exception as e:
                retries -= 1
                logger.warning(f"Sequential download failed: {e}. Retrying...")
                time.sleep(2)

        if retries == 0:
            self.error_message = "单线程顺序下载失败，请检查网络"
            self.stop_event.set()

    def run(self):
        self.start_time = time.time()
        self.precheck()

        # Ensure parent directory exists (mkdir -p)
        parent_dir = os.path.dirname(self.file_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        tasks = load_tasks()
        if self.task_id in tasks:
            tasks[self.task_id]["total_size"] = self.total_size
            tasks[self.task_id]["status"] = "downloading"
            save_tasks(tasks)

        def monitor_loop():
            last_bytes = 0
            last_time = time.time()
            while not self.stop_event.is_set() and self.downloaded_size < (self.total_size or 1):
                time.sleep(0.8)
                now = time.time()
                dt = now - last_time
                if dt <= 0:
                    continue
                db = self.downloaded_size - last_bytes
                self.speed = db / dt

                cur_tasks = load_tasks()
                if self.task_id in cur_tasks:
                    cur_tasks[self.task_id]["downloaded_size"] = self.downloaded_size
                    progress_val = int((self.downloaded_size / self.total_size) * 100) if self.total_size > 0 else 0
                    cur_tasks[self.task_id]["progress"] = progress_val
                    cur_tasks[self.task_id]["speed"] = format_bytes(int(self.speed)) + "/s"
                    cur_tasks[self.task_id]["eta"] = calculate_eta(self.downloaded_size, self.total_size, self.speed)
                    save_tasks(cur_tasks)

                last_bytes = self.downloaded_size
                last_time = now

        m_thread = threading.Thread(target=monitor_loop, daemon=True)
        m_thread.start()

        if self.supports_range and self.total_size > 0:
            seg_size = self.total_size // self.max_workers
            threads = []
            part_paths = []
            progress_list = [0] * self.max_workers

            for i in range(self.max_workers):
                start = i * seg_size
                end = self.total_size - 1 if i == self.max_workers - 1 else (i + 1) * seg_size - 1
                part_path = f"{self.file_path}.part_{i}"
                part_paths.append(part_path)

                t = threading.Thread(
                    target=self.download_segment,
                    args=(i, start, end, part_path, progress_list),
                    daemon=True
                )
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            if not self.stop_event.is_set():
                try:
                    with open(self.file_path, "wb") as outfile:
                        for p_path in part_paths:
                            if os.path.exists(p_path):
                                with open(p_path, "rb") as infile:
                                    shutil.copyfileobj(infile, outfile)
                                os.remove(p_path)
                except Exception as e:
                    self.error_message = f"分块合并失败: {e}"
                    self.stop_event.set()
        else:
            self.download_sequential()

        self.stop_event.set()
        final_tasks = load_tasks()
        if self.task_id in final_tasks:
            if self.error_message:
                final_tasks[self.task_id]["status"] = "failed"
                final_tasks[self.task_id]["error_message"] = self.error_message
                final_tasks[self.task_id]["speed"] = "0 B/s"
            else:
                final_tasks[self.task_id]["status"] = "completed"
                final_tasks[self.task_id]["progress"] = 100
                final_tasks[self.task_id]["downloaded_size"] = self.total_size or self.downloaded_size
                final_tasks[self.task_id]["speed"] = "0 B/s"
                final_tasks[self.task_id]["eta"] = "已完成"

                try:
                    h = hashlib.md5()
                    with open(self.file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(65536), b''):
                            h.update(chunk)
                    final_tasks[self.task_id]["md5"] = h.hexdigest()
                except Exception:
                    pass
            save_tasks(final_tasks)


def run_scheduler_daemon():
    global scheduler_running
    scheduler_running = True
    while scheduler_running:
        time.sleep(10)
        tasks = load_tasks()
        now_time = time.strftime("%H:%M")

        launched_any = False
        for task_id, t in tasks.items():
            if t.get("status") == "scheduled" and t.get("scheduled_time") == now_time:
                t["status"] = "pending"
                save_tasks(tasks)
                launch_task_thread(task_id)
                launched_any = True


def launch_task_thread(task_id: str):
    tasks = load_tasks()
    task = tasks.get(task_id)
    if not task:
        return

    url = task.get("url", "")
    file_path = task.get("file_path")

    # Ensure output directory exists before launching thread (mkdir -p)
    if file_path:
        out_dir = os.path.dirname(file_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

    stop_flag = threading.Event()

    downloader = SegmentedDownloader(
        task_id=task_id,
        url=url,
        file_path=file_path,
        max_workers=16
    )
    downloader.stop_event = stop_flag

    t = threading.Thread(target=downloader.run, daemon=True)
    t.start()
    with active_lock:
        ACTIVE_DOWNLOADS[task_id] = {"thread": t, "stop_flag": stop_flag, "manager": downloader}


def handle_request(action: str, **kwargs) -> Any:
    global scheduler_thread, scheduler_running
    if not scheduler_running:
        scheduler_thread = threading.Thread(target=run_scheduler_daemon, daemon=True)
        scheduler_thread.start()
        start_streaming_server()

    if action == "get_status":
        return {
            "status": "ok",
            "standalone": get_standalone_status(),
            "download_path": get_downloads_dir(),
            "config": load_local_config()
        }

    elif action == "add_task":
        url = kwargs.get("url", "").strip()
        save_location = kwargs.get("save_location") or kwargs.get("output_dir") or kwargs.get("output")
        category = kwargs.get("category", "other")
        scheduled_time = kwargs.get("scheduled_time")

        if not url:
            return {"error": "链接不能为空"}

        parsed = urllib.parse.urlparse(url)
        name = os.path.basename(parsed.path) or "downloaded_file"
        name = urllib.parse.unquote(name)

        # Handle custom save location or default ./download/
        if save_location:
            target_dir = os.path.expanduser(save_location)
            if not os.path.isabs(target_dir):
                target_dir = os.path.abspath(os.path.join(PROJECT_ROOT, target_dir))
        else:
            target_dir = get_downloads_dir()

        # Execute mkdir -p automatically
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, name)

        task_id = f"dl_{int(time.time() * 1000)}"

        tasks = load_tasks()
        tasks[task_id] = {
            "id": task_id,
            "url": url,
            "name": name,
            "status": "scheduled" if scheduled_time else "pending",
            "total_size": 0,
            "downloaded_size": 0,
            "progress": 0,
            "speed": "0 B/s",
            "eta": "排队中" if not scheduled_time else "已定时",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "file_path": file_path,
            "category": category,
            "is_p2p": False,
            "scheduled_time": scheduled_time,
            "speed_limited": False
        }
        save_tasks(tasks)

        if not scheduled_time:
            launch_task_thread(task_id)

        return {"status": "ok", "task_id": task_id, "name": name, "file_path": file_path}

    elif action == "list_tasks":
        return load_tasks()

    elif action == "cli":
        url = kwargs.get("url")
        output = kwargs.get("output") or kwargs.get("save_location")
        daemon = kwargs.get("daemon", False)
        from .cli import download_cli
        tid = download_cli(url, output_dir=output, daemon=daemon)
        return {"status": "ok", "task_id": tid}

    return {"status": "ok"}
