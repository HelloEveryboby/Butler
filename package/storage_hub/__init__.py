"""
Cloud Storage Aggregation Engine (Storage Hub)
极简云驱动聚合引擎 - 支持阿里云、AWS S3、本地文件系统
"""

from .storage_hub import StorageHub
from .drivers.abstract_driver import AbstractDriver
from .drivers.local_driver import LocalDriver
from .drivers.aliyun_driver import AliyunDriver
from .drivers.aws_driver import AWSDriver

__all__ = [
    'StorageHub',
    'AbstractDriver',
    'LocalDriver',
    'AliyunDriver',
    'AWSDriver',
]

__version__ = '1.0.0'
