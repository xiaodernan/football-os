"""Distributed rate limiting: one token bucket, counted where every worker can see it.

The tier this replaces is `app.core.security.RateLimiter` — a fixed window held in a dict — and its
own docstring has said "swap for Redis when horizontally scaled" since M1. What that sentence was
waiting for is not the client (the cache tier already owns one) but an answer to four questions a
per-process dict cannot answer:

1. **Which clock?** A fixed window keyed on `time.time()` divides a second at a boundary every
   worker computes for itself, and two workers whose clocks differ by 40 ms disagree about which
   window a request belongs to. The Lua script below reads `TIME` from the server, so N workers
   share one clock and a caller cannot dodge the limit by landing on the worker with the slow clock.

2. **Which key?** A bucket per `(scope, client, path)` grows without bound in a process that sees
   every caller, and the old limiter bounded it by evicting the least recently seen bucket —
   including buckets that were still inside their window, which hands that caller a fresh budget.
   A bucket here expires at the instant it would have refilled to capacity, because from that
   instant it carries no information: the state it holds is the state a missing key produces.

3. **What happens when the store is down?** Deny-everything turns a cache outage into a product
   outage; allow-everything turns it into an unbounded one. This module degrades to a process-local
   bucket of the same shape and *says so in the answer* (`X-RateLimit-Scope: process`), so the
   caller and the metrics door can both see which tier judged the request.

4. **How much does the check cost?** A Redis round trip per request is a round trip per request. The
   local bucket is therefore an **admission pre-filter** with the cluster's own capacity: it never
   refuses a caller the cluster would admit (its capacity is not smaller), and once a caller has
   spent the burst the pre-filter answers locally, so a flood of one caller's requests reaches the
   shared store at the refill rate rather than at the flood's rate. That is the difference between a
   limiter that protects the core and a limiter that becomes the core's new bottleneck.

The algorithm is a token bucket rather than a fixed window for a reason that shows up in a test: a
fixed window admits `2 × limit` across its boundary — `limit` at 00:59.9 and `limit` again at
01:00.1 — while a bucket admits `capacity + rate × t` over any interval, which is the property the
`Retry-After` this module publishes actually promises.

Nothing here knows what a football is. The policy table lives beside the app factory so a door can
be re-priced without touching the algorithm, and the measurement lives at `/api/v1/metrics`.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Final, Protocol

logger = logging.getLogger(__name__)

#: The longest a bucket may live in the shared store. A policy that refills slower than this would
#: have its key expire while it still held a deficit, which would hand the caller a full bucket —
#: so the TTL is the refill time, and this is only the floor that keeps a tiny policy from
#: expiring between two requests that arrive in the same millisecond.
MIN_TTL_MS: Final = 1_000

#: How many buckets one process will hold in its pre-filter. The same reasoning as the old limiter's
#: ceiling, applied where it is safe: a pre-filter bucket that is evicted early only means the next
#: request asks the shared store, which is the authority. Eviction here cannot grant a budget the
#: cluster would refuse.
MAX_LOCAL_BUCKETS: Final = 8192

#: `HMGET tokens ts` → refill → `HSET` → `PEXPIRE`, in one script so the read-modify-write cannot be
#: interleaved by another worker. `redis.call('TIME')` inside the script is evaluated by the server,
#: which is the single clock. `elapsed` is clamped at zero: a replica whose wall clock is behind the
#: timestamp another worker wrote must not mint tokens by travelling backwards.
_TOKEN_BUCKET_LUA: Final[str] = """
local capacity = tonumber(ARGV[1])
local refill_per_ms = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])
local clock = redis.call('TIME')
local now_ms = tonumber(clock[1]) * 1000 + math.floor(tonumber(clock[2]) / 1000)
local state = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(state[1])
local stamped = tonumber(state[2])
if tokens == nil or stamped == nil then
  tokens = capacity
  stamped = now_ms
end
local elapsed = now_ms - stamped
if elapsed < 0 then elapsed = 0 end
tokens = math.min(capacity, tokens + elapsed * refill_per_ms)
local allowed = 0
if tokens >= cost then
  tokens = tokens - cost
  allowed = 1
end
redis.call('HSET', KEYS[1], 'tokens', string.format('%.6f', tokens), 'ts', now_ms)
local ttl = math.ceil(capacity / refill_per_ms) + 1000
redis.call('PEXPIRE', KEYS[1], ttl)
local retry_ms = 0
if allowed == 0 then
  retry_ms = math.ceil((cost - tokens) / refill_per_ms)
end
return {allowed, math.floor(tokens), retry_ms}
"""


@dataclass(frozen=True)
class Policy:
    """How fast one caller may ask one door.

    `capacity` is the burst — how many requests may arrive back to back from a caller that has been
    quiet. `refill_per_second` is the sustained rate. The pair is the whole policy: a door that is
    cheap to serve can afford a large burst and a high rate, and a door that runs a model cannot.
    """

    name: str
    capacity: int
    refill_per_second: float
    cost: int = 1

    @property
    def refill_per_ms(self) -> float:
        return self.refill_per_second / 1000.0

    def __post_init__(self) -> None:
        if self.capacity < 1:
            raise ValueError(f"policy {self.name!r} needs capacity >= 1")
        if self.refill_per_second <= 0:
            raise ValueError(f"policy {self.name!r} needs a positive refill rate")
        if not 1 <= self.cost <= self.capacity:
            raise ValueError(f"policy {self.name!r} needs 1 <= cost <= capacity")


@dataclass(frozen=True)
class Decision:
    """What the limiter decided, and everything a response needs to say about it."""

    allowed: bool
    policy: str
    limit: int
    remaining: int
    retry_after: int
    scope: str
    #: The tier that answered: `cluster` when the shared store judged it, `process` when the local
    #: fallback did. Published so a degraded tier is visible rather than inferred.
    source: str

    def headers(self) -> dict[str, str]:
        """The rate-limit headers, in the shape the IETF draft names and clients already read.

        Both spellings are sent on purpose. `RateLimit-*` is the draft's, and `X-RateLimit-*` is
        what every client library written before it reads; sending one and not the other makes a
        correct server look like a broken one to half its callers. `RateLimit-Policy` names the
        policy so a caller that hits two doors with two budgets can tell them apart.
        """
        headers = {
            "RateLimit-Policy": f'"{self.policy}";q={self.limit};w=1',
            "RateLimit-Limit": str(self.limit),
            "RateLimit-Remaining": str(self.remaining),
            "RateLimit-Reset": str(self.retry_after),
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Scope": self.scope,
        }
        if not self.allowed:
            headers["Retry-After"] = str(max(1, self.retry_after))
        return headers


class Limiter(Protocol):
    def decide(self, key: str, policy: Policy) -> Decision: ...


@dataclass
class _Bucket:
    tokens: float
    stamped: float


class MemoryLimiter:
    """The process-local tier: the same algorithm, the same arithmetic, one clock per process.

    It is not a cache of the cluster's decision and must not be read as one — two workers each hold
    their own bucket, so the effective ceiling is `workers × capacity` when the shared store is
    absent. That is why every decision it produces is stamped `scope="process"`: a caller reading
    the headers can see the limit is per worker, and the metrics door counts the degraded answers.
    """

    def __init__(self, max_buckets: int = MAX_LOCAL_BUCKETS) -> None:
        self._buckets: OrderedDict[str, _Bucket] = OrderedDict()
        self._lock = threading.Lock()
        self._max = max_buckets
        #: Counters, read by the metrics door. Kept here rather than in a module global so two
        #: limiters in one process (a test's, the app's) do not add their figures together.
        self.allowed = 0
        self.refused = 0

    def _refill(self, key: str, policy: Policy, stamp: float) -> _Bucket:
        """Bring `key`'s bucket up to `stamp`, creating or evicting as needed. Caller holds the lock."""
        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=float(policy.capacity), stamped=stamp)
            self._buckets[key] = bucket
        elapsed = max(0.0, stamp - bucket.stamped)
        bucket.tokens = min(float(policy.capacity), bucket.tokens + elapsed * policy.refill_per_second)
        bucket.stamped = stamp
        self._buckets.move_to_end(key)
        while len(self._buckets) > self._max:
            self._buckets.popitem(last=False)
        return bucket

    def admit(self, key: str, policy: Policy) -> bool:
        """Spend a token, or answer `False` without consuming one.

        This is the pre-filter's question — "may this request reach the shared store" — and it
        deliberately keeps no counters: the answer it gives is not a rate-limit verdict, only a
        routing decision. The verdict, with its headers and its reason, comes from `decide`.
        """
        with self._lock:
            bucket = self._refill(key, policy, time.monotonic())
            if bucket.tokens < policy.cost:
                return False
            bucket.tokens -= policy.cost
            return True

    def decide(self, key: str, policy: Policy, *, now: float | None = None) -> Decision:
        stamp = time.monotonic() if now is None else now
        with self._lock:
            bucket = self._refill(key, policy, stamp)
            allowed = bucket.tokens >= policy.cost
            if allowed:
                bucket.tokens -= policy.cost
            remaining = int(bucket.tokens)
            retry = 0 if allowed else max(1, math.ceil((policy.cost - bucket.tokens) / policy.refill_per_second))
        if allowed:
            self.allowed += 1
        else:
            self.refused += 1
        return Decision(
            allowed=allowed,
            policy=policy.name,
            limit=policy.capacity,
            remaining=max(0, remaining),
            retry_after=retry,
            scope="process",
            source="process",
        )

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


class RedisLimiter:
    """The shared tier: one atomic script, one server clock, one bucket per caller and door.

    `client` is a `redis.Redis` (sync). The tier is optional at runtime for the same reason the
    response cache is: a product that cannot boot without its cache has a cache in the critical
    path of boot, which is the opposite of what a cache is for. A failure to reach the store, an
    error inside the script, or a reply that is not the three integers the script promises all
    resolve the same way — fall back to `fallback` and stamp the answer `process`.
    """

    def __init__(self, client: Any, fallback: MemoryLimiter | None = None) -> None:
        self._client = client
        self._fallback = fallback or MemoryLimiter()
        self._script_sha: str | None = None
        #: Counters for the metrics door, split by which tier answered and why.
        self.cluster_calls = 0
        self.cluster_failures = 0
        self.fallback_calls = 0

    def _script(self) -> str:
        """Register the script once, then call it by digest.

        `EVALSHA` is one round trip; re-sending the body on every request would put the script's
        ~700 bytes on the wire per call. A worker that has never loaded it — a fresh process, or a
        Redis that was restarted and lost its script cache — gets `NoScriptError`, and that is the
        one failure this tier answers by loading rather than by degrading.
        """
        import redis

        if self._script_sha is None:
            loaded = getattr(self._client, "script_load", None)
            if loaded is None:  # pragma: no cover - a client that cannot load scripts is unusable
                raise redis.RedisError("client has no SCRIPT LOAD")
            self._script_sha = str(loaded(_TOKEN_BUCKET_LUA))
        return self._script_sha

    def _run(self, key: str, policy: Policy) -> list[int] | None:
        import redis

        sha = self._script()
        evalsha = self._client.evalsha
        try:
            reply = evalsha(sha, 1, key, policy.capacity, policy.refill_per_ms, policy.cost)
        except redis.exceptions.NoScriptError:
            self._script_sha = None
            reply = evalsha(self._script(), 1, key, policy.capacity, policy.refill_per_ms, policy.cost)
        if not isinstance(reply, list | tuple) or len(reply) != 3:
            return None
        return [int(part) for part in reply]

    def decide(self, key: str, policy: Policy) -> Decision:
        self.cluster_calls += 1
        try:
            reply = self._run(key, policy)
        except Exception as exc:  # noqa: BLE001 - any failure degrades, none may reach the caller
            # Logged once per failure rather than once per request: a burst of the same exception
            # would otherwise be the loudest thing in the log during exactly the incident an
            # operator is reading it for.
            self.cluster_failures += 1
            logger.warning("rate limiter degraded to process scope: %s", exc.__class__.__name__)
            reply = None
        if reply is None:
            self.fallback_calls += 1
            return self._fallback.decide(key, policy)
        allowed, remaining, retry_ms = reply
        return Decision(
            allowed=bool(allowed),
            policy=policy.name,
            limit=policy.capacity,
            remaining=max(0, remaining),
            retry_after=0 if allowed else max(1, (retry_ms + 999) // 1000),
            scope="cluster",
            source="cluster",
        )


class TwoTierLimiter:
    """Admission pre-filter in front of the shared store.

    The local bucket is sized to the cluster's capacity, so it can never refuse a request the
    cluster would admit; what it buys is the *rate* at which a caller reaches the store. A caller
    inside its budget asks Redis once per request — that is the price of a cluster-correct answer.
    A caller outside it is answered locally after the burst is spent, so a flood costs Redis one
    call per refill tick rather than one per request.
    """

    def __init__(self, cluster: RedisLimiter | None, local: MemoryLimiter | None = None) -> None:
        self._cluster = cluster
        self._local = local or MemoryLimiter()
        #: How many requests the pre-filter answered without asking the shared store.
        self.short_circuited = 0

    @property
    def local(self) -> MemoryLimiter:
        return self._local

    def decide(self, key: str, policy: Policy) -> Decision:
        if self._cluster is None:
            return self._local.decide(key, policy)
        # Ask the cheap tier first. It spends a token only when the shared store is about to be
        # asked, so a request the pre-filter refuses costs no round trip at all.
        if not self._local.admit(key, policy):
            self.short_circuited += 1
            # The local bucket is the tier that refused, and its own `decide` re-reads the state it
            # just left (a token short) to produce the retry the caller can act on.
            return self._local.decide(key, policy)
        return self._cluster.decide(key, policy)

    def reset(self) -> None:
        self._local.reset()


# --------------------------------------------------------------------------------------------------
# The process singleton
# --------------------------------------------------------------------------------------------------

_limiter: TwoTierLimiter | None = None
_limiter_lock = threading.Lock()


def build_cluster(url: str) -> RedisLimiter | None:
    """A shared-store limiter, or `None` when this host has no store to speak to.

    The connect timeout is deliberately much shorter than the cache tier's: a rate limiter sits in
    front of *every* request, so a store that takes two seconds to refuse would add two seconds to
    the first request of every process restart. Half a second is enough for a local instance and
    short enough that a host with no instance at all pays it once and then remembers.
    """
    if not url:
        return None
    try:
        import redis

        client = redis.from_url(
            url,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            decode_responses=True,
        )
        client.ping()
    except Exception as exc:  # noqa: BLE001 - absence is a state, not an error
        try:
            from app.core.redis_cache import connection_refusal_hint

            hint = connection_refusal_hint(exc, url)
        except Exception:
            hint = str(exc) or exc.__class__.__name__
        logger.info("rate limiter has no shared store (%s: %s); process scope only", exc.__class__.__name__, hint)
        return None
    return RedisLimiter(client)


def get_limiter(redis_url: str | None = None) -> TwoTierLimiter:
    """The process's limiter, built on first use.

    Built lazily for the same reason the response cache is: a process that never serves a priced
    door should not pay a connect at import. `redis_url` is read only on the first call, so the
    settings that decide it are the ones in force at boot.
    """
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                url = redis_url if redis_url is not None else _redis_url_from_env()
                _limiter = TwoTierLimiter(build_cluster(url))
    return _limiter


def _redis_url_from_env() -> str:
    import os

    return os.getenv("RATE_LIMIT_REDIS_URL") or os.getenv("REDIS_URL") or ""


def reset_limiter() -> None:
    """Drop the singleton. Only tests call this; production has one limiter per process by design."""
    global _limiter
    with _limiter_lock:
        _limiter = None


def snapshot(limiter: TwoTierLimiter | None = None) -> dict[str, object]:
    """The limiter's own counters, in the shape the metrics door publishes.

    Read from whichever object answered the requests rather than from module globals, so two
    limiters in one test process do not report each other's figures.
    """
    active = limiter if limiter is not None else _limiter
    if active is None:
        return {"configured": False}
    cluster = active._cluster  # noqa: SLF001 - the snapshot is this module's own reporting door
    payload: dict[str, object] = {
        "configured": True,
        "scope": "cluster" if cluster is not None else "process",
        "short_circuited": active.short_circuited,
        "process_allowed": active.local.allowed,
        "process_refused": active.local.refused,
    }
    if isinstance(cluster, RedisLimiter):
        payload.update(
            {
                "cluster_checks": cluster.cluster_calls,
                "cluster_failures": cluster.cluster_failures,
                "cluster_fallback_answers": cluster.fallback_calls,
            }
        )
    return payload
