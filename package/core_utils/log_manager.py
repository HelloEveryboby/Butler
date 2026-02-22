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
from typing import Dict, Any, Optional, Callable

class LogManager:
    """一个综合性的日志管理类。"""
    _configured = False
    _loggers = {}
    _log_dir = "logs"
    _log_level = logging.INFO
    _max_bytes = 10 * 1024 * 1024  # 10MB
    _backup_count = 3
    _log_rotation = 'size'  # 'size' 或 'time'
    _time_rotation_params = {'when': 'midnight', 'interval': 1, 'backupCount': 7}
    _custom_filters = {}
    _log_formats = {}
    _context_data = {}
    _enable_console = True
    _enable_file_logging = True
    _compression_enabled = False

    @classmethod
    def _configure(cls, **kwargs):
        """配置日志系统（只执行一次）"""
        if cls._configured:
            return

        # 更新配置参数
        cls._update_config(**kwargs)
        
        # 创建日志目录
        Path(cls._log_dir).mkdir(parents=True, exist_ok=True)
        
        # 获取根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(cls._log_level)
        
        # 清除现有处理器（防止重复）
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 基本日志格式
        default_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 控制台处理器
        if cls._enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(default_formatter)
            root_logger.addHandler(console_handler)
        
        # 文件日志处理器
        if cls._enable_file_logging:
            # 1. 所有级别日志
            cls._add_file_handler(root_logger, "all.log", logging.NOTSET, default_formatter)
            
            # 2. DEBUG 级别日志
            cls._add_file_handler(root_logger, "debug.log", logging.DEBUG, 
                                 cls._get_formatter('debug'), 
                                 lambda r: r.levelno == logging.DEBUG)
            
            # 3. INFO 级别日志
            cls._add_file_handler(root_logger, "info.log", logging.INFO, 
                                 cls._get_formatter('info'), 
                                 lambda r: r.levelno == logging.INFO)
            
            # 4. WARNING 级别日志
            cls._add_file_handler(root_logger, "warning.log", logging.WARNING, 
                                 cls._get_formatter('warning'), 
                                 lambda r: r.levelno == logging.WARNING)
            
            # 5. ERROR 级别日志
            cls._add_file_handler(root_logger, "error.log", logging.ERROR, 
                                 cls._get_formatter('error'))
            
            # 6. CRITICAL 级别日志
            cls._add_file_handler(root_logger, "critical.log", logging.CRITICAL, 
                                 cls._get_formatter('critical'), 
                                 lambda r: r.levelno == logging.CRITICAL)
            
            # 7. JSON 格式日志
            json_formatter = cls._get_formatter('json') or cls._create_json_formatter()
            cls._add_file_handler(root_logger, "application.json", logging.INFO, json_formatter)
        
        cls._configured = True
    
    @classmethod
    def _update_config(cls, **kwargs):
        """更新配置参数"""
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
        """添加文件处理器"""
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
            # 添加压缩支持
            handler.namer = cls._compress_namer
        
        logger.addHandler(handler)
    
    @classmethod
    def _compress_namer(cls, name: str) -> str:
        """
        用于 RotatingFileHandler 的命名器，会对轮转后的日志文件进行 gzip 压缩。
        """
        if name.endswith(".gz"):
            return name
        return name + ".gz"
    
    @classmethod
    def _rotate_and_compress(cls, handler: RotatingFileHandler):
        """
        轮转并压缩日志文件。
        这是一个自定义轮转器，在标准轮转的基础上增加了压缩功能。
        """
        handler.doRollover()
        if cls._compression_enabled:
            for i in range(1, cls._backup_count + 1):
                log_path = f"{handler.baseFilename}.{i}"
                if os.path.exists(log_path):
                    cls._compress_file(log_path)
    
    @staticmethod
    def _compress_file(file_path: str):
        """压缩文件"""
        compressed_path = f"{file_path}.gz"
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        os.remove(file_path)
    
    @classmethod
    def _get_formatter(cls, log_type: str) -> logging.Formatter:
        """获取自定义日志格式"""
        if log_type in cls._log_formats:
            fmt = cls._log_formats[log_type].get('format')
            datefmt = cls._log_formats[log_type].get('datefmt')
            return logging.Formatter(fmt, datefmt)
        return None
    
    @staticmethod
    def _create_json_formatter() -> logging.Formatter:
        """创建 JSON 格式的日志格式化器"""
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
    def get_logger(cls, name: Optional[str] = None) -> logging.Logger:
        """获取配置好的日志记录器"""
        if not cls._configured:
            cls._configure()
        
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            # 添加自定义过滤器
            for filter_name, filter_func in cls._custom_filters.items():
                logger.addFilter(filter_func)
            cls._loggers[name] = logger
        return cls._loggers[name]
    
    @classmethod
    def configure(cls, **kwargs):
        """自定义日志配置（必须在首次获取日志记录器前调用）"""
        if not cls._configured:
            cls._update_config(**kwargs)
        else:
            raise RuntimeError("日志记录器已配置。Configure 必须在首次使用前调用。")
    
    @classmethod
    def add_context(cls, key: str, value: Any):
        """添加上下文信息到所有日志"""
        cls._context_data[key] = value
        
        # 为所有现有记录器添加上下文
        for logger in cls._loggers.values():
            for handler in logger.handlers:
                old_formatter = handler.formatter
                if old_formatter:
                    # 创建包含上下文的新格式
                    new_format = old_formatter._fmt + f" | %({key})s"
                    handler.setFormatter(logging.Formatter(
                        new_format,
                        datefmt=old_formatter.datefmt
                    ))
    
    @classmethod
    def remove_context(cls, key: str):
        """移除上下文信息"""
        if key in cls._context_data:
            del cls._context_data[key]
    
    @classmethod
    def log_performance(cls, func):
        """性能日志装饰器"""
        def wrapper(*args, **kwargs):
            logger = cls.get_logger("performance")
            start_time = datetime.datetime.now()
            result = func(*args, **kwargs)
            end_time = datetime.datetime.now()
            elapsed = (end_time - start_time).total_seconds() * 1000  # 毫秒
            
            logger.info(f"性能统计: {func.__name__} 执行耗时 {elapsed:.2f}ms")
            return result
        return wrapper
    
    @classmethod
    def manual_rotate(cls):
        """手动轮转所有日志文件"""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, (RotatingFileHandler, TimedRotatingFileHandler)):
                if isinstance(handler, RotatingFileHandler):
                    cls._rotate_and_compress(handler)
                else:
                    handler.doRollover()

# 预配置一些有用的过滤器
LogManager._custom_filters = {
    'sensitive_data_filter': lambda record: not any(
        secret in str(record.msg) 
        for secret in ['password', 'secret_key', 'api_key']
    )
}

# 预定义 JSON 日志格式
LogManager._log_formats = {
    'json': {
        'format': None  # 使用自定义 JSON 格式化器
    },
    'debug': {
        'format': '%(asctime)s | DEBUG | %(name)s | %(filename)s:%(lineno)d | %(message)s | %(funcName)s'
    },
    'error': {
        'format': '%(asctime)s | ERROR | %(name)s | %(filename)s:%(lineno)d | %(message)s | %(exc_info)s'
    }
}
