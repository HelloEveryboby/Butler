"""AWS S3 storage driver."""

from typing import Any, Dict, List, Optional
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class AWSDriver:
    """Driver for AWS S3 storage."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize AWS S3 driver.

        Args:
            config: Configuration dict with keys:
                - access_key_id: AWS access key
                - secret_access_key: AWS secret key
                - region: AWS region (default: us-east-1)
                - bucket: S3 bucket name
                - endpoint_url: Optional custom endpoint URL (for S3-compatible services)
        """
        self.config = config
        self.access_key_id = config.get('access_key_id')
        self.secret_access_key = config.get('secret_access_key')
        self.region = config.get('region', 'us-east-1')
        self.bucket = config.get('bucket')
        self.endpoint_url = config.get('endpoint_url')
        self.s3_client = None
        self.connected = False

        try:
            import boto3
            self.boto3 = boto3
        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            self.boto3 = None

    def connect(self) -> bool:
        """Establish connection to AWS S3."""
        if not self.boto3:
            logger.error("boto3 library not available")
            return False

        try:
            kwargs = {
                'service_name': 's3',
                'region_name': self.region,
                'aws_access_key_id': self.access_key_id,
                'aws_secret_access_key': self.secret_access_key,
            }

            if self.endpoint_url:
                kwargs['endpoint_url'] = self.endpoint_url

            self.s3_client = self.boto3.client(**kwargs)

            # Test connection by listing objects with max_keys=1
            self.s3_client.list_objects_v2(Bucket=self.bucket, MaxKeys=1)

            self.connected = True
            logger.info(f"Connected to AWS S3 bucket: {self.bucket}")
            return True
        except Exception as e:
            logger.error(f"AWS S3 connection error: {e}")
            return False

    def disconnect(self) -> bool:
        """Close connection to AWS S3."""
        self.connected = False
        return True

    def put(self, path: str, data: bytes) -> bool:
        """Upload file content to AWS S3."""
        if not self.connected:
            logger.error("Not connected to AWS S3")
            return False

        try:
            self.s3_client.put_object(Bucket=self.bucket, Key=path, Body=data)
            logger.debug(f"Uploaded to AWS S3: {path}")
            return True
        except Exception as e:
            logger.error(f"AWS S3 put error: {e}")
            return False

    def put_file(self, local_path: str, remote_path: str) -> bool:
        """Upload file from local filesystem to AWS S3."""
        if not self.connected:
            logger.error("Not connected to AWS S3")
            return False

        try:
            self.s3_client.upload_file(local_path, self.bucket, remote_path)
            logger.debug(f"Uploaded file to AWS S3: {remote_path}")
            return True
        except Exception as e:
            logger.error(f"AWS S3 put_file error: {e}")
            return False

    def get(self, path: str) -> Optional[bytes]:
        """Download file content from AWS S3."""
        if not self.connected:
            logger.error("Not connected to AWS S3")
            return None

        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=path)
            data = response['Body'].read()
            logger.debug(f"Downloaded from AWS S3: {path}")
            return data
        except Exception as e:
            logger.error(f"AWS S3 get error: {e}")
            return None

    def get_file(self, remote_path: str, local_path: str) -> bool:
        """Download file from AWS S3 to local filesystem."""
        if not self.connected:
            logger.error("Not connected to AWS S3")
            return False

        try:
            self.s3_client.download_file(self.bucket, remote_path, local_path)
            logger.debug(f"Downloaded from AWS S3 to: {local_path}")
            return True
        except Exception as e:
            logger.error(f"AWS S3 get_file error: {e}")
            return False

    def list_objects(self, prefix: str = "", recursive: bool = False) -> List[Dict[str, Any]]:
        """List objects in AWS S3 bucket."""
        if not self.connected:
            logger.error("Not connected to AWS S3")
            return []

        try:
            objects = []
            delimiter = "" if recursive else "/"

            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix,
                Delimiter=delimiter
            )

            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects.append({
                            'name': obj['Key'],
                            'size': obj['Size'],
                            'modified_time': obj['LastModified'].timestamp(),
                            'etag': obj['ETag'],
                            'storage_class': obj.get('StorageClass'),
                        })

                if 'CommonPrefixes' in page and not recursive:
                    for prefix_info in page['CommonPrefixes']:
                        objects.append({
                            'name': prefix_info['Prefix'],
                            'size': 0,
                            'modified_time': None,
                            'is_prefix': True,
                        })

            return objects
        except Exception as e:
            logger.error(f"AWS S3 list_objects error: {e}")
            return []

    def exists(self, path: str) -> bool:
        """Check if object exists in AWS S3."""
        if not self.connected:
            logger.error("Not connected to AWS S3")
            return False

        try:
            self.s3_client.head_object(Bucket=self.bucket, Key=path)
            return True
        except self.s3_client.exceptions.NoSuchKey:
            return False
        except Exception as e:
            logger.error(f"AWS S3 exists error: {e}")
            return False

    def delete(self, path: str) -> bool:
        """Delete object from AWS S3."""
        if not self.connected:
            logger.error("Not connected to AWS S3")
            return False

        try:
            self.s3_client.delete_object(Bucket=self.bucket, Key=path)
            logger.debug(f"Deleted from AWS S3: {path}")
            return True
        except Exception as e:
            logger.error(f"AWS S3 delete error: {e}")
            return False

    def copy(self, src_path: str, dst_path: str) -> bool:
        """Copy object within AWS S3 bucket."""
        if not self.connected:
            logger.error("Not connected to AWS S3")
            return False

        try:
            copy_source = {'Bucket': self.bucket, 'Key': src_path}
            self.s3_client.copy_object(CopySource=copy_source, Bucket=self.bucket, Key=dst_path)
            logger.debug(f"Copied in AWS S3: {src_path} -> {dst_path}")
            return True
        except Exception as e:
            logger.error(f"AWS S3 copy error: {e}")
            return False

    def get_url(self, path: str, expires_in: int = 3600) -> Optional[str]:
        """Get presigned URL for object in AWS S3."""
        if not self.connected:
            logger.error("Not connected to AWS S3")
            return None

        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': path},
                ExpiresIn=expires_in
            )
            logger.debug(f"Generated presigned URL for: {path}")
            return url
        except Exception as e:
            logger.error(f"AWS S3 get_url error: {e}")
            return None

    def get_metadata(self, path: str) -> Optional[Dict[str, Any]]:
        """Get object metadata from AWS S3."""
        if not self.connected:
            logger.error("Not connected to AWS S3")
            return None

        try:
            response = self.s3_client.head_object(Bucket=self.bucket, Key=path)
            return {
                'name': path,
                'size': response['ContentLength'],
                'modified_time': response['LastModified'].timestamp(),
                'content_type': response.get('ContentType'),
                'etag': response['ETag'],
                'storage_class': response.get('StorageClass'),
            }
        except Exception as e:
            logger.error(f"AWS S3 get_metadata error: {e}")
            return None
