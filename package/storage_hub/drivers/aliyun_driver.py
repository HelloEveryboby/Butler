"""Alibaba Cloud (Aliyun) OSS storage driver."""

from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class AliyunDriver:
    """Driver for Alibaba Cloud OSS storage."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Aliyun OSS driver.
        
        Args:
            config: Configuration dict with keys:
                - access_key_id: OSS access key
                - access_key_secret: OSS secret key
                - endpoint: OSS endpoint URL
                - bucket: Bucket name
        """
        self.config = config
        self.access_key_id = config.get('access_key_id')
        self.access_key_secret = config.get('access_key_secret')
        self.endpoint = config.get('endpoint')
        self.bucket = config.get('bucket')
        self.auth = None
        self.oss_client = None
        self.connected = False
        
        try:
            import oss2
            self.oss2 = oss2
        except ImportError:
            logger.error("oss2 not installed. Install with: pip install oss2")
            self.oss2 = None
    
    def connect(self) -> bool:
        """Establish connection to Aliyun OSS."""
        if not self.oss2:
            logger.error("oss2 library not available")
            return False
        
        try:
            # Create auth object
            self.auth = self.oss2.Auth(self.access_key_id, self.access_key_secret)
            
            # Create bucket object
            self.oss_client = self.oss2.Bucket(self.auth, self.endpoint, self.bucket)
            
            # Test connection by listing objects (with limit 1)
            self.oss_client.list_objects(max_keys=1)
            
            self.connected = True
            logger.info(f"Connected to Aliyun OSS bucket: {self.bucket}")
            return True
        except Exception as e:
            logger.error(f"Aliyun connection error: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Close connection to Aliyun OSS."""
        self.connected = False
        return True
    
    def put(self, path: str, data: bytes) -> bool:
        """Upload file content to Aliyun OSS."""
        if not self.connected:
            logger.error("Not connected to Aliyun OSS")
            return False
        
        try:
            self.oss_client.put_object(path, data)
            logger.debug(f"Uploaded to Aliyun: {path}")
            return True
        except Exception as e:
            logger.error(f"Aliyun put error: {e}")
            return False
    
    def put_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file from local filesystem to Aliyun OSS."""
        if not self.connected:
            logger.error("Not connected to Aliyun OSS")
            return False
        
        try:
            self.oss_client.put_object_from_file(remote_path, local_path)
            logger.debug(f"Uploaded file to Aliyun: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"Aliyun put_file error: {e}")
            return False
    
    def get(self, path: str) -> Optional[bytes]:
        """Download file content from Aliyun OSS."""
        if not self.connected:
            logger.error("Not connected to Aliyun OSS")
            return None
        
        try:
            response = self.oss_client.get_object(path)
            data = response.read()
            logger.debug(f"Downloaded from Aliyun: {path}")
            return data
        except Exception as e:
            logger.error(f"Aliyun get error: {e}")
            return None
    
    def get_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from Aliyun OSS to local filesystem."""
        if not self.connected:
            logger.error("Not connected to Aliyun OSS")
            return False
        
        try:
            self.oss_client.get_object_to_file(remote_path, local_path)
            logger.debug(f"Downloaded from Aliyun to: {local_path}")
            return True
        except Exception as e:
            logger.error(f"Aliyun get_file error: {e}")
            return False
    
    def list_objects(self, prefix: str = "", recursive: bool = False) -> List[Dict[str, Any]]:
        """List objects in Aliyun OSS bucket."""
        if not self.connected:
            logger.error("Not connected to Aliyun OSS")
            return []
        
        try:
            objects = []
            delimiter = "" if recursive else "/"
            
            for obj in self.oss2.ObjectIterator(
                self.oss_client,
                prefix=prefix,
                delimiter=delimiter
            ):
                objects.append({
                    'name': obj.key,
                    'size': obj.size,
                    'modified_time': obj.last_modified.timestamp() if obj.last_modified else None,
                    'etag': obj.etag,
                    'storage_class': obj.storage_class,
                })
            
            return objects
        except Exception as e:
            logger.error(f"Aliyun list_objects error: {e}")
            return []
    
    def exists(self, path: str) -> bool:
        """Check if object exists in Aliyun OSS."""
        if not self.connected:
            logger.error("Not connected to Aliyun OSS")
            return False
        
        try:
            return self.oss_client.object_exists(path)
        except Exception as e:
            logger.error(f"Aliyun exists error: {e}")
            return False
    
    def delete(self, path: str) -> bool:
        """Delete object from Aliyun OSS."""
        if not self.connected:
            logger.error("Not connected to Aliyun OSS")
            return False
        
        try:
            self.oss_client.delete_object(path)
            logger.debug(f"Deleted from Aliyun: {path}")
            return True
        except Exception as e:
            logger.error(f"Aliyun delete error: {e}")
            return False
    
    def copy(self, src_path: str, dst_path: str) -> bool:
        """Copy object within Aliyun OSS bucket."""
        if not self.connected:
            logger.error("Not connected to Aliyun OSS")
            return False
        
        try:
            self.oss_client.copy_object(self.bucket, src_path, dst_path)
            logger.debug(f"Copied in Aliyun: {src_path} -> {dst_path}")
            return True
        except Exception as e:
            logger.error(f"Aliyun copy error: {e}")
            return False
    
    def get_url(self, path: str, expires_in: int = 3600) -> Optional[str]:
        """Get signed URL for object in Aliyun OSS."""
        if not self.connected:
            logger.error("Not connected to Aliyun OSS")
            return None
        
        try:
            url = self.oss_client.sign_url('GET', path, expires_in)
            logger.debug(f"Generated signed URL for: {path}")
            return url
        except Exception as e:
            logger.error(f"Aliyun get_url error: {e}")
            return None
    
    def get_metadata(self, path: str) -> Optional[Dict[str, Any]]:
        """Get object metadata from Aliyun OSS."""
        if not self.connected:
            logger.error("Not connected to Aliyun OSS")
            return None
        
        try:
            response = self.oss_client.head_object(path)
            return {
                'name': path,
                'size': response.content_length,
                'modified_time': response.last_modified.timestamp() if response.last_modified else None,
                'content_type': response.content_type,
                'etag': response.etag,
            }
        except Exception as e:
            logger.error(f"Aliyun get_metadata error: {e}")
            return None
