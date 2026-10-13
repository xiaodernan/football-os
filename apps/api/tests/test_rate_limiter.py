"""The rate limiter, which guarded the doors that matter and had no test at all.

`limit()` sits on `/auth/register`, `/auth/login` and `/auth/account_delete` before any
credential is looked at, so it is the only thing standing between this API and a
credential-stuffing run — and `git grep` for it in `tests/` returned nothing. Route
tests cannot reach it either, because it returns early when `settings.env == "test"`,
for the same reason the response cache does: a limiter that survives from case to case
would make the twentieth registration in a session fail.

So these cases drive `RateLimiter.check` directly, which is where every decision lives.
The bypass gets a case of its own rather than being assumed, because a reader who does
not know it is there will conclude the limiter is simply untested.
"""

from __future__ import annotations

import time as time_module

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core import security
from app.core.security import MAX_BUCKETS, RateLimiter, limit


def _request(path: str = "/api/v1/auth/login", client: tuple[str, int] = ("203.0.113.9", 5)) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "query_string": b"",
            "headers": [],
            "client": client,
            "server": ("testserver", 80),
        }
    )


def _refusal(bucket: str = "login:203.0.113.9:/api/v1/auth/login", *, hits: int, limit_: int = 3, window: int = 60) -> HTTPException:
    limiter = RateLimiter()
    for _ in range(hits):
        limiter.check(bucket, limit_, window)
    with pytest.raises(HTTPException) as caught:
        limiter.check(bucket, limit_, window)
    return caught.value


def test_it_serves_up_to_the_limit_and_then_refuses() -> None:
    limiter = RateLimiter()
    for _ in range(3):
        limiter.check("b", 3, 60)
    with pytest.raises(HTTPException) as caught:
        limiter.check("b", 3, 60)
    assert caught.value.status_code == 429


def test_the_refusal_speaks_the_codes_that_are_census_tracked() -> None:
    """§60's census assembles status codes from the modules that raise them."""
    detail = _refusal(hits=3).detail
    assert detail["code"] == "rate_limited"
    assert detail["message"] == "Too many requests, slow down"


def test_the_refusal_tells_the_caller_how_long_to_wait() -> None:
    """`Retry-After` is what makes a 429 actionable instead of just a failure."""
    headers = _refusal(hits=3).headers
    assert "Retry-After" in headers
    retry = int(headers["Retry-After"])
    assert retry >= 1, "a zero or negative wait would tell the caller to try immediately"


def test_the_wait_is_what_frees_the_oldest_slot() -> None:
    """The value has to describe the hit that is about to expire, not an arbitrary one.

    Three hits land and the fourth is refused; the oldest of the three is the one whose
    expiry opens a slot, so `Retry-After` must be the remainder of *its* window.
    """
    limiter = RateLimiter()
    bucket = "b"
    first = time_module.time()
    limiter.check(bucket, 3, 60)
    limiter.check(bucket, 3, 60)
    limiter.check(bucket, 3, 60)
    elapsed = time_module.time() - first
    with pytest.raises(HTTPException) as caught:
        limiter.check(bucket, 3, 60)

    retry = int(caught.value.headers["Retry-After"])
    assert retry <= 61, "the wait can never exceed one window"
    assert retry >= 60 - elapsed, "the wait must still cover what is left of the oldest hit's window"


def test_hits_outside_the_window_stop_counting(monkeypatch: pytest.MonkeyPatch) -> None:
    """A sliding window, not a fixed one: the count follows the clock."""
    now = 1_000_000.0
    monkeypatch.setattr(security.time, "time", lambda: now)

    limiter = RateLimiter()
    for _ in range(3):
        limiter.check("b", 3, 60)

    now += 61  # every hit is now older than the window
    limiter.check("b", 3, 60)  # must not raise: the window slid

    limiter.check("b", 3, 60)
    limiter.check("b", 3, 60)
    with pytest.raises(HTTPException):
        limiter.check("b", 3, 60)


def test_buckets_do_not_see_each_other() -> None:
    """A scope, a path or a client that differs is a different budget.

    The key is `scope:client:path`, and the point of taking all three is that one
    noisy office (`/register`) cannot spend `/login`'s budget, and one caller cannot
    spend another's.
    """
    limiter = RateLimiter()
    for _ in range(3):
        limiter.check("login:203.0.113.9:/login", 3, 60)

    with pytest.raises(HTTPException):
        limiter.check("login:203.0.113.9:/login", 3, 60)

    limiter.check("login:198.51.100.7:/login", 3, 60)  # another client
    limiter.check("register:203.0.113.9:/login", 3, 60)  # another scope
    limiter.check("login:203.0.113.9:/register", 3, 60)  # another path


def test_the_map_stays_bounded_when_the_buckets_keep_coming() -> None:
    """The comment in the code says "keep the map bounded". It has to mean it.

    Buckets are keyed by client IP, which is a dimension nobody controls: an attacker
    rotating source addresses creates them faster than any window can expire them.
    The prune that runs at the stated cap only drops *idle* buckets, so against a
    sustained flood it drops nothing and the map grows without limit — a memory leak
    reachable from outside, behind the very doors the limiter is there to protect.

    This asserts the invariant the comment promises rather than the mechanism: no
    number of live buckets may take the map past `MAX_BUCKETS`.
    """
    limiter = RateLimiter()
    for i in range(MAX_BUCKETS + 1000):
        limiter.check(f"probe:10.0.0.{i}:/probe", 5, 3600)

    assert len(limiter._hits) <= MAX_BUCKETS, (  # noqa: SLF001 - the invariant lives in that attribute
        f"the map holds {len(limiter._hits)} buckets after a flood of {MAX_BUCKETS + 1000} live ones, " f"with a cap of {MAX_BUCKETS}"
    )


def test_the_environment_bypass_is_what_keeps_route_tests_running() -> None:
    """Why no route test can reach this, stated rather than assumed.

    `limit()` returns before touching the limiter when `settings.env == "test"`, so a
    session that registers twenty times does not fail on the fourth. The limiter itself
    is untouched by that decision, which is what makes these cases possible at all.
    """
    from app.core.config import settings

    assert settings.env == "test"

    request = _request()
    for _ in range(20):
        limit(request, 1, 60, scope="probe")  # would raise on the second call if the bypass were absent

    fresh = RateLimiter()
    fresh.check("probe", 1, 60)
    with pytest.raises(HTTPException):
        fresh.check("probe", 1, 60)  # the limiter behind the bypass still refuses at 1
