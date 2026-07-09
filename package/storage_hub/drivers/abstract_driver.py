"""Abstract base class for storage drivers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, BinaryIO


class AbstractDriver(ABC):
    """Abstract base class for all storage drivers."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the driver with configuration.
        
        Args:
            config: Configuration dictionary specific to each driver
        """
        self.config = config
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the storage backend.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """
        Close connection to the storage backend.
        
        Returns:
            True if disconnection successful
        """
        pass
    
    @abstractmethod
    def put(self, path: str, data: bytes) -> bool:
        """
        Upload file to storage.
        
        Args:
            path: Remote file path
            data: File content as bytes
            
        Returns:
            True if upload successful
        """
        pass
    
    @abstractmethod
    def put_file(self, local_path: str, remote_path: str) -> bool:
        """
        Upload file from local filesystem to storage.
        
        Args:
            local_path: Local file path
            remote_path: Remote file path in storage
            
        Returns:
            True if upload successful
        """
        pass
    
    @abstractmethod
    def get(self, path: str) -> Optional[bytes]:
        """
        Download file from storage.
        
        Args:
            path: Remote file path
            
        Returns:
            File content as bytes, or None if failed
        """
        pass
    
    @abstractmethod
    def get_file(self, remote_path: str, local_path: str) -> bool:
        """
        Download file from storage to local filesystem.
        
        Args:
            remote_path: Remote file path in storage
            local_path: Local file path to save to
            
        Returns:
            True if download successful
        """
        pass
    
    @abstractmethod
    def list_objects(self, prefix: str = "", recursive: bool = False) -> List[Dict[str, Any]]:
        """
        List objects in storage.
        
        Args:
            prefix: Optional prefix to filter objects
            recursive: Whether to list recursively
            
        Returns:
            List of objects with metadata (name, size, modified_time, etc.)
        """
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Check if object exists in storage.
        
        Args:
            path: Remote file path
            
        Returns:
            True if object exists
        """
        pass
    
    @abstractmethod
    def delete(self, path: str) -> bool:
        """
        Delete object from storage.
        
        Args:
            path: Remote file path
            
        Returns:
            True if deletion successful
        """
        pass
    
    @abstractmethod
    def copy(self, src_path: str, dst_path: str) -> bool:
        """
        Copy object within storage.
        
        Args:
            src_path: Source file path
            dst_path: Destination file path
            
        Returns:
            True if copy successful
        """
        pass
    
    @abstractmethod
    def get_url(self, path: str, expires_in: int = 3600) -> Optional[str]:
        """
        Get signed URL for object (if applicable).
        
        Args:
            path: Remote file path
            expires_in: Expiration time in seconds
            
        Returns:
            Signed URL string, or None if not supported
        """
        pass
    
    @abstractmethod
    def get_metadata(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get object metadata.
        
        Args:
            path: Remote file path
            
        Returns:
            Dictionary with metadata (size, modified_time, content_type, etc.)
        """
        pass
