"""Redis-backed cache with TTL and graceful degradation (M12 Production).

Provides a Redis-backed cache that can be used alongside the in-memory TTLCache.
Gracefully degrades to in-memory only when Redis is unavailable.

The `cast`s are types, not behaviour: redis-py's stubs type every command's return as
`Awaitable[Any] | Any` because one client class serves both the sync and the async API,
and this build only ever drives the sync half — so each result is asserted to the type
the sync call actually returns. A guard that merely narrowed `self._redis` would not
survive mypy: a method call may mutate an attribute, so every guarded block binds the
client to a local first.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

import redis

from app.core.cache import TTLCache

logger = logging.getLogger(__name__)


def redact_url(url: str) -> str:
    """The URL with its password removed, for anything that leaves this process.

    A Redis URL is where the password lives — `redis://:secret@host:6379/0` — so every place the
    URL is printed has to drop the userinfo or the password is in the log line, in the metrics
    door, and in whatever reads them. The host, the port and the database number stay, because
    those are what make the line useful: an operator needs to know *which* instance is serving,
    not the credential for it.

    The redaction is on the parsed URL rather than on a string, so a password that contains the
    `@` or `/` that a naive split would trip over is still removed.
    """
    parts = urlsplit(url)
    if not parts.password:
        return url
    host = parts.hostname or ""
    if parts.port is not None:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


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
        # Annotated, not inferred: `redis_url` arrives as `str | None`, and typeshed
        # declares `os.getenv` as `str | None` even when a default is passed — so the
        # literal has to sit outside the call for the expression to narrow to `str`,
        # which is what `from_url` demands two lines down.
        self.redis_url: str = redis_url or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
        self._redis: redis.Redis | None = None
        self._fallback = TTLCache(max_size=max_size, default_ttl=default_ttl)
        self._available = False
        #: This process's own count of the shared tier's reads: a read Redis answered and a read
        #: it did not. The server's own counters are not used - they count every client of the
        #: instance, so they could not be attributed to this application.
        self._shared_hits = 0
        self._shared_misses = 0
        self._connect()

    def _connect(self) -> None:
        """Attempt to connect to Redis."""
        try:
            client: redis.Redis | None = redis.from_url(
                self.redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            # typeshed allows from_url to yield no client; a configured-but-absent
            # client is the same degraded state as a refused handshake.
            if client is None:
                raise ConnectionError("redis.from_url returned no client")
            client.ping()
            self._redis = client
            self._available = True
            logger.info("Redis cache connected: %s", self.redacted_url())
        except Exception as e:
            self._available = False
            self._redis = None
            logger.warning("Redis unavailable, using in-memory fallback: %s", e)

    def _key(self, key: str) -> str:
        """Prefix keys to avoid collisions."""
        return f"football_os:{key}"

    def redacted_url(self) -> str:
        """This tier's URL with the password removed — the only form allowed to leave the process."""
        return redact_url(self.redis_url)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value by key."""
        client = self._redis
        if self._available and client is not None:
            try:
                value = cast("Any", client.get(self._key(key)))
                if value is not None:
                    self._shared_hits += 1
                    return json.loads(value)
                self._shared_misses += 1
            except Exception as e:
                logger.warning("Redis get failed, falling back: %s", e)
                self._available = False

        # Fallback to in-memory
        return self._fallback.get(key, default)

    def set(self, key: str, value: Any, ttl: float | None = None) -> bool:
        """Set value with optional TTL."""
        ttl_seconds = int(ttl if ttl is not None else self.default_ttl)

        # Always write to fallback
        self._fallback.set(key, value, ttl)

        client = self._redis
        if self._available and client is not None:
            try:
                #: `setex` is deprecated in the pinned redis-py (8.1.0 says "use `set` instead"), and
                #: `set` with `ex=` is the same write with the expiry in the same command.
                client.set(
                    self._key(key),
                    json.dumps(value, separators=(",", ":")),
                    ex=int(ttl_seconds),
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

        client = self._redis
        if self._available and client is not None:
            try:
                result = client.delete(self._key(key))
                return result > 0 or deleted
            except Exception as e:
                logger.warning("Redis delete failed: %s", e)
                self._available = False

        return deleted

    def clear(self) -> None:
        """Clear all entries."""
        self._fallback.clear()
        client = self._redis
        if self._available and client is not None:
            try:
                # Use SCAN to delete keys with our prefix
                pattern = self._key("*")
                cursor = 0
                while True:
                    cursor, keys = cast("tuple[int, list[str]]", client.scan(cursor, match=pattern, count=1000))
                    if keys:
                        client.delete(*keys)
                    if cursor == 0:
                        break
            except Exception as e:
                logger.warning("Redis clear failed: %s", e)
                self._available = False

    def drop_identity(self, identity: str) -> int:
        """Delete this caller's entries from the process-local fallback.

        The shared store never holds a private answer (a credentialed response is never
        written to it, per RFC 9111 §3.5), so a caller's own cached answers live only in
        a near tier — this process's `_response_cache`, or this class's fallback when it
        is standing in for one. Dropping therefore touches the fallback and not Redis;
        sweeping the shared store would delete other callers' public answers for no
        correctness gain.
        """
        return self._fallback.drop_identity(identity)

    @property
    def available(self) -> bool:
        """Whether Redis is actually serving, as opposed to configured.

        Distinct from `redis_url` being set: on a host whose instance rejects the
        handshake this is False while the configuration still looks right. A caller
        deciding whether to *write* to the shared tier needs this, because writing
        into this class's internal fallback while Redis is down would populate a
        second process-local cache and quietly defeat the point of a shared one.
        """
        return self._available

    def get_stats(self) -> dict[str, Any]:
        """Get combined stats from Redis and fallback."""
        fallback_stats = self._fallback.get_stats()
        shared_total = self._shared_hits + self._shared_misses
        stats = {
            "fallback": fallback_stats,
            "redis_available": self._available,
            #: The URL without its password. The metrics door publishes this to any signed-in
            #: caller, and a URL that carries a credential is a credential in a metrics door.
            "redis_url": self.redacted_url() if self._available else None,
            #: How often the shared tier answered, counted by this process. With several workers
            #: the app-wide figure is the sum of theirs, and a worker with hits above zero has
            #: served an answer another worker paid for.
            "redis_hits": self._shared_hits,
            "redis_misses": self._shared_misses,
            "redis_hit_rate": round(self._shared_hits / shared_total, 4) if shared_total else 0.0,
        }
        client = self._redis
        if self._available and client is not None:
            try:
                info = client.info("memory")
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
_redis_cache: RedisCache | None = None


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
