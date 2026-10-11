"""Redis-backed cache with TTL and graceful degradation (M12 Production).

Provides a Redis-backed cache that can be used alongside the in-memory TTLCache.
Gracefully degrades to in-memory only when Redis is unavailable.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import redis

from app.core.cache import TTLCache
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis-backed cache with TTL and graceful degradation.

    When Redis is available, reads/writes go through Redis.
    When Redis is unavailable, falls back to in-memory TTLCache.
    """

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: float = 300.0,
        redis_url: str | None = None,
    ) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis: redis.Redis | None = None
        self._fallback = TTLCache(max_size=max_size, default_ttl=default_ttl)
        self._available = False
        self._connect()

    def _connect(self) -> None:
        """Attempt to connect to Redis."""
        try:
            self._redis = redis.from_url(
                self.redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            # Test connection
            self._redis.ping()
            self._available = True
            logger.info("Redis cache connected: %s", self.redis_url)
        except Exception as e:
            self._available = False
            self._redis = None
            logger.warning("Redis unavailable, using in-memory fallback: %s", e)

    def _key(self, key: str) -> str:
        """Prefix keys to avoid collisions."""
        return f"football_os:{key}"

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key."""
        redis_key = self._key(key)

        if self._available and self._redis:
            try:
                value = self._redis.get(self._key(key))
                if value is not None:
                    return json.loads(value)
            except Exception as e:
                logger.warning("Redis get failed, falling back: %s", e)
                self._available = False

        # Fallback to in-memory
        return self._fallback.get(key, default)

    def set(self, key: str, value: Any, ttl: float | None = None) -> bool:
        """Set value with optional TTL."""
        redis_key = self._key(key)
        ttl_seconds = int(ttl if ttl is not None else self.default_ttl)

        # Always write to fallback
        self._fallback.set(key, value, ttl)

        if self._available and self._redis:
            try:
                self._redis.setex(
                    self._key(key),
                    int(ttl_seconds),
                    json.dumps(value, separators=(",", ":")),
                )
                return True
            except Exception as e:
                logger.warning("Redis set failed: %s", e)
                self._available = False
                return True  # Still wrote to fallback

        return True

    def delete(self, key: str) -> bool:
        """Delete key from both Redis and fallback."""
        deleted = self._fallback.delete(key)

        if self._available and self._redis:
            try:
                result = self._redis.delete(self._key(key))
                return result > 0 or deleted
            except Exception as e:
                logger.warning("Redis delete failed: %s", e)
                self._available = False

        return deleted

    def clear(self) -> None:
        """Clear all entries."""
        self._fallback.clear()
        if self._available and self._redis:
            try:
                # Use SCAN to delete keys with our prefix
                pattern = self._key("*")
                cursor = 0
                while True:
                    cursor, keys = self._redis.scan(cursor, match=pattern, count=1000)
                    if keys:
                        self._redis.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning("Redis clear failed: %s", e)
                self._available = False

    def get_stats(self) -> dict[str, Any]:
        """Get combined stats from Redis and fallback."""
        fallback_stats = self._fallback.get_stats()
        stats = {
            "fallback": fallback_stats,
            "redis_available": self._available,
            "redis_url": self.redis_url if self._available else None,
        }
        if self._available and self._redis:
            try:
                info = self._redis.info("memory")
                stats["redis_memory_used"] = info.get("used_memory_human")
                stats["redis_connected_clients"] = info.get("connected_clients")
            except Exception:
                pass
        return stats

    def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            try:
                self._redis.close()
            except Exception:
                pass
            self._redis = None
            self._available = False


# Global Redis cache instance (lazy initialization)
_redis_cache: "RedisCache | None" = None


def get_redis_cache() -> RedisCache:
    """Get or create the global Redis cache instance."""
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
    return _redis_cache


def close_redis_cache() -> None:
    """Close the global Redis cache."""
    global _redis_cache
    if _redis_cache:
        _redis_cache.close()
        _redis_cache = None