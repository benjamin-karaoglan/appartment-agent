"""
Fault-tolerant Redis cache helpers.

Redis down = cache miss, never an error. All operations are wrapped
in try/except so callers never need to handle Redis failures.
"""

import logging
from typing import Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """Return a lazy singleton Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


def cache_get(key: str) -> Optional[str]:
    """Get a value from Redis. Returns None on miss or error."""
    try:
        return get_redis().get(key)
    except Exception:
        logger.warning("Redis cache_get failed for key=%s", key, exc_info=True)
        return None


def cache_set(key: str, value: str, ttl: int) -> None:
    """Set a value in Redis with a TTL (seconds). Silently ignores errors."""
    try:
        get_redis().set(key, value, ex=ttl)
    except Exception:
        logger.warning("Redis cache_set failed for key=%s", key, exc_info=True)
