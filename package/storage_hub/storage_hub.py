"""
Core Storage Hub - Cloud Storage Aggregation Engine
极简云驱动聚合引擎 - 统一管理多云存储
"""

from typing import Any, Dict, List, Optional
import logging

from .drivers.abstract_driver import AbstractDriver
from .drivers.local_driver import LocalDriver
from .drivers.aliyun_driver import AliyunDriver
from .drivers.aws_driver import AWSDriver

logger = logging.getLogger(__name__)


class StorageHub:
    """
    Unified cloud storage aggregation engine supporting multiple backends.
    
    Example:
        hub = StorageHub()
        hub.register_driver('local', LocalDriver({'base_path': './data'}))
        hub.register_driver('aliyun', AliyunDriver({...}))
        
        hub.upload('local', 'folder/file.txt', b'content')
        data = hub.download('aliyun', 'folder/file.txt')
    """
    
    def __init__(self):
        """Initialize the storage hub."""
        self.drivers: Dict[str, AbstractDriver] = {}
        self.default_driver = None
        logger.info("StorageHub initialized")

    def init(self):
        """Initialize Storage Hub and run all pending database migrations."""
        from package.storage_hub.migration_manager import MigrationManager
        manager = MigrationManager()
        manager.migrate()
    
    def register_driver(self, name: str, driver: AbstractDriver) -> bool:
        """
        Register a storage driver.
        
        Args:
            name: Driver identifier (e.g., 'local', 'aliyun', 'aws')
            driver: Driver instance
            
        Returns:
            True if registration successful
        """
        try:
            if not driver.connect():
                logger.error(f"Failed to connect driver: {name}")
                return False
            
            self.drivers[name] = driver
            
            if self.default_driver is None:
                self.default_driver = name
            
            logger.info(f"Driver '{name}' registered successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to register driver '{name}': {e}")
            return False
    
    def unregister_driver(self, name: str) -> bool:
        """
        Unregister and disconnect a driver.
        
        Args:
            name: Driver identifier
            
        Returns:
            True if unregistration successful
        """
        try:
            if name in self.drivers:
                self.drivers[name].disconnect()
                del self.drivers[name]
                
                if self.default_driver == name and self.drivers:
                    self.default_driver = next(iter(self.drivers))
                
                logger.info(f"Driver '{name}' unregistered")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to unregister driver '{name}': {e}")
            return False
    
    def set_default_driver(self, name: str) -> bool:
        """
        Set default driver for operations.
        
        Args:
            name: Driver identifier
            
        Returns:
            True if driver exists
        """
        if name in self.drivers:
            self.default_driver = name
            logger.info(f"Default driver set to: {name}")
            return True
        
        logger.error(f"Driver not found: {name}")
        return False
    
    def _get_driver(self, source: Optional[str] = None) -> Optional[AbstractDriver]:
        """Get driver by name or use default."""
        if source is None:
            source = self.default_driver
        
        if source not in self.drivers:
            logger.error(f"Driver not found: {source}")
            return None
        
        return self.drivers[source]
    
    # ==================== Upload Operations ====================
    
    def upload(self, source: str, remote_path: str, data: bytes) -> bool:
        """
        Upload file content to storage.
        
        Args:
            source: Source storage name
            remote_path: Remote file path
            data: File content as bytes
            
        Returns:
            True if upload successful
        """
        driver = self._get_driver(source)
        if not driver:
            return False
        
        return driver.put(remote_path, data)
    
    def upload_file(self, source: str, local_path: str, remote_path: str) -> bool:
        """
        Upload file from local filesystem to storage.
        
        Args:
            source: Source storage name
            local_path: Local file path
            remote_path: Remote file path
            
        Returns:
            True if upload successful
        """
        driver = self._get_driver(source)
        if not driver:
            return False
        
        return driver.put_file(local_path, remote_path)
    
    # ==================== Download Operations ====================
    
    def download(self, source: str, remote_path: str) -> Optional[bytes]:
        """
        Download file content from storage.
        
        Args:
            source: Source storage name
            remote_path: Remote file path
            
        Returns:
            File content as bytes, or None if failed
        """
        driver = self._get_driver(source)
        if not driver:
            return None
        
        return driver.get(remote_path)
    
    def download_file(self, source: str, remote_path: str, local_path: str) -> bool:
        """
        Download file from storage to local filesystem.
        
        Args:
            source: Source storage name
            remote_path: Remote file path
            local_path: Local file path
            
        Returns:
            True if download successful
        """
        driver = self._get_driver(source)
        if not driver:
            return False
        
        return driver.get_file(remote_path, local_path)
    
    # ==================== List Operations ====================
    
    def list_objects(self, source: str, prefix: str = "", recursive: bool = False) -> List[Dict[str, Any]]:
        """
        List objects in storage.
        
        Args:
            source: Source storage name
            prefix: Optional prefix filter
            recursive: Whether to list recursively
            
        Returns:
            List of objects with metadata
        """
        driver = self._get_driver(source)
        if not driver:
            return []
        
        return driver.list_objects(prefix, recursive)
    
    # ==================== Metadata Operations ====================
    
    def exists(self, source: str, path: str) -> bool:
        """Check if object exists in storage."""
        driver = self._get_driver(source)
        if not driver:
            return False
        
        return driver.exists(path)
    
    def get_metadata(self, source: str, path: str) -> Optional[Dict[str, Any]]:
        """Get object metadata."""
        driver = self._get_driver(source)
        if not driver:
            return None
        
        return driver.get_metadata(path)
    
    def get_url(self, source: str, path: str, expires_in: int = 3600) -> Optional[str]:
        """Get signed/presigned URL for object."""
        driver = self._get_driver(source)
        if not driver:
            return None
        
        return driver.get_url(path, expires_in)
    
    # ==================== Delete Operations ====================
    
    def delete(self, source: str, path: str) -> bool:
        """Delete object from storage."""
        driver = self._get_driver(source)
        if not driver:
            return False
        
        return driver.delete(path)
    
    # ==================== Copy Operations ====================
    
    def copy(self, source: str, src_path: str, dst_path: str) -> bool:
        """Copy object within same storage backend."""
        driver = self._get_driver(source)
        if not driver:
            return False
        
        return driver.copy(src_path, dst_path)
    
    def copy_cross_storage(self, src_storage: str, src_path: str, 
                          dst_storage: str, dst_path: str) -> bool:
        """
        Copy object between different storage backends.
        
        Args:
            src_storage: Source storage name
            src_path: Source file path
            dst_storage: Destination storage name
            dst_path: Destination file path
            
        Returns:
            True if copy successful
        """
        try:
            # Download from source
            data = self.download(src_storage, src_path)
            if data is None:
                logger.error(f"Failed to download from {src_storage}: {src_path}")
                return False
            
            # Upload to destination
            if not self.upload(dst_storage, dst_path, data):
                logger.error(f"Failed to upload to {dst_storage}: {dst_path}")
                return False
            
            logger.info(f"Copied: {src_storage}/{src_path} -> {dst_storage}/{dst_path}")
            return True
        except Exception as e:
            logger.error(f"Cross-storage copy error: {e}")
            return False
    
    # ==================== Sync Operations ====================
    
    def sync_directory(self, src_storage: str, src_prefix: str,
                      dst_storage: str, dst_prefix: str, recursive: bool = True) -> int:
        """
        Sync directory from one storage to another.
        
        Args:
            src_storage: Source storage name
            src_prefix: Source directory prefix
            dst_storage: Destination storage name
            dst_prefix: Destination directory prefix
            recursive: Whether to sync recursively
            
        Returns:
            Number of files synced
        """
        try:
            objects = self.list_objects(src_storage, src_prefix, recursive)
            count = 0
            
            for obj in objects:
                if obj.get('is_file', True) or 'is_prefix' not in obj:
                    src_path = obj['name']
                    # Construct destination path
                    rel_path = src_path[len(src_prefix):].lstrip('/')
                    dst_path = f"{dst_prefix}/{rel_path}".lstrip('/')
                    
                    if self.copy_cross_storage(src_storage, src_path, dst_storage, dst_path):
                        count += 1
            
            logger.info(f"Synced {count} files from {src_storage} to {dst_storage}")
            return count
        except Exception as e:
            logger.error(f"Sync directory error: {e}")
            return 0
    
    # ==================== Info Operations ====================
    
    def list_drivers(self) -> List[str]:
        """Get list of registered driver names."""
        return list(self.drivers.keys())
    
    def get_driver_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a registered driver."""
        if name not in self.drivers:
            return None
        
        driver = self.drivers[name]
        return {
            'name': name,
            'type': driver.__class__.__name__,
            'connected': driver.connected if hasattr(driver, 'connected') else True,
            'config_keys': list(driver.config.keys()),
        }
    
    def cleanup(self):
        """Disconnect all drivers and cleanup."""
        for name, driver in self.drivers.items():
            try:
                driver.disconnect()
                logger.info(f"Disconnected driver: {name}")
            except Exception as e:
                logger.error(f"Error disconnecting {name}: {e}")
        
        self.drivers.clear()
        self.default_driver = None
