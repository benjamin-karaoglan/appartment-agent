"""
MinIO service for object storage operations.
"""

import logging
from io import BytesIO
from typing import Optional, BinaryIO
from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)


class MinIOService:
    """Service for MinIO object storage operations."""

    def __init__(self):
        """Initialize MinIO client."""
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self):
        """Ensure the documents bucket exists."""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")
            else:
                logger.debug(f"MinIO bucket already exists: {self.bucket}")
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {e}")
            raise

    def upload_file(
        self,
        file_data: bytes,
        object_name: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> str:
        """
        Upload a file to MinIO.

        Args:
            file_data: Binary file data
            object_name: Name for the object in MinIO (e.g., "documents/123/file.pdf")
            content_type: MIME type of the file
            metadata: Optional metadata dict to attach to the object

        Returns:
            The object name (key) in MinIO

        Raises:
            S3Error: If upload fails
        """
        try:
            file_size = len(file_data)
            file_stream = BytesIO(file_data)

            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_name,
                data=file_stream,
                length=file_size,
                content_type=content_type,
                metadata=metadata or {}
            )

            logger.info(f"Uploaded file to MinIO: {object_name} ({file_size} bytes)")
            return object_name

        except S3Error as e:
            logger.error(f"Error uploading file to MinIO: {e}")
            raise

    def download_file(self, object_name: str) -> bytes:
        """
        Download a file from MinIO.

        Args:
            object_name: Name of the object in MinIO

        Returns:
            Binary file data

        Raises:
            S3Error: If download fails
        """
        try:
            response = self.client.get_object(self.bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()

            logger.info(f"Downloaded file from MinIO: {object_name} ({len(data)} bytes)")
            return data

        except S3Error as e:
            logger.error(f"Error downloading file from MinIO: {e}")
            raise

    def download_file_stream(self, object_name: str) -> BinaryIO:
        """
        Download a file from MinIO as a stream.

        Args:
            object_name: Name of the object in MinIO

        Returns:
            Binary stream

        Raises:
            S3Error: If download fails
        """
        try:
            response = self.client.get_object(self.bucket, object_name)
            logger.info(f"Opened stream for file from MinIO: {object_name}")
            return response

        except S3Error as e:
            logger.error(f"Error downloading file stream from MinIO: {e}")
            raise

    def delete_file(self, object_name: str) -> bool:
        """
        Delete a file from MinIO.

        Args:
            object_name: Name of the object in MinIO

        Returns:
            True if deleted successfully

        Raises:
            S3Error: If deletion fails
        """
        try:
            self.client.remove_object(self.bucket, object_name)
            logger.info(f"Deleted file from MinIO: {object_name}")
            return True

        except S3Error as e:
            logger.error(f"Error deleting file from MinIO: {e}")
            raise

    def file_exists(self, object_name: str) -> bool:
        """
        Check if a file exists in MinIO.

        Args:
            object_name: Name of the object in MinIO

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            logger.error(f"Error checking file existence: {e}")
            raise

    def get_file_url(self, object_name: str, expires_in: int = 3600) -> str:
        """
        Generate a presigned URL for accessing a file.

        Args:
            object_name: Name of the object in MinIO
            expires_in: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL

        Raises:
            S3Error: If URL generation fails
        """
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=object_name,
                expires=expires_in
            )
            logger.debug(f"Generated presigned URL for {object_name}")
            return url

        except S3Error as e:
            logger.error(f"Error generating presigned URL: {e}")
            raise

    def list_files(self, prefix: str = "") -> list[str]:
        """
        List files in MinIO with optional prefix filter.

        Args:
            prefix: Optional prefix to filter objects (e.g., "documents/123/")

        Returns:
            List of object names

        Raises:
            S3Error: If listing fails
        """
        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket,
                prefix=prefix,
                recursive=True
            )
            object_names = [obj.object_name for obj in objects]
            logger.info(f"Listed {len(object_names)} objects with prefix '{prefix}'")
            return object_names

        except S3Error as e:
            logger.error(f"Error listing files from MinIO: {e}")
            raise


# Singleton instance
_minio_service: Optional[MinIOService] = None


def get_minio_service() -> MinIOService:
    """Get or create MinIO service singleton."""
    global _minio_service
    if _minio_service is None:
        _minio_service = MinIOService()
    return _minio_service
