"""The boot lock: one replica per sync, one process per owner — no fleet-wide double sync.

`RedisCache.try_lock` / `unlock` split two worlds, and the tests rehearse both: the shared tier
(where `SET NX` keeps replicas honest) and the degraded in-process fallback (where a host that
boots twice gets the same shape of answer, with nothing to pretend a replica that isn't there
ever held anything). The unlock is compare-and-delete in both worlds, so a stale owner of a
TTL-healed key can never unlink the replacement's lock.
"""

from __future__ import annotations

from app.core.redis_cache import RedisCache


class StubRedis:
    """The three moves the lock makes against a real Redis: SET NX, EVAL compare-and-delete."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):  # noqa: ARG002
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def eval(self, script: str, numkeys: int, key: str, arg: str):  # noqa: ARG002
        if self.store.get(key) == arg:
            self.store.pop(key)
            return 1
        return 0


def _cache_with_redis() -> RedisCache:
    cache = RedisCache(redis_url="redis://127.0.0.1:9/0")  # unreachable port: fallback engaged
    cache._redis = StubRedis()  # type: ignore[assignment]
    cache._available = True
    return cache


class TestTheSharedTier:
    def test_only_one_replica_takes_the_lock(self) -> None:
        cache = _cache_with_redis()
        first = cache.try_lock("boot:world-sync", ttl_seconds=300)
        second = cache.try_lock("boot:world-sync", ttl_seconds=300)
        assert first is not None
        assert second is None, "the loser of a SET NX race must not proceed to the sync"

    def test_a_release_hands_the_lock_to_the_next_replica(self) -> None:
        cache = _cache_with_redis()
        token = cache.try_lock("boot:world-sync", 300)
        assert token is not None
        assert cache.unlock("boot:world-sync", token) is True
        assert cache.try_lock("boot:world-sync", 300) is not None

    def test_a_stale_owner_cannot_unlink_a_replacement(self) -> None:
        cache = _cache_with_redis()
        right = cache.try_lock("boot:world-sync", 300)
        # replacement syncs after the winner's TTL; the stale token must fail its unlock
        assert cache._redis is not None
        cache._redis.store["football_os:boot:world-sync"] = "not-the-stale-token"
        assert cache.unlock("boot:world-sync", right) is False
        assert cache._redis.store["football_os:boot:world-sync"] == "not-the-stale-token"


class TestTheDegradedTier:
    def test_one_process_one_owner_in_the_fallback(self) -> None:
        cache = RedisCache(redis_url="redis://127.0.0.1:9/0")  # nothing answers there
        first = cache.try_lock("boot:world-sync", 300)
        second = cache.try_lock("boot:world-sync", 300)
        assert first is not None
        assert second is None

    def test_the_fallback_hands_it_back_after_a_release(self) -> None:
        cache = RedisCache(redis_url="redis://127.0.0.1:9/0")
        token = cache.try_lock("boot:world-sync", 300)
        assert token is not None
        assert cache.unlock("boot:world-sync", token) is True
        assert cache.try_lock("boot:world-sync", 300) is not None
