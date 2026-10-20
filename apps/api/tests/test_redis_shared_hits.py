"""The shared tier's own hit rate: counted where it happens (M12 performance).

The M12 document said no figure measured what sharing buys, because the tier had never served a
request on the host the figures were taken on, and because nothing counted the shared tier's own
hits. The tier is live now (2026-10-20), and these counters are the second half.

Three claims:

* a read the shared tier answers is a hit, and a read it does not is a miss;
* the counters are this process's own, so a worker whose hit rate is above zero has served an
  answer another worker paid for — the thing the load numbers could not show;
* the numbers reach the metrics door, so an operator can read them without a debugger.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.redis_cache import RedisCache


def _serving_client(store: dict[str, str]) -> MagicMock:
    client = MagicMock()
    client.ping.return_value = True

    def _get(key: str) -> str | None:
        return store.get(key)

    def _set(key: str, value: str, ex: int | None = None) -> bool:
        store[key] = value
        return True

    client.get.side_effect = _get
    client.set.side_effect = _set
    return client


def test_a_read_the_shared_tier_answers_is_a_hit() -> None:
    store: dict[str, str] = {}
    with patch("redis.from_url") as mock_from_url:
        mock_from_url.return_value = _serving_client(store)
        cache = RedisCache(redis_url="redis://localhost:6379/0")

        cache.set("k", {"v": 1})
        assert cache.get("k") == {"v": 1}

        stats = cache.get_stats()
        assert stats["redis_hits"] == 1, f"a read the shared tier answered was not counted: {stats}"
        assert stats["redis_misses"] == 0
        assert stats["redis_hit_rate"] == 1.0


def test_a_read_the_shared_tier_does_not_answer_is_a_miss() -> None:
    store: dict[str, str] = {}
    with patch("redis.from_url") as mock_from_url:
        mock_from_url.return_value = _serving_client(store)
        cache = RedisCache(redis_url="redis://localhost:6379/0")

        assert cache.get("never-written") is None

        stats = cache.get_stats()
        assert stats["redis_misses"] == 1, f"a read the shared tier did not answer was not counted: {stats}"
        assert stats["redis_hits"] == 0
        assert stats["redis_hit_rate"] == 0.0


def test_the_counters_are_this_process_s_own() -> None:
    """Two workers, one store: the second worker's hit is an answer the first one paid for."""
    store: dict[str, str] = {}
    with patch("redis.from_url") as mock_from_url:
        mock_from_url.return_value = _serving_client(store)
        first = RedisCache(redis_url="redis://localhost:6379/0")
        second = RedisCache(redis_url="redis://localhost:6379/0")

        first.set("shared", {"paid": "by the first worker"})
        assert second.get("shared") == {"paid": "by the first worker"}

        assert first.get_stats()["redis_hits"] == 0, "the writer counted a hit it did not read"
        assert second.get_stats()["redis_hits"] == 1, "the reader did not count the answer it was given"


def test_a_degraded_tier_reports_no_hits_rather_than_none() -> None:
    """A tier that is not serving must not claim a hit rate it did not earn."""
    with patch("redis.from_url") as mock_from_url:
        mock_from_url.return_value = MagicMock(ping=MagicMock(side_effect=Exception("refused")))
        cache = RedisCache(redis_url="redis://localhost:6379/0")

        assert cache.available is False
        stats = cache.get_stats()
        assert stats["redis_available"] is False
        assert stats["redis_hits"] == 0
        assert stats["redis_hit_rate"] == 0.0
        assert stats["redis_url"] is None
