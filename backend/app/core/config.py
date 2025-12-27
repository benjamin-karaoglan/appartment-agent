"""
Application configuration using Pydantic settings.
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings."""

    # Application
    PROJECT_NAME: str = "Appartment Agent"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # API
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://appartment:appartment@localhost:5432/appartment_agent"
    )

    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"

    # File uploads
    UPLOAD_DIR: str = os.path.join(os.path.dirname(__file__), "../../../uploads")
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = [
        ".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx", ".xls", ".xlsx"
    ]

    # DVF Data
    DVF_DATA_DIR: str = os.path.join(os.path.dirname(__file__), "../../../data/dvf")

    # Redis Cache
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    CACHE_TTL: int = 3600  # 1 hour cache TTL

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
