"""One hot miss is the only expensive miss this platform keeps.

The second reader asking the knowledge service the same new question is already free —
`services/knowledge/answer_cache.py` coalesces those and the scrape door counts them. The
same storm exists on the public read doors: K callers land on `/world/search` in the same
second *before* the 60-second response cache has an answer, and K identical `LIKE '%'`
scans hit SQLite. This module is the in-process half of closing that, mirroring the lane
table the answer cache proved — one owner per key, waiters wake together, nobody waits on
somebody else's lane.

Semantics, deliberately no more:

* **leader** executes `fn` **outside any lock**; followers wait on the lane's event and take a
  reference to the leader's value when it publishes. Nothing is copied, nothing is marshalled —
  the object returned by `fn` is the object every caller in the window holds.
* a leader's **exception** is re-raised in every follower that was waiting. The alternative —
  followers quietly repeating the failure as a fresh call — would triple a broken provider
  under a burst instead of quarantining it.
* the lane **never blocks construction of a new lane**: follower arrival is a dict lookup and
  a counter bump; the lock is held for nanoseconds, never for `fn`'s duration.
* `joins` is the number of calls this module turned into waits. It is the only number worth
  printing: a lane with zero joins is a cache the world never asked twice.
* **Scope.** In-process. A multi-worker deployment coalesces per worker; the shared half is
  the 60-second response cache, which this sits in front of for the miss window only. The
  correctness property does not depend on the tier: a follower never sees a partial answer,
  and a follower that arrives after the leader published its value waits for it instead of
  duplicating the work.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class _Lane:
    __slots__ = ("done", "value", "error")

    def __init__(self) -> None:
        self.done = threading.Event()
        self.value: Any = None
        self.error: BaseException | None = None


class Singleflight:
    """Per-key coalescing for synchronous work, safe under threads and asyncio's executor."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._lanes: dict[str, _Lane] = {}
        self._guard = threading.Lock()
        self.leaders = 0
        self.joins = 0

    def call(self, key: str, fn: Callable[[], Any]) -> Any:
        with self._guard:
            lane = self._lanes.get(key)
            if lane is None:
                lane = _Lane()
                self._lanes[key] = lane
                leader = True
            else:
                leader = False
        if leader:
            return self._lead(key, lane, fn)
        self.joins += 1
        lane.done.wait()
        if lane.error is not None:
            raise lane.error
        return lane.value

    def _lead(self, key: str, lane: _Lane, fn: Callable[[], Any]) -> Any:
        self.leaders += 1
        try:
            lane.value = fn()
        except BaseException as exc:
            lane.error = exc
        finally:
            lane.done.set()
            with self._guard:
                self._lanes.pop(key, None)
        if lane.error is not None:
            raise lane.error
        return lane.value

    def inflight_size(self) -> int:
        """How many lanes are open. Bounded by concurrency, not by history."""
        with self._guard:
            return len(self._lanes)

    def stats(self) -> dict[str, int]:
        with self._guard:
            return {"leaders": self.leaders, "joins": self.joins}

    def reset_stats(self) -> None:
        with self._guard:
            self.leaders = 0
            self.joins = 0


world_search_flight = Singleflight("world-search")

__all__ = ["Singleflight", "world_search_flight"]
