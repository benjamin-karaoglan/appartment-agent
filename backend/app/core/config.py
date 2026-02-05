"""
Application configuration using Pydantic settings.
"""

import os
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Application
    PROJECT_NAME: str = "AppArt Agent"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # API
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS - Updated for GCP deployment
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        # Cloud Run URLs (pattern: https://*.run.app)
        # Add specific domains here or use wildcard matching in middleware
    ]

    # Additional CORS origins from environment (comma-separated)
    EXTRA_CORS_ORIGINS: str = os.getenv("EXTRA_CORS_ORIGINS", "")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://appart:appart@localhost:5432/appart_agent"
    )

    # Google Cloud / Gemini (Primary LLM Provider)
    GOOGLE_CLOUD_API_KEY: str = os.getenv("GOOGLE_CLOUD_API_KEY", "")
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    GEMINI_USE_VERTEXAI: bool = os.getenv("GEMINI_USE_VERTEXAI", "false").lower() == "true"

    # Gemini Models
    GEMINI_LLM_MODEL: str = os.getenv("GEMINI_LLM_MODEL", "gemini-2.0-flash-lite")  # Default for text/document analysis
    GEMINI_IMAGE_MODEL: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")  # For image generation

    # Anthropic (DEPRECATED - kept for backward compatibility)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"  # Deprecated

    # File uploads - Use environment variable or /tmp for Cloud Run
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/tmp/uploads")
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = [
        ".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".xls", ".xlsx"
    ]

    # DVF Data - Use environment variable or /tmp for Cloud Run
    DVF_DATA_DIR: str = os.getenv("DVF_DATA_DIR", "/tmp/data/dvf")

    # Logfire observability (optional - set LOGFIRE_TOKEN to enable)
    LOGFIRE_TOKEN: str = os.getenv("LOGFIRE_TOKEN", "")
    LOGFIRE_ENABLED: bool = os.getenv("LOGFIRE_ENABLED", "false").lower() == "true"

    # Redis Cache
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    CACHE_TTL: int = 3600  # 1 hour cache TTL

    # Storage Backend Configuration
    # Options: 'minio' (default for local), 'gcs' (for GCP production)
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "minio")

    # MinIO Object Storage (for local development)
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "minio:9000")
    MINIO_PUBLIC_ENDPOINT: str = os.getenv("MINIO_PUBLIC_ENDPOINT", "")
    MINIO_REGION: str = os.getenv("MINIO_REGION", "us-east-1")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "documents")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"

    # Google Cloud Storage (for GCP production)
    GCS_DOCUMENTS_BUCKET: str = os.getenv("GCS_DOCUMENTS_BUCKET", "")
    GCS_PHOTOS_BUCKET: str = os.getenv("GCS_PHOTOS_BUCKET", "")

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
