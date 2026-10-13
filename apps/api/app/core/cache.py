"""In-memory cache with TTL support (M12 Performance).

Provides a lightweight cache for API responses and computed values.
Thread-safe with automatic TTL expiration.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry:
    """A single cache entry with value and expiration."""

    value: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)


class TTLCache:
    """Thread-safe TTL cache with LRU eviction."""

    def __init__(
        self,
        max_size: int = 10000,
        default_ttl: float = 300.0,
    ) -> None:
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "sets": 0}

    def _is_expired(self, entry: CacheEntry) -> bool:
        return time.time() > entry.expires_at

    def _evict_expired(self) -> int:
        """Remove expired entries. Returns count evicted."""
        now = time.time()
        evicted = 0
        keys_to_remove = [key for key, entry in self._cache.items() if now > entry.expires_at]
        for key in keys_to_remove:
            del self._cache[key]
            evicted += 1
        return evicted

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._cache:
            self._cache.popitem(last=False)
            self._stats["evictions"] += 1

    def get(self, key: str, default: T | None = None) -> T | None:
        """Get value by key, returning default if not found or expired."""
        with self._lock:
            self._evict_expired()

            entry = self._cache.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return default

            if self._is_expired(entry):
                del self._cache[key]
                self._stats["misses"] += 1
                return default

            # Update access stats
            entry.access_count += 1
            entry.last_accessed = time.time()

            # Move to end (most recently used)
            self._cache.move_to_end(key)

            self._stats["hits"] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set value with optional TTL (seconds)."""
        with self._lock:
            self._evict_expired()

            if len(self._cache) >= self.max_size and key not in self._cache:
                self._evict_lru()

            expires_at = time.time() + (ttl if ttl is not None else self.default_ttl)
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
            self._cache.move_to_end(key)
            self._stats["sets"] += 1

    def delete(self, key: str) -> bool:
        """Delete key from cache. Returns True if key existed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._cache.clear()

    @property
    def available(self) -> bool:
        """Whether this tier can serve. An in-process cache always can."""
        return True

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": round(hit_rate, 4),
                "evictions": self._stats["evictions"],
                "sets": self._stats["sets"],
            }

    def keys(self) -> list[str]:
        """Return all valid (non-expired) keys."""
        with self._lock:
            self._evict_expired()
            return list(self._cache.keys())


# Global cache instances
_response_cache = TTLCache(max_size=5000, default_ttl=60.0)  # 1 min for responses
_compute_cache = TTLCache(max_size=10000, default_ttl=300.0)  # 5 min for computations


def cached_response(
    ttl: float = 60.0,
    key_prefix: str = "resp",
    vary_on: list[str] | None = None,
) -> Callable:
    """Decorator for caching endpoint responses.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        vary_on: List of request attributes to include in cache key
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if hasattr(arg, "url") and hasattr(arg, "headers"):
                    request = arg
                    break
            if request is None:
                request = kwargs.get("request")

            # Build cache key
            key_parts = [key_prefix, func.__name__]
            if request:
                key_parts.append(request.url.path)
                if request.query_params:
                    key_parts.append(str(request.query_params))
                if vary_on:
                    for header in vary_on:
                        val = request.headers.get(header, "")
                        key_parts.append(f"{header}:{val}")

            cache_key = ":".join(key_parts)

            # Try cache
            cached = _response_cache.get(cache_key)
            if cached is not None:
                return cached

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result (only cache successful responses)
            if hasattr(result, "status_code") and 200 <= result.status_code < 300:
                _response_cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


def cached_computation(
    ttl: float = 300.0,
    key_prefix: str = "comp",
) -> Callable:
    """Decorator for caching expensive computations.

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Build cache key from function name and arguments
            key_parts = [key_prefix, func.__name__]
            for arg in args:
                key_parts.append(str(arg))
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}={v}")

            cache_key = ":".join(key_parts)

            # Try cache
            cached = _compute_cache.get(cache_key)
            if cached is not None:
                return cached

            # Execute function
            result = func(*args, **kwargs)

            # Cache result
            _compute_cache.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


def get_cache_stats() -> dict[str, dict[str, Any]]:
    """Get statistics for all caches."""
    return {
        "response_cache": _response_cache.get_stats(),
        "compute_cache": _compute_cache.get_stats(),
    }


def clear_caches() -> None:
    """Clear all caches."""
    _response_cache.clear()
    _compute_cache.clear()
