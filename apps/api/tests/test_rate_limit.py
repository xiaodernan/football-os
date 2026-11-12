"""M15's rate limiter: the algorithm, the policy table, and the identity it counts.

The four claims, in the order they can go wrong:

* **The arithmetic.** A token bucket admits `capacity` back to back and then `refill × t` more over
  any interval. The fixed window it replaced admitted `2 × limit` across a window boundary — the
  test that pins this is `test_a_bucket_does_not_double_spend_across_a_boundary`, and it is the
  reason the change is worth making rather than a rewrite for its own sake.
* **The identity.** A budget counted against the socket's peer collapses every caller behind one
  NAT into one bucket; a budget counted against a header the caller types is not a budget at all.
  `caller_key` is a three-branch function and each branch has a case here.
* **The venue.** The pre-filter is not a second limiter, it is a way of not asking the shared store
  on every request from a caller that has already spent its burst. Both branches are driven here.
* **The degradation.** A store that is down must not take the product down, and it must not take the
  limit down silently either: the answer says `scope=process`. Case: `test_a_broken_store_degrades`.
"""

from __future__ import annotations

import os
import time
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core.rate_policy import (
    AUTH,
    DEFAULT,
    MEDIA,
    POLICY_TABLE,
    UPLOAD,
    caller_key,
    policy_for,
)
from app.core.ratelimit import (
    Decision,
    MemoryLimiter,
    Policy,
    RedisLimiter,
    TwoTierLimiter,
    get_limiter,
    reset_limiter,
    snapshot,
)

# --------------------------------------------------------------------------------------------------
# The policy table
# --------------------------------------------------------------------------------------------------


def test_policy_table_prices_the_doors_it_names() -> None:
    """The order is the document: `/auth` must be priced before the generic rule that would match it."""
    assert policy_for("/api/v1/auth/login") is AUTH
    assert policy_for("/api/v1/auth/register") is AUTH
    assert policy_for("/api/v1/players") is DEFAULT
    assert policy_for("/api/v1/coach/ask") is not DEFAULT
    assert policy_for("/api/v1/knowledge/ask") is not DEFAULT
    # A prefix is not a word: `/coach/ask` must not price `/coach/asksomething`, which is why every
    # entry that names a leaf carries the slash it ends with.
    assert policy_for("/api/v1/coach/askers") is DEFAULT


def test_the_video_media_doors_are_priced_as_readers_not_as_uploads() -> None:
    """A report page asks for one page's worth of frames per navigation; uploads ask for one clip."""
    assert policy_for("/api/v1/video/upload") is UPLOAD
    assert policy_for("/api/v1/video/vid_abc123/frames/0") is MEDIA
    assert policy_for("/api/v1/video/vid_abc123/frames/24") is MEDIA
    assert policy_for("/api/v1/video/vid_abc123/file") is MEDIA
    assert policy_for("/api/v1/video/vid_abc123") is MEDIA
    assert policy_for("/api/v1/video/vid_abc123/analyse") is MEDIA


def test_exempt_and_foreign_paths_are_not_priced() -> None:
    assert policy_for("/api/v1/healthz") is None
    assert policy_for("/api/v1/openapi.json") is None
    assert policy_for("/actuator/health") is None
    assert policy_for("/healthz") is None


def test_every_policy_is_well_formed() -> None:
    """A policy whose cost exceeds its capacity could never be allowed, and the door would be shut."""
    distinct = {policy.name: policy for _, policy in POLICY_TABLE}
    assert set(distinct) == {"auth", "expensive", "upload", "write", "media"}, "the table's names are its price list"
    distinct[DEFAULT.name] = DEFAULT
    for policy in distinct.values():
        assert policy.capacity >= 1
        assert policy.refill_per_second > 0
        assert 1 <= policy.cost <= policy.capacity


# --------------------------------------------------------------------------------------------------
# The arithmetic
# --------------------------------------------------------------------------------------------------


def test_burst_is_spent_then_refused() -> None:
    limiter = MemoryLimiter()
    policy = Policy("t", capacity=3, refill_per_second=1.0)
    decisions = [limiter.decide("k", policy, now=100.0) for _ in range(4)]
    assert [d.allowed for d in decisions] == [True, True, True, False]
    assert [d.remaining for d in decisions] == [2, 1, 0, 0]
    assert decisions[-1].scope == "process"


def test_a_bucket_does_not_double_spend_across_a_boundary() -> None:
    """The property a fixed window does not have: no interval admits more than capacity + rate × t.

    The same caller asks three times at the end of one second and three times at the start of the
    next. A fixed window with `limit=3` would admit all six; a bucket admits three and then nothing
    until a token refills.
    """
    limiter = MemoryLimiter()
    policy = Policy("t", capacity=3, refill_per_second=1.0)
    late = [limiter.decide("k", policy, now=0.99) for _ in range(3)]
    early = [limiter.decide("k", policy, now=1.01) for _ in range(3)]
    assert all(d.allowed for d in late)
    assert not any(d.allowed for d in early)


def test_refill_restores_the_budget_at_the_published_rate() -> None:
    limiter = MemoryLimiter()
    policy = Policy("t", capacity=2, refill_per_second=2.0)  # one token every 500 ms
    assert limiter.decide("k", policy, now=0.0).allowed
    assert limiter.decide("k", policy, now=0.0).allowed
    assert not limiter.decide("k", policy, now=0.0).allowed
    # Half a second later exactly one token exists — enough for one request, not for two.
    assert limiter.decide("k", policy, now=0.5).allowed
    assert not limiter.decide("k", policy, now=0.5).allowed


def test_retry_after_is_the_time_to_one_more_token() -> None:
    limiter = MemoryLimiter()
    policy = Policy("t", capacity=1, refill_per_second=0.5)  # one token per two seconds
    limiter.decide("k", policy, now=0.0)
    refused = limiter.decide("k", policy, now=0.0)
    assert refused.allowed is False
    # A token takes 2 s, and the answer is rounded up so a client that obeys it is not refused again.
    assert refused.retry_after == 2
    assert refused.headers()["Retry-After"] == "2"


def test_buckets_are_isolated_by_key() -> None:
    limiter = MemoryLimiter()
    policy = Policy("t", capacity=1, refill_per_second=0.1)
    assert limiter.decide("a", policy, now=0.0).allowed
    assert not limiter.decide("a", policy, now=0.0).allowed
    assert limiter.decide("b", policy, now=0.0).allowed


def test_memory_is_bounded_without_evicting_a_live_bucket_first() -> None:
    """A flood of distinct identities must not grow the dict without bound — the old limiter's bug."""
    limiter = MemoryLimiter(max_buckets=4)
    policy = Policy("t", capacity=1, refill_per_second=1.0)
    for index in range(10):
        limiter.decide(f"k{index}", policy, now=float(index))
    assert len(limiter._buckets) == 4  # noqa: SLF001 - the bound is the claim


def test_headers_carry_both_spellings_and_the_policy() -> None:
    allowed = Decision(True, "default", 240, 239, 0, "cluster", "cluster")
    headers = allowed.headers()
    assert headers["RateLimit-Limit"] == "240"
    assert headers["X-RateLimit-Limit"] == "240"
    assert headers["RateLimit-Policy"] == '"default";q=240;w=1'
    assert headers["X-RateLimit-Scope"] == "cluster"
    assert "Retry-After" not in headers

    refused = Decision(False, "auth", 12, 0, 4, "cluster", "cluster")
    assert refused.headers()["Retry-After"] == "4"
    assert refused.headers()["RateLimit-Reset"] == "4"


# --------------------------------------------------------------------------------------------------
# The venue
# --------------------------------------------------------------------------------------------------


class _StubCluster:
    """A cluster that answers without a store: the pre-filter's behaviour is what is under test."""

    def __init__(self, allow: bool = True) -> None:
        self.calls = 0
        self.allow = allow

    def decide(self, key: str, policy: Policy) -> Decision:
        self.calls += 1
        return Decision(self.allow, policy.name, policy.capacity, policy.capacity - 1, 0, "cluster", "cluster")


def test_prefilter_answers_without_asking_the_cluster() -> None:
    cluster = _StubCluster()
    limiter = TwoTierLimiter(cluster)  # type: ignore[arg-type]
    policy = Policy("t", capacity=2, refill_per_second=0.001)
    assert limiter.decide("k", policy).allowed
    assert limiter.decide("k", policy).allowed
    refused = limiter.decide("k", policy)
    assert refused.allowed is False
    assert cluster.calls == 2, "the pre-filter's refusal must not reach the shared store"
    assert limiter.short_circuited == 1


def test_cluster_answers_when_the_prefilter_admits() -> None:
    cluster = _StubCluster(allow=False)
    limiter = TwoTierLimiter(cluster)  # type: ignore[arg-type]
    policy = Policy("t", capacity=5, refill_per_second=1.0)
    decision = limiter.decide("k", policy)
    assert cluster.calls == 1
    assert decision.allowed is False
    assert decision.scope == "cluster"


class _BrokenStore:
    def script_load(self, script: str) -> str:
        return "0" * 40

    def evalsha(self, *args: object) -> list[int]:
        raise ConnectionError("the store is down")


def test_a_broken_store_degrades() -> None:
    limiter = RedisLimiter(_BrokenStore())
    policy = Policy("t", capacity=2, refill_per_second=1.0)
    decision = limiter.decide("k", policy)
    assert decision.allowed is True
    assert decision.scope == "process", "a degraded answer must say which tier judged it"
    assert limiter.cluster_failures == 1
    assert limiter.fallback_calls == 1


def test_snapshot_names_the_scope_it_runs_in() -> None:
    limiter = TwoTierLimiter(_StubCluster())  # type: ignore[arg-type]
    payload = snapshot(limiter)
    assert payload["configured"] is True
    assert payload["scope"] == "cluster"


def test_no_limiter_configured_is_reported_as_such() -> None:
    reset_limiter()
    assert snapshot(None)["configured"] is False
    # Build the singleton with no store at all, so the metrics door answers about a real object.
    built = get_limiter("")
    assert snapshot(built)["scope"] == "process"


def test_the_store_defaults_to_the_cache_tiers_and_can_be_pointed_elsewhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """`config.py` says the limiter shares the cache's instance unless a deployment separates them.

    That sentence is only true if the fallback lives in `Settings`. Both callers — the middleware and
    `security.limit` — pass `settings.rate_limit_redis_url` explicitly, and `get_limiter` treats an
    empty string as a value rather than an absence, so its own `REDIS_URL` fallback is unreachable
    from the wired path. A deployment that set only `REDIS_URL` would have run process-scoped while
    the comment promised a cluster.
    """
    from app.core.config import Settings

    monkeypatch.setenv("REDIS_URL", "redis://cache-host:6379/3")
    monkeypatch.delenv("RATE_LIMIT_REDIS_URL", raising=False)
    assert Settings().rate_limit_redis_url == "redis://cache-host:6379/3"

    monkeypatch.setenv("RATE_LIMIT_REDIS_URL", "redis://counter-host:6379/7")
    assert Settings().rate_limit_redis_url == "redis://counter-host:6379/7", "the limiter's own instance wins"

    reset_limiter()
    try:
        assert snapshot(get_limiter(""))["scope"] == "process", "an explicit empty URL must not consult the environment"
    finally:
        reset_limiter()


# --------------------------------------------------------------------------------------------------
# The identity
# --------------------------------------------------------------------------------------------------


def test_caller_key_prefers_the_credential() -> None:
    key = caller_key(
        authorization="Bearer abc.def.ghi",
        peer="10.0.0.9",
        forwarded_for="203.0.113.7",
        trusted_proxies=("127.0.0.1/32",),
    )
    assert key.startswith("acct:")
    assert "abc.def.ghi" not in key, "the token must never be the key"


def test_caller_key_reads_forwarded_for_from_a_trusted_peer() -> None:
    key = caller_key(
        authorization="",
        peer="127.0.0.1",
        forwarded_for="203.0.113.7, 10.0.0.1",
        trusted_proxies=("127.0.0.1/32", "::1/128"),
    )
    # The left-most entry is the client; the right-most is the proxy that appended it.
    assert key == "fwd:203.0.113.7"


def test_forwarded_for_from_an_untrusted_peer_is_ignored() -> None:
    key = caller_key(
        authorization="",
        peer="198.51.100.4",
        forwarded_for="203.0.113.7",
        trusted_proxies=("127.0.0.1/32",),
    )
    assert key == "ip:198.51.100.4", "a header anyone can type must not mint a new identity"


def test_an_empty_peer_still_gets_one_shared_name() -> None:
    key = caller_key(authorization="", peer="", forwarded_for="", trusted_proxies=())
    assert key == "ip:unknown", "an empty key would put every anonymous test request in one bucket"


# --------------------------------------------------------------------------------------------------
# The live store
# --------------------------------------------------------------------------------------------------


def test_the_script_is_atomic_against_a_live_server() -> None:
    """The Lua path, exercised against a real Redis when this host has one.

    Skipped with the reason printed when `REDIS_URL` is absent: the arithmetic above is proved on the
    in-process twin, and this case exists for the one thing the twin cannot prove — that the server
    evaluates the read-modify-write as one operation and reports the same numbers.
    """
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        pytest.skip("no REDIS_URL: the in-process twin covers the arithmetic, not the atomicity")
    import redis

    client = redis.from_url(url, decode_responses=True)
    client.ping()
    key = f"football_os:test:ratelimit:{time.time_ns()}"
    limiter = RedisLimiter(client)
    policy = Policy("live", capacity=3, refill_per_second=1.0)
    try:
        first = [limiter.decide(key, policy) for _ in range(3)]
        assert all(d.allowed for d in first)
        assert [d.remaining for d in first] == [2, 1, 0]
        refused = limiter.decide(key, policy)
        assert refused.allowed is False
        assert refused.scope == "cluster"
        assert refused.retry_after == 1
        time.sleep(1.05)
        assert limiter.decide(key, policy).allowed
    finally:
        client.delete(key)


# --------------------------------------------------------------------------------------------------
# The dresser: one header set, on every answer the tier judged
# --------------------------------------------------------------------------------------------------

BUDGET_HEADERS = (
    "RateLimit-Policy",
    "RateLimit-Limit",
    "RateLimit-Remaining",
    "RateLimit-Reset",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-RateLimit-Scope",
)


@pytest.fixture
def priced_app(monkeypatch: pytest.MonkeyPatch):
    """The real app, the limiter on, and four probe doors that need no database.

    The suite runs with `ENV=test`, where the limiter is off by default — a thousand requests from one
    identity on purpose must not be a budget test. These cases are about the *wiring*, so they turn it
    on for the app module alone (`Settings` is frozen, hence `replace`) and drop the process singleton
    on both sides so no other case inherits this one's spent buckets.

    The store is pinned to none here, and that is not a convenience: both wired callers pass
    `settings.rate_limit_redis_url`, so an operator who exports `REDIS_URL` would otherwise decide which
    tier these cases measure. The crash case below asserts the scope by name, and it went red on a
    working limiter for exactly that reason — `cluster` where the case had typed `process`. The wiring
    is proved against a known tier; the live store has its own case.
    """
    from app import main

    monkeypatch.setattr(main, "settings", replace(main.settings, rate_limit_enabled=True, rate_limit_redis_url=""))
    reset_limiter()
    app = main.create_app()

    @app.get("/api/v1/__probe_budget")
    def _budget() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/v1/auth/__probe_refusal")
    def _refusal() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/v1/__probe_boom")
    def _boom() -> None:
        raise RuntimeError("deliberate probe failure")

    @app.get("/__probe_free")
    def _free() -> dict[str, bool]:
        return {"ok": True}

    yield app
    reset_limiter()


def _budget_header_names(response) -> set[str]:
    return {name.lower() for name in response.headers if name.lower().startswith(("ratelimit-", "x-ratelimit-"))}


@pytest.fixture
def pinned_budget_clock(priced_app, monkeypatch: pytest.MonkeyPatch):
    """The same app, with the limiter's clock held still.

    A case that counts tokens across two HTTP calls is counting the host's speed as well: `DEFAULT`
    refills 40 tokens a second, so a 25 ms gap between two requests puts back the token the first one
    spent and `Remaining` never moves. That is not a hypothetical — under load this suite saw a 16 s
    call, and the decrement case went red on a limiter that was working exactly as designed.

    Pinned here rather than by freezing `time.monotonic` process-wide, because the event loop under
    `TestClient` reads that same clock to decide when its own deadlines are due. Only the tier's
    arithmetic is given a fixed `now`; everything else keeps the real one.
    """
    tier = get_limiter("")
    real_decide = tier.local.decide
    monkeypatch.setattr(tier.local, "decide", lambda key, policy: real_decide(key, policy, now=1_000.0))
    return priced_app


def test_a_priced_door_publishes_its_budget_on_every_answer(pinned_budget_clock) -> None:
    """The headers describe the request being answered, so two answers must not report one number."""
    with TestClient(pinned_budget_clock) as client:
        first = client.get("/api/v1/__probe_budget")
        second = client.get("/api/v1/__probe_budget")
    assert first.status_code == 200, f"the probe door answered {first.status_code}"
    assert second.status_code == 200, f"the probe door answered {second.status_code}"
    for response in (first, second):
        for name in BUDGET_HEADERS:
            assert response.headers.get(name), f"{name} is missing from a {response.status_code} answer"
    assert first.headers["RateLimit-Policy"] == f'"default";q={DEFAULT.capacity};w=1', first.headers["RateLimit-Policy"]
    assert int(second.headers["RateLimit-Remaining"]) == int(first.headers["RateLimit-Remaining"]) - 1, (
        f"the second answer reported {second.headers['RateLimit-Remaining']} after the first reported " f"{first.headers['RateLimit-Remaining']}: a budget that does not move while it is spent"
    )


def test_the_crash_answer_carries_the_budget_too(priced_app) -> None:
    """A 500 never comes back through the middleware, so the dresser has to be the one that speaks.

    This is the case that fails if the headers are written after `await call_next` instead of inside
    `dress_response`: the crash propagates out before those lines run, and a client retrying a 500 in
    a loop is exactly the client that needs to be told it is about to be refused.
    """
    with TestClient(priced_app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/__probe_boom")
    assert response.status_code == 500, f"the probe door answered {response.status_code}"
    for name in BUDGET_HEADERS:
        assert response.headers.get(name), f"{name} is missing from the crash answer"
    assert response.headers["X-RateLimit-Scope"] == "process", response.headers["X-RateLimit-Scope"]


def test_the_crash_answer_names_the_cluster_when_a_store_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other direction of the scope header, against a real store when this host has one.

    The case above pins the store to none so its verdict cannot depend on the operator's environment.
    This one is what makes that pin safe rather than a way of hiding the cluster: it proves the same
    dresser publishes `cluster` when the shared tier judged, so a limiter that always said `process`
    would not pass both. Skipped with the reason printed when no store is reachable.
    """
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        pytest.skip("no REDIS_URL: the process direction is proved above, this is the cluster direction")
    from app import main

    monkeypatch.setattr(main, "settings", replace(main.settings, rate_limit_enabled=True, rate_limit_redis_url=url))
    reset_limiter()
    app = main.create_app()

    @app.get("/api/v1/__probe_boom")
    def _boom() -> None:
        raise RuntimeError("deliberate probe failure")

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/api/v1/__probe_boom")
        assert response.status_code == 500, f"the probe door answered {response.status_code}"
        for name in BUDGET_HEADERS:
            assert response.headers.get(name), f"{name} is missing from the crash answer"
        assert response.headers["X-RateLimit-Scope"] == "cluster", response.headers["X-RateLimit-Scope"]
    finally:
        reset_limiter()


def test_the_refusal_publishes_the_same_header_set_as_the_success(pinned_budget_clock) -> None:
    """One list of headers, not two: a 429 that names a budget the 200 does not is a client's bug report.

    The burst has to be spent against a pinned clock for the same reason the decrement case does: at
    `AUTH`'s 0.2 tokens a second, a slow enough loop refills a token before request thirteen and the
    refusal this case exists to read never happens.
    """
    with TestClient(pinned_budget_clock) as client:
        allowed = [client.get("/api/v1/auth/__probe_refusal") for _ in range(AUTH.capacity)]
        refused = client.get("/api/v1/auth/__probe_refusal")
    assert all(r.status_code == 200 for r in allowed), "the auth burst was spent before the probe started"
    assert refused.status_code == 429, f"request {AUTH.capacity + 1} answered {refused.status_code}"
    assert refused.json()["detail"]["code"] == "rate_limited", refused.text
    assert refused.headers.get("Retry-After"), "a refusal without a retry is 'slow down', not 'come back in 4s'"
    assert _budget_header_names(refused) == _budget_header_names(allowed[0]), (
        f"the refusal published {sorted(_budget_header_names(refused))} where the success published " f"{sorted(_budget_header_names(allowed[0]))}"
    )


def test_a_door_outside_the_api_is_not_priced(priced_app) -> None:
    """The rule is about `/api/v1`. A header on a door the table never priced would be a made-up budget."""
    with TestClient(priced_app) as client:
        response = client.get("/__probe_free")
    assert response.status_code == 200, f"the probe door answered {response.status_code}"
    assert not _budget_header_names(response), f"an unpriced door published {sorted(_budget_header_names(response))}"
