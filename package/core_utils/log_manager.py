import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import sys
import os
from pathlib import Path
import gzip
import shutil
import datetime
import traceback
import json
import base64
from typing import Dict, Any, Optional, Callable

class LogManager:
    """
    全功能的日志管理类，支持多种日志级别、自动轮转、JSON格式化及性能监控。

    该类采用了单例模式的配置管理，确保整个系统中的日志行为一致。
    支持：
    - 按文件大小 (RotatingFileHandler) 或按时间 (TimedRotatingFileHandler) 轮转日志。
    - 自动压缩旧的日志文件 (.gz)。
    - 输出 JSON 格式日志，便于结构化分析。
    - 装饰器模式记录函数执行性能。
    - 自定义过滤器（如敏感数据过滤）。
    """
    _configured = False
    _loggers = {}
    _log_dir = "logs"
    _log_level = logging.INFO
    _max_bytes = 10 * 1024 * 1024  # 默认 10MB
    _backup_count = 3
    _log_rotation = 'size'  # 可选 'size' 或 'time'
    _time_rotation_params = {'when': 'midnight', 'interval': 1, 'backupCount': 7}
    _custom_filters = {}
    _log_formats = {}
    _context_data = {}
    _enable_console = True
    _enable_file_logging = True
    _compression_enabled = False
    _stealth_log_path = ".sys_temp.db" # Hidden log file

    @classmethod
    def _configure(cls, **kwargs):
        """
        内部配置方法，初始化日志系统。

        Args:
            **kwargs: 覆盖默认配置的参数，如 log_dir, log_level 等。
        """
        if cls._configured:
            return

        # 更新配置参数
        cls._update_config(**kwargs)
        
        # 创建日志目录
        Path(cls._log_dir).mkdir(parents=True, exist_ok=True)
        
        # 获取根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(cls._log_level)
        
        # 清除现有处理器（防止在某些环境下重复添加）
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 定义默认日志格式
        default_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 配置控制台输出
        if cls._enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(default_formatter)
            root_logger.addHandler(console_handler)
        
        # 配置多渠道文件日志
        if cls._enable_file_logging:
            # 1. 汇总日志：包含所有级别的记录
            cls._add_file_handler(root_logger, "all.log", logging.NOTSET, default_formatter)
            
            # 2. DEBUG 专用：仅记录调试信息
            cls._add_file_handler(root_logger, "debug.log", logging.DEBUG, 
                                 cls._get_formatter('debug'), 
                                 lambda r: r.levelno == logging.DEBUG)
            
            # 3. INFO 专用：普通运行信息
            cls._add_file_handler(root_logger, "info.log", logging.INFO, 
                                 cls._get_formatter('info'), 
                                 lambda r: r.levelno == logging.INFO)
            
            # 4. WARNING 专用：警告记录
            cls._add_file_handler(root_logger, "warning.log", logging.WARNING, 
                                 cls._get_formatter('warning'), 
                                 lambda r: r.levelno == logging.WARNING)
            
            # 5. ERROR 专用：所有错误和异常
            cls._add_file_handler(root_logger, "error.log", logging.ERROR, 
                                 cls._get_formatter('error'))
            
            # 6. CRITICAL 专用：严重系统故障
            cls._add_file_handler(root_logger, "critical.log", logging.CRITICAL, 
                                 cls._get_formatter('critical'), 
                                 lambda r: r.levelno == logging.CRITICAL)
            
            # 7. JSON 格式化输出：适合程序读取和分析
            json_formatter = cls._get_formatter('json') or cls._create_json_formatter()
            cls._add_file_handler(root_logger, "application.json", logging.INFO, json_formatter)
        
        cls._configured = True
    
    @classmethod
    def _update_config(cls, **kwargs):
        """更新内部配置参数"""
        if 'log_dir' in kwargs:
            cls._log_dir = kwargs['log_dir']
        if 'log_level' in kwargs:
            cls._log_level = kwargs['log_level']
        if 'max_bytes' in kwargs:
            cls._max_bytes = kwargs['max_bytes']
        if 'backup_count' in kwargs:
            cls._backup_count = kwargs['backup_count']
        if 'log_rotation' in kwargs:
            cls._log_rotation = kwargs['log_rotation']
        if 'time_rotation_params' in kwargs:
            cls._time_rotation_params = kwargs['time_rotation_params']
        if 'custom_filters' in kwargs:
            cls._custom_filters.update(kwargs['custom_filters'])
        if 'log_formats' in kwargs:
            cls._log_formats.update(kwargs['log_formats'])
        if 'enable_console' in kwargs:
            cls._enable_console = kwargs['enable_console']
        if 'enable_file_logging' in kwargs:
            cls._enable_file_logging = kwargs['enable_file_logging']
        if 'compression_enabled' in kwargs:
            cls._compression_enabled = kwargs['compression_enabled']
    
    @classmethod
    def _add_file_handler(cls, logger: logging.Logger, filename: str, 
                         level: int, formatter: logging.Formatter, 
                         filter_func: Optional[Callable] = None):
        """
        向指定的 Logger 添加文件处理器。

        Args:
            logger: 日志记录器实例。
            filename: 日志文件名。
            level: 日志过滤级别。
            formatter: 格式化器。
            filter_func: 可选的自定义过滤函数。
        """
        file_path = os.path.join(cls._log_dir, filename)
        
        if cls._log_rotation == 'time':
            handler = TimedRotatingFileHandler(
                filename=file_path,
                **cls._time_rotation_params
            )
        else:  # 默认为按大小轮转
            handler = RotatingFileHandler(
                filename=file_path,
                maxBytes=cls._max_bytes,
                backupCount=cls._backup_count,
                encoding='utf-8'
            )
        
        handler.setLevel(level)
        handler.setFormatter(formatter)
        
        if filter_func:
            handler.addFilter(filter_func)
        
        if cls._compression_enabled and cls._log_rotation == 'size':
            # 开启自动压缩支持
            handler.namer = cls._compress_namer
        
        logger.addHandler(handler)
    
    @classmethod
    def _compress_namer(cls, name: str) -> str:
        """为轮转的文件名添加 .gz 后缀"""
        if name.endswith(".gz"):
            return name
        return name + ".gz"
    
    @classmethod
    def _rotate_and_compress(cls, handler: RotatingFileHandler):
        """手动触发轮转并执行压缩逻辑"""
        handler.doRollover()
        if cls._compression_enabled:
            for i in range(1, cls._backup_count + 1):
                log_path = f"{handler.baseFilename}.{i}"
                if os.path.exists(log_path):
                    cls._compress_file(log_path)
    
    @staticmethod
    def _compress_file(file_path: str):
        """使用 gzip 压缩指定文件并删除原文件"""
        compressed_path = f"{file_path}.gz"
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(file_path)
    
    @classmethod
    def _get_formatter(cls, log_type: str) -> logging.Formatter:
        """从预定义的格式配置中获取格式化器"""
        if log_type in cls._log_formats:
            fmt = cls._log_formats[log_type].get('format')
            datefmt = cls._log_formats[log_type].get('datefmt')
            return logging.Formatter(fmt, datefmt)
        return None
    
    @staticmethod
    def _create_json_formatter() -> logging.Formatter:
        """创建自定义的 JSON 日志格式化器"""
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_record = {
                    'timestamp': datetime.datetime.now().isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'file': f"{record.filename}:{record.lineno}",
                    'message': record.getMessage(),
                    'stack_trace': traceback.format_exc() if record.exc_info else None,
                    'extra': getattr(record, 'extra', {})
                }
                return json.dumps(log_record, ensure_ascii=False)
        
        return JsonFormatter()
    
    @classmethod
    def log_stealth(cls, message: str, level: str = "INFO"):
        """
        Records a log entry into the hidden stealth database/file.
        Uses XOR-based obfuscation.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "t": timestamp,
            "l": level,
            "m": message
        }

        raw_str = json.dumps(log_entry)
        # Use a secondary obfuscation key (could be linked to core_code in future)
        secret_key = b"BUTLER_STEALTH_2026"

        data = raw_str.encode()
        obfuscated_bytes = bytes(data[i] ^ secret_key[i % len(secret_key)] for i in range(len(data)))
        obfuscated = base64.b64encode(obfuscated_bytes).decode()

        try:
            with open(cls._stealth_log_path, "a", encoding="utf-8") as f:
                f.write(obfuscated + "\n")
        except Exception:
            pass

    @classmethod
    def get_logger(cls, name: Optional[str] = None) -> logging.Logger:
        """
        获取一个配置好的日志记录器（Logger）实例。

        Args:
            name: 记录器名称。通常使用 __name__。

        Returns:
            logging.Logger: 记录器实例。
        """
        if not cls._configured:
            cls._configure()
        
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            # 添加预设的自定义过滤器
            for filter_name, filter_func in cls._custom_filters.items():
                logger.addFilter(filter_func)
            cls._loggers[name] = logger
        return cls._loggers[name]
    
    @classmethod
    def configure(cls, **kwargs):
        """
        公开的自定义配置接口。

        注意：必须在第一次调用 get_logger 之前调用此方法，否则将抛出异常。

        Args:
            **kwargs: 配置参数。
        """
        if not cls._configured:
            cls._update_config(**kwargs)
        else:
            raise RuntimeError("日志系统已经初始化，无法重新配置。请在第一次获取 logger 之前调用 configure。")
    
    @classmethod
    def add_context(cls, key: str, value: Any):
        """
        向后续的所有日志中添加全局上下文信息（如 request_id）。

        Args:
            key: 字段名。
            value: 字段值。
        """
        cls._context_data[key] = value
        
        # 为所有已存在的记录器更新格式
        for logger in cls._loggers.values():
            for handler in logger.handlers:
                old_formatter = handler.formatter
                if old_formatter:
                    new_format = old_formatter._fmt + f" | %({key})s"
                    handler.setFormatter(logging.Formatter(
                        new_format,
                        datefmt=old_formatter.datefmt
                    ))
    
    @classmethod
    def remove_context(cls, key: str):
        """从上下文数据中移除指定的键"""
        if key in cls._context_data:
            del cls._context_data[key]
    
    @classmethod
    def log_performance(cls, func):
        """
        性能统计装饰器，记录函数的执行耗时。

        Usage:
            @LogManager.log_performance
            def my_function():
                ...
        """
        def wrapper(*args, **kwargs):
            logger = cls.get_logger("performance")
            start_time = datetime.datetime.now()
            result = func(*args, **kwargs)
            end_time = datetime.datetime.now()
            elapsed = (end_time - start_time).total_seconds() * 1000  # 转换为毫秒
            
            logger.info(f"PERFORMANCE: 函数 {func.__name__} 执行耗时: {elapsed:.2f}ms")
            return result
        return wrapper
    
    @classmethod
    def manual_rotate(cls):
        """手动对当前所有的文件处理器执行轮转操作"""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, (RotatingFileHandler, TimedRotatingFileHandler)):
                if isinstance(handler, RotatingFileHandler):
                    cls._rotate_and_compress(handler)
                else:
                    handler.doRollover()

# 预配置一些通用的过滤器
LogManager._custom_filters = {
    # 敏感信息过滤器：自动隐藏包含 password, key 等字样的日志消息
    'sensitive_data_filter': lambda record: not any(
        secret in str(record.msg).lower()
        for secret in ['password', 'secret_key', 'api_key']
    )
}

# 预定义几种常用的日志输出格式
LogManager._log_formats = {
    'json': {
        'format': None  # 使用内部 JsonFormatter
    },
    'debug': {
        'format': '%(asctime)s | DEBUG | %(name)s | %(filename)s:%(lineno)d | %(message)s | %(funcName)s'
    },
    'error': {
        'format': '%(asctime)s | ERROR | %(name)s | %(filename)s:%(lineno)d | %(message)s | %(exc_info)s'
    }
}
