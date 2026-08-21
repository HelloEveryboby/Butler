# -*- coding: utf-8 -*-
"""
Proxy loader for skills/downloader referencing top-level downloader package.
"""
from downloader import (
    get_standalone_status,
    get_downloads_dir,
    SegmentedDownloader,
    SafeHTTPRangeHandler,
    start_streaming_server,
    handle_request,
    load_tasks,
    save_tasks,
    run_scheduler_daemon,
    launch_task_thread
)

__all__ = [
    "get_standalone_status",
    "get_downloads_dir",
    "SegmentedDownloader",
    "SafeHTTPRangeHandler",
    "start_streaming_server",
    "handle_request",
    "load_tasks",
    "save_tasks",
    "run_scheduler_daemon",
    "launch_task_thread"
]
