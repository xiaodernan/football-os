"""Redis cache tests (M12 Production - Redis cache layer)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_redis_cache_fallback_when_unavailable() -> None:
    """When Redis is unavailable, falls back to in-memory cache."""
    with patch("redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception("Connection refused")
        mock_from_url.return_value = mock_redis

        from app.core.redis_cache import RedisCache
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        assert cache._available is False

        # Should fall back to in-memory
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"
        assert cache._fallback.get("test_key") == "test_value"


def test_redis_cache_happy_path() -> None:
    """When Redis is available, reads/writes go through Redis."""
    with patch("redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = '"test_value"'
        mock_redis.setex.return_value = True
        mock_redis.delete.return_value = 1
        mock_redis.ping.return_value = True
        mock_from_url.return_value = mock_redis

        from app.core.redis_cache import RedisCache
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        assert cache._available is True

        cache.set("test_key", "test_value")
        mock_redis.setex.assert_called_once()

        value = cache.get("test_key")
        assert value == "test_value"


def test_redis_cache_fallback_on_redis_failure() -> None:
    """When Redis fails mid-operation, falls back to in-memory."""
    with patch("redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.get.side_effect = Exception("Connection lost")
        mock_from_url.return_value = mock_redis

        from app.core.redis_cache import RedisCache
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        assert cache._available is True

        # First call succeeds
        cache.set("test_key", "test_value")

        # Second call fails on Redis, falls back
        cache.set("test_key", "new_value")
        result = cache.get("test_key")
        assert result == "new_value"  # Falls back to in-memory


def test_redis_cache_graceful_degradation_on_set_failure() -> None:
    """When Redis set fails, still writes to fallback."""
    with patch("redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.setex.side_effect = Exception("Connection lost")
        mock_from_url.return_value = mock_redis

        from app.core.redis_cache import RedisCache
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        assert cache._available is True

        result = cache.set("test_key", "test_value")
        assert result is True  # Still returns True (wrote to fallback)
        assert cache._available is False  # Marked unavailable


def test_redis_cache_delete() -> None:
    """Delete works on both Redis and fallback."""
    with patch("redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.delete.return_value = 1
        mock_from_url.return_value = mock_redis

        from app.core.redis_cache import RedisCache
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache.set("test_key", "test_value")

        result = cache.delete("test_key")
        assert result is True


def test_redis_cache_clear() -> None:
    """Clear removes from both Redis and fallback."""
    with patch("redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.scan.return_value = (0, ["key1", "key2"])
        mock_redis.delete.return_value = 2
        mock_from_url.return_value = mock_redis

        from app.core.redis_cache import RedisCache
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache.set("test_key", "test_value")
        cache.clear()

        # Fallback should be cleared
        assert cache._fallback.get_stats()["size"] == 0


def test_redis_cache_get_stats() -> None:
    """Stats include both Redis and fallback info."""
    with patch("redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {"used_memory_human": "1.5M", "connected_clients": 5}
        mock_from_url.return_value = mock_redis

        from app.core.redis_cache import RedisCache
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        cache.set("test_key", "test_value")

        stats = cache.get_stats()
        assert stats["redis_available"] is True
        assert stats["fallback"]["size"] == 1
        assert stats["redis_memory_used"] == "1.5M"


def test_global_redis_cache_singleton() -> None:
    """get_redis_cache returns singleton."""
    with patch("redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_from_url.return_value = mock_redis

        from app.core.redis_cache import get_redis_cache, close_redis_cache
        cache1 = get_redis_cache()
        cache2 = get_redis_cache()
        assert cache1 is cache2

        close_redis_cache()


def test_redis_cache_close() -> None:
    """Close closes Redis connection."""
    with patch("redis.from_url") as mock_from_url:
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_from_url.return_value = mock_redis

        from app.core.redis_cache import RedisCache, close_redis_cache
        cache = RedisCache(redis_url="redis://localhost:6379/0")
        assert cache._available is True

        cache.close()
        assert cache._redis is None
        assert cache._available is False


def test_redis_cache_graceful_degradation_when_env_unset() -> None:
    """When REDIS_URL is not set, uses default and gracefully fails."""
    with patch.dict("os.environ", {}, clear=True):
        with patch("redis.from_url") as mock_from_url:
            mock_redis = MagicMock()
            mock_redis.ping.side_effect = Exception("Connection refused")
            mock_from_url.return_value = mock_redis

            from app.core.redis_cache import RedisCache
            cache = RedisCache()  # Uses default redis_url
            assert cache._available is False
            # Still works via fallback
            cache.set("test", "value")
            assert cache.get("test") == "value"


# Integration-style test that can run against a real Redis if available
@pytest.mark.integration
def test_redis_cache_real_integration() -> None:
    """Integration test against real Redis (requires running Redis)."""
    pytest.importorskip("redis")
    from app.core.redis_cache import RedisCache
    cache = RedisCache(redis_url="redis://localhost:6379/0")
    if not cache._available:
        pytest.skip("Redis not available")

    cache.set("integration_test", {"value": 123, "nested": {"a": 1}})
    assert cache.get("integration_test") == {"value": 123, "nested": {"a": 1}}
    cache.delete("integration_test")
    assert cache.get("integration_test") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])