"""High-concurrency guard for the in-memory token bucket — the degraded tier must stay atomic.

When the shared Redis tier is absent, every worker falls back to MemoryLimiter. Under a credential-
stuffing burst, dozens of threads hit the same key at once; the bucket must spend exactly one token
per admitted request and never let the burst exceed capacity, or the fallback becomes a hole.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.core.ratelimit import MemoryLimiter, Policy

BURST = 20
CALLERS = 200
policy = Policy(name="login-burst", capacity=BURST, refill_per_second=0.001)


def test_a_threaded_burst_admits_exactly_capacity():
    limiter = MemoryLimiter()
    key = "ip:203.0.113.9"
    with ThreadPoolExecutor(max_workers=32) as pool:
        verdicts = list(pool.map(lambda _: limiter.admit(key, policy), range(CALLERS)))
    assert sum(verdicts) == BURST, "the lock must serialise the spend so only capacity tokens go out"
    assert limiter.allowed == 0, "admit is a routing pre-filter and keeps no counters"


def test_decide_under_threads_never_exceeds_the_ceiling():
    limiter = MemoryLimiter()
    key = "ip:203.0.113.10"
    with ThreadPoolExecutor(max_workers=32) as pool:
        decisions = list(pool.map(lambda _: limiter.decide(key, policy), range(CALLERS)))
    admitted = sum(1 for d in decisions if d.allowed)
    assert admitted == BURST
    assert limiter.allowed == BURST
    assert limiter.refused == CALLERS - BURST
    # every admitted decision reports the same published ceiling; remaining never goes negative
    assert all(d.limit == BURST for d in decisions)
    assert all(d.remaining >= 0 for d in decisions)


def test_the_fallback_is_visible_in_every_decision():
    limiter = MemoryLimiter()
    d = limiter.decide("ip:203.0.113.11", policy)
    assert d.source == "process", "a degraded tier must announce itself, never pose as the cluster"
    assert d.scope == "process"
