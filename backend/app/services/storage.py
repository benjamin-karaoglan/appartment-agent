"""
Storage Service - Multi-backend object storage abstraction.

Supports:
- MinIO/S3 for local development
- Google Cloud Storage (GCS) for production

The backend is selected based on STORAGE_BACKEND environment variable.
"""

import logging
from io import BytesIO
from typing import Optional, BinaryIO, Protocol
from datetime import timedelta
from urllib.parse import urlparse
from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.logging import trace_storage_operation

logger = logging.getLogger(__name__)


# =============================================================================
# Storage Backend Interface
# =============================================================================

class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        bucket_name: Optional[str] = None,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> str:
        """Upload a file to storage."""
        pass

    @abstractmethod
    def download_file(self, object_name: str, bucket_name: Optional[str] = None) -> bytes:
        """Download a file from storage."""
        pass

    @abstractmethod
    def delete_file(self, object_name: str, bucket_name: Optional[str] = None) -> bool:
        """Delete a file from storage."""
        pass

    @abstractmethod
    def file_exists(self, object_name: str, bucket_name: Optional[str] = None) -> bool:
        """Check if a file exists."""
        pass

    @abstractmethod
    def get_presigned_url(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
        expiry=None
    ) -> str:
        """Generate a presigned/signed URL for file access."""
        pass

    @abstractmethod
    def list_files(self, prefix: str = "", bucket_name: Optional[str] = None) -> list[str]:
        """List files with optional prefix filter."""
        pass


# =============================================================================
# MinIO/S3 Backend
# =============================================================================

class MinIOBackend(StorageBackend):
    """S3-compatible storage backend using MinIO."""

    @staticmethod
    def _normalize_endpoint(endpoint: str) -> tuple[str, bool]:
        """Normalize endpoint to host:port and determine secure flag."""
        value = endpoint.strip()
        if "://" in value:
            parsed = urlparse(value)
            return parsed.netloc, parsed.scheme == "https"

        parsed = urlparse(f"//{value}")
        if parsed.netloc:
            return parsed.netloc, settings.MINIO_SECURE

        return value, settings.MINIO_SECURE

    def __init__(self):
        """Initialize MinIO client."""
        from minio import Minio

        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )

        # Public client for generating external URLs
        self.public_client = None
        if settings.MINIO_PUBLIC_ENDPOINT:
            public_endpoint, public_secure = self._normalize_endpoint(settings.MINIO_PUBLIC_ENDPOINT)
            self.public_client = Minio(
                public_endpoint,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=public_secure,
                region=settings.MINIO_REGION
            )

        self.default_bucket = settings.MINIO_BUCKET
        self._ensure_bucket_exists(self.default_bucket)
        self._ensure_bucket_exists("photos")

        logger.info(f"MinIO backend initialized with bucket: {self.default_bucket}")

    def _ensure_bucket_exists(self, bucket_name: str) -> None:
        """Ensure a bucket exists."""
        from minio.error import S3Error
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"Created bucket: {bucket_name}")
        except S3Error as e:
            logger.error(f"Error ensuring bucket exists: {e}")
            raise

    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        bucket_name: Optional[str] = None,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> str:
        from minio.error import S3Error
        bucket = bucket_name or self.default_bucket
        file_size = len(file_data)

        with trace_storage_operation(operation="upload", bucket=bucket, filename=filename, file_size=file_size):
            try:
                self.client.put_object(
                    bucket_name=bucket,
                    object_name=filename,
                    data=BytesIO(file_data),
                    length=file_size,
                    content_type=content_type,
                    metadata=metadata or {}
                )
                logger.info(f"Uploaded: {filename} ({file_size} bytes)")
                return filename
            except S3Error as e:
                logger.error(f"Upload failed: {e}")
                raise

    def download_file(self, object_name: str, bucket_name: Optional[str] = None) -> bytes:
        from minio.error import S3Error
        bucket = bucket_name or self.default_bucket

        with trace_storage_operation(operation="download", bucket=bucket, filename=object_name):
            try:
                response = self.client.get_object(bucket, object_name)
                data = response.read()
                response.close()
                response.release_conn()
                logger.info(f"Downloaded: {object_name} ({len(data)} bytes)")
                return data
            except S3Error as e:
                logger.error(f"Download failed: {e}")
                raise

    def delete_file(self, object_name: str, bucket_name: Optional[str] = None) -> bool:
        from minio.error import S3Error
        bucket = bucket_name or self.default_bucket
        try:
            self.client.remove_object(bucket, object_name)
            logger.info(f"Deleted: {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Delete failed: {e}")
            raise

    def file_exists(self, object_name: str, bucket_name: Optional[str] = None) -> bool:
        from minio.error import S3Error
        bucket = bucket_name or self.default_bucket
        try:
            self.client.stat_object(bucket, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise

    def get_presigned_url(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
        expiry=None
    ) -> str:
        from minio.error import S3Error
        bucket = bucket_name or self.default_bucket

        if expiry is None:
            expires = timedelta(hours=1)
        elif isinstance(expiry, timedelta):
            expires = expiry
        else:
            expires = timedelta(seconds=int(expiry))

        try:
            client = self.public_client or self.client
            return client.presigned_get_object(
                bucket_name=bucket,
                object_name=object_name,
                expires=expires
            )
        except S3Error as e:
            logger.error(f"URL generation failed: {e}")
            raise

    def list_files(self, prefix: str = "", bucket_name: Optional[str] = None) -> list[str]:
        from minio.error import S3Error
        bucket = bucket_name or self.default_bucket
        try:
            objects = self.client.list_objects(bucket, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error(f"List failed: {e}")
            raise


# =============================================================================
# Google Cloud Storage Backend
# =============================================================================

class GCSBackend(StorageBackend):
    """Google Cloud Storage backend."""

    def __init__(self):
        """Initialize GCS client."""
        from google.cloud import storage
        from google.auth import default
        
        # Get default credentials to determine the service account email
        self._credentials, self._project = default()
        
        self.client = storage.Client(project=settings.GOOGLE_CLOUD_PROJECT)
        self.documents_bucket = settings.GCS_DOCUMENTS_BUCKET or f"{settings.GOOGLE_CLOUD_PROJECT}-documents"
        self.photos_bucket = settings.GCS_PHOTOS_BUCKET or f"{settings.GOOGLE_CLOUD_PROJECT}-photos"

        # Set default bucket for compatibility with StorageService
        self.default_bucket = self.documents_bucket

        # Get service account email for signing URLs
        self._service_account_email = self._get_service_account_email()

        logger.info(f"GCS backend initialized: documents={self.documents_bucket}, photos={self.photos_bucket}")
        logger.info(f"GCS service account for signing: {self._service_account_email}")
    
    def _get_service_account_email(self) -> str:
        """Get the service account email for URL signing."""
        # Try to get service account email from credentials
        if hasattr(self._credentials, 'service_account_email'):
            return self._credentials.service_account_email
        
        # For compute engine credentials, fetch from metadata server
        try:
            import requests
            response = requests.get(
                'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email',
                headers={'Metadata-Flavor': 'Google'},
                timeout=5
            )
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.warning(f"Could not fetch service account email from metadata: {e}")
        
        # Fallback to default compute engine service account pattern
        return f"{settings.GOOGLE_CLOUD_PROJECT}@appspot.gserviceaccount.com"

    def _get_bucket(self, bucket_name: Optional[str] = None):
        """Get the appropriate bucket."""
        name = bucket_name or self.documents_bucket
        # Map legacy MinIO bucket names to actual GCS bucket names
        if name == "photos":
            name = self.photos_bucket
        elif name == "documents":
            name = self.documents_bucket
        return self.client.bucket(name)

    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        bucket_name: Optional[str] = None,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> str:
        file_size = len(file_data)
        bucket = self._get_bucket(bucket_name)

        with trace_storage_operation(operation="upload", bucket=bucket.name, filename=filename, file_size=file_size):
            try:
                blob = bucket.blob(filename)
                blob.upload_from_string(file_data, content_type=content_type)

                if metadata:
                    blob.metadata = metadata
                    blob.patch()

                logger.info(f"Uploaded to GCS: {filename} ({file_size} bytes)")
                return filename
            except Exception as e:
                logger.error(f"GCS upload failed: {e}")
                raise

    def download_file(self, object_name: str, bucket_name: Optional[str] = None) -> bytes:
        bucket = self._get_bucket(bucket_name)

        with trace_storage_operation(operation="download", bucket=bucket.name, filename=object_name):
            try:
                blob = bucket.blob(object_name)
                data = blob.download_as_bytes()
                logger.info(f"Downloaded from GCS: {object_name} ({len(data)} bytes)")
                return data
            except Exception as e:
                logger.error(f"GCS download failed: {e}")
                raise

    def delete_file(self, object_name: str, bucket_name: Optional[str] = None) -> bool:
        bucket = self._get_bucket(bucket_name)
        try:
            blob = bucket.blob(object_name)
            blob.delete()
            logger.info(f"Deleted from GCS: {object_name}")
            return True
        except Exception as e:
            logger.error(f"GCS delete failed: {e}")
            raise

    def file_exists(self, object_name: str, bucket_name: Optional[str] = None) -> bool:
        bucket = self._get_bucket(bucket_name)
        blob = bucket.blob(object_name)
        return blob.exists()

    def get_presigned_url(
        self,
        object_name: str,
        bucket_name: Optional[str] = None,
        expiry=None
    ) -> str:
        """
        Generate a signed URL for file access.
        
        Uses IAM signBlob API when running with Application Default Credentials
        (e.g., on Cloud Run) since compute engine credentials don't have private keys.
        """
        from google.auth import compute_engine
        from google.auth.transport import requests as google_requests
        
        bucket = self._get_bucket(bucket_name)

        if expiry is None:
            expires = timedelta(hours=1)
        elif isinstance(expiry, timedelta):
            expires = expiry
        else:
            expires = timedelta(seconds=int(expiry))

        try:
            blob = bucket.blob(object_name)
            
            # Check if we're using compute engine credentials (ADC without private key)
            if isinstance(self._credentials, compute_engine.Credentials):
                # Use IAM signBlob API for signing
                # This requires the service account to have the iam.serviceAccounts.signBlob permission
                from google.auth.iam import Signer
                
                # Refresh credentials to ensure we have a valid token
                auth_request = google_requests.Request()
                self._credentials.refresh(auth_request)
                
                # Create IAM-based signer
                signer = Signer(
                    request=auth_request,
                    credentials=self._credentials,
                    service_account_email=self._service_account_email
                )
                
                # Generate signed URL using the IAM signer
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=expires,
                    method="GET",
                    service_account_email=self._service_account_email,
                    access_token=self._credentials.token
                )
            else:
                # Standard signed URL generation with service account key
                url = blob.generate_signed_url(
                    version="v4",
                    expiration=expires,
                    method="GET"
                )
            
            return url
        except Exception as e:
            logger.error(f"GCS URL generation failed: {e}")
            raise

    def list_files(self, prefix: str = "", bucket_name: Optional[str] = None) -> list[str]:
        bucket = self._get_bucket(bucket_name)
        try:
            blobs = bucket.list_blobs(prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"GCS list failed: {e}")
            raise


# =============================================================================
# Storage Service (Facade)
# =============================================================================

class StorageService:
    """
    Unified storage service that delegates to the appropriate backend.

    Backend selection is based on STORAGE_BACKEND environment variable:
    - 'minio' or 's3': Use MinIO/S3 backend (default for local development)
    - 'gcs': Use Google Cloud Storage backend (for production)
    """

    def __init__(self):
        """Initialize the appropriate storage backend."""
        backend_type = settings.STORAGE_BACKEND.lower()

        if backend_type == "gcs":
            try:
                self._backend = GCSBackend()
                logger.info("Using GCS storage backend")
            except ImportError as e:
                logger.warning(
                    f"GCS storage requested but google-cloud-storage not available: {e}. "
                    "Falling back to MinIO. To use GCS, install google-cloud-storage package."
                )
                self._backend = MinIOBackend()
                logger.info("Using MinIO storage backend (fallback from GCS)")
        else:
            self._backend = MinIOBackend()
            logger.info("Using MinIO storage backend")

        # Expose default bucket for backward compatibility
        if hasattr(self._backend, 'default_bucket'):
            self.bucket = self._backend.default_bucket
        else:
            self.bucket = settings.MINIO_BUCKET

    def upload_file(
        self,
        file_data: bytes,
        filename: str,
        bucket_name: Optional[str] = None,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> str:
        """Upload a file to storage."""
        return self._backend.upload_file(file_data, filename, bucket_name, content_type, metadata)

    def download_file(self, object_name: str, bucket_name: Optional[str] = None) -> bytes:
        """Download a file from storage."""
        return self._backend.download_file(object_name, bucket_name)

    def get_file(self, minio_key: str = None, bucket_name: Optional[str] = None, storage_key: str = None) -> bytes:
        """Alias for download_file (backward compatibility)."""
        key = storage_key or minio_key
        return self.download_file(key, bucket_name)

    def delete_file(self, object_name: str, bucket_name: Optional[str] = None) -> bool:
        """Delete a file from storage."""
        return self._backend.delete_file(object_name, bucket_name)

    def file_exists(self, object_name: str, bucket_name: Optional[str] = None) -> bool:
        """Check if a file exists."""
        return self._backend.file_exists(object_name, bucket_name)

    def get_presigned_url(
        self,
        minio_key: str,
        bucket_name: Optional[str] = None,
        expiry=None
    ) -> str:
        """Generate a presigned/signed URL for file access."""
        return self._backend.get_presigned_url(minio_key, bucket_name, expiry)

    def get_file_url(self, object_name: str, expires_in: int = 3600) -> str:
        """Alias for get_presigned_url (backward compatibility)."""
        return self.get_presigned_url(object_name, expiry=expires_in)

    def list_files(self, prefix: str = "", bucket_name: Optional[str] = None) -> list[str]:
        """List files with optional prefix filter."""
        return self._backend.list_files(prefix, bucket_name)

    # Legacy methods for backward compatibility
    def download_file_stream(self, object_name: str) -> BinaryIO:
        """Download a file as a stream (MinIO only)."""
        if isinstance(self._backend, MinIOBackend):
            return self._backend.client.get_object(self._backend.default_bucket, object_name)
        else:
            # For GCS, return BytesIO wrapper
            data = self.download_file(object_name)
            return BytesIO(data)


# =============================================================================
# Singleton and Backward Compatibility
# =============================================================================

_instance: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get or create the StorageService singleton."""
    global _instance
    if _instance is None:
        _instance = StorageService()
    return _instance


# Backward compatibility aliases
MinIOService = StorageService
get_minio_service = get_storage_service
minio_service = None


def _get_minio_service():
    """Lazy initialization for module-level singleton."""
    global minio_service
    if minio_service is None:
        minio_service = get_storage_service()
    return minio_service
