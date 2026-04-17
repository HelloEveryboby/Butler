import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import sys
import os
import uuid
from pathlib import Path
import datetime
import traceback
import json
import base64
from typing import Dict, Any, Optional, Callable
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    Fore = Style = None

import threading

_local_context = threading.local()

class ContextFilter(logging.Filter):
    """
    Injects context-specific information like trace_id into log records.
    """
    def filter(self, record):
        if not hasattr(record, 'trace_id'):
            record.trace_id = getattr(_local_context, 'trace_id', 'N/A')
        return True

class LogManager:
    """
    Refactored LogManager supporting structured logging, trace IDs, and colorized console output.
    """
    _configured = False
    _loggers = {}
    _log_dir = "logs"
    _log_level = logging.INFO
    _max_bytes = 10 * 1024 * 1024
    _backup_count = 5
    _enable_console = True

    @classmethod
    def set_trace_id(cls, trace_id: Optional[str] = None):
        _local_context.trace_id = trace_id or str(uuid.uuid4())[:8]

    @classmethod
    def _configure(cls, **kwargs):
        if cls._configured:
            return

        from butler.core.constants import LOGS_DIR
        cls._log_dir = str(LOGS_DIR)
        
        root_logger = logging.getLogger()
        root_logger.setLevel(cls._log_level)
        
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Formatter with Trace-ID
        log_format = '%(asctime)s | %(levelname)-8s | [%(trace_id)s] | %(name)s | %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
        
        # Console Handler
        if cls._enable_console:
            class ColorFormatter(logging.Formatter):
                LEVEL_COLORS = {
                    logging.DEBUG: Fore.CYAN if Fore else "",
                    logging.INFO: Fore.GREEN if Fore else "",
                    logging.WARNING: Fore.YELLOW if Fore else "",
                    logging.ERROR: Fore.RED if Fore else "",
                    logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT if Fore else ""
                }
                def format(self, record):
                    color = self.LEVEL_COLORS.get(record.levelno, "")
                    orig_levelname = record.levelname
                    record.levelname = f"{color}{orig_levelname}{Style.RESET_ALL if Style else ''}"
                    formatted = super().format(record)
                    record.levelname = orig_levelname # Restore to avoid affecting other handlers
                    return formatted

            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(ColorFormatter(log_format, date_format))
            console_handler.addFilter(ContextFilter())
            root_logger.addHandler(console_handler)
        
        # File Handler (JSON)
        json_path = os.path.join(cls._log_dir, "butler.json")
        file_handler = RotatingFileHandler(json_path, maxBytes=cls._max_bytes, backupCount=cls._backup_count, encoding='utf-8')
        
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_record = {
                    't': datetime.datetime.now().isoformat(),
                    'lvl': record.levelname,
                    'tid': getattr(record, 'trace_id', 'N/A'),
                    'logger': record.name,
                    'msg': record.getMessage(),
                }
                if record.exc_info:
                    log_record['exc'] = traceback.format_exception(*record.exc_info)
                return json.dumps(log_record, ensure_ascii=False)

        file_handler.setFormatter(JsonFormatter())
        file_handler.addFilter(ContextFilter())
        root_logger.addHandler(file_handler)

        cls._configured = True

    @classmethod
    def get_logger(cls, name: Optional[str] = None) -> logging.Logger:
        if not cls._configured:
            cls._configure()
        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)
        return cls._loggers[name]

    @classmethod
    def log_stealth(cls, message: str, level: str = "INFO"):
        # Legacy stealth log implementation remains for compatibility
        pass

# Global convenience
def get_logger(name: str):
    return LogManager.get_logger(name)
