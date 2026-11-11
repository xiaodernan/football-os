"""The door limiter: what `limit()` promises the routes that call it.

This file used to test `app.core.security.RateLimiter` — a fixed window in a process-local dict,
keyed on the socket's peer. That class is gone. `limit()` now charges the same tier the middleware
does (`app.core.ratelimit`), against the same identity rule (`app.core.rate_policy.caller_key`), and
the algorithm's own cases live in `test_rate_limit.py`. What is left here is the part only this seam
can answer: **does a route that asks for `N per W seconds` actually get it, counted against the right
caller, on the right door?**

Two of the old cases changed meaning rather than wording, and both changes are the point of the
takeover:

* `Retry-After` used to be the remainder of the oldest hit's window — up to a full window. A token
  bucket's retry is the time to *one more token*, so a 3-per-minute door now says 20 seconds, not 60.
* The bucket used to be keyed on the peer alone. Behind this project's own edge every caller arrives
  from the proxy's address, so one bucket counted the whole internet; a caller with a credential was
  counted by address anyway, so one account could spend another's budget by sharing its NAT.

Route tests cannot reach any of this: `limit()` returns early when `settings.env == "test"`, for the
same reason the response cache does — a limiter that survived from case to case would fail the
twentieth registration in a session. So these cases put the module's own settings into a serving
posture and drive `limit()` directly. The bypass gets a case of its own rather than being assumed.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import replace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core import ratelimit, security
from app.core.config import Settings, settings
from app.core.ratelimit import Decision, Policy, TwoTierLimiter, get_limiter, reset_limiter
from app.core.security import limit

TRUSTED = ("127.0.0.1/32", "::1/128")


def _request(
    verb: str = "POST",
    path: str = "/api/v1/auth/login",
    *,
    peer: str = "203.0.113.9",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": verb,
            "scheme": "http",
            "path": path,
            "query_string": b"",
            "headers": headers or [],
            "client": (peer, 5) if peer else None,
            "server": ("testserver", 80),
        }
    )


def _serve(request: Request, ceiling: int, window: int = 60, *, scope: str = "probe", times: int = 500) -> tuple[int, HTTPException | None]:
    """Ask until refused. Returns how many were served and the refusal that stopped it."""
    served = 0
    for _ in range(times):
        try:
            limit(request, ceiling, window, scope=scope)
        except HTTPException as refusal:
            return served, refusal
        served += 1
    return served, None


@pytest.fixture
def priced(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """A serving posture: the limiter armed, no shared store, the loopback proxies trusted."""
    reset_limiter()
    live = replace(settings, env="production", rate_limit_redis_url="", rate_limit_trusted_proxies=TRUSTED)
    monkeypatch.setattr(security, "settings", live)
    yield live
    reset_limiter()


# --------------------------------------------------------------------------------------------------
# The ceiling a route asks for
# --------------------------------------------------------------------------------------------------


def test_the_door_serves_up_to_its_ceiling_and_then_refuses(priced: Settings) -> None:
    served, refusal = _serve(_request(), 3)
    assert served == 3
    assert refusal is not None
    assert refusal.status_code == 429


def test_the_doors_policy_keeps_the_ceiling_the_route_published(priced: Settings) -> None:
    """No door's stated price moves in the takeover: burst `N`, sustained `N / W`.

    `/auth/register` asks for 5 per 300 s and `/auth/login` for 10 per 300 s; both still mean that.
    The policy is built once per (scope, ceiling, window) because a door called a thousand times a
    second must not re-run `Policy.__post_init__` or re-allocate the object on every call.
    """
    register = security._door_policy("register", 5, 300)  # noqa: SLF001 - the cache is the claim
    assert register.capacity == 5
    assert register.refill_per_second == pytest.approx(5 / 300)
    assert security._door_policy("register", 5, 300) is register  # noqa: SLF001
    login = security._door_policy("login", 10, 300)  # noqa: SLF001
    assert login.capacity == 10
    assert login is not register


def test_the_refusal_speaks_the_code_the_census_tracks(priced: Settings) -> None:
    """§60's census assembles status codes from the modules that raise them, and the web tier holds
    a sentence for `rate_limited` in six catalogues. The message now names the door and the wait."""
    _, refusal = _serve(_request(), 3, scope="login")
    assert refusal is not None
    assert refusal.detail["code"] == "rate_limited"
    assert refusal.detail["message"] == "Too many requests for login; retry in 20s"


def test_the_wait_is_the_time_to_one_more_token(priced: Settings) -> None:
    """The semantics that changed. A fixed window's `Retry-After` was the remainder of the oldest
    hit's window — for a 3-per-minute door, up to 60 seconds. A bucket refills continuously, so the
    wait is one token's worth: `window / ceiling`, rounded up. Telling a caller to wait three times
    longer than the door needs is a throttle the policy never asked for.
    """
    ceiling, window = 3, 60
    _, refusal = _serve(_request(), ceiling, window)
    assert refusal is not None
    retry = int(refusal.headers["Retry-After"])
    assert retry == math.ceil(window / ceiling)
    assert retry < window, "a full-window wait is the fixed window's answer, not the bucket's"


def test_the_door_opens_again_once_a_token_refills(priced: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """The wait is a promise, so it has to be kept. Clock pinned rather than slept: a case that
    waits on the wall clock measures the host's load as well as the limiter."""
    clock = [1_000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: clock[0])

    request = _request()
    served, refusal = _serve(request, 2, 2)  # one token per second
    assert served == 2
    assert refusal is not None

    clock[0] += 0.5  # half a token: still shut
    served, half = _serve(request, 2, 2, times=1)
    assert served == 0
    assert half is not None

    clock[0] += 0.5  # one whole token
    served, _ = _serve(request, 2, 2, times=1)
    assert served == 1, "the published wait must actually open the door"
    served, _ = _serve(request, 2, 2, times=1)
    assert served == 0, "and open it for exactly one request, not for the whole burst again"


# --------------------------------------------------------------------------------------------------
# Who is counted
# --------------------------------------------------------------------------------------------------


def test_the_door_counts_the_credential_not_the_socket(priced: Settings) -> None:
    """Two accounts behind one NAT address are two budgets. The old limiter keyed the peer alone,
    so the second account inherited the first one's refusal."""
    path = "/api/v1/careers/car_a/tickets"
    alice = _request("GET", path, peer="198.51.100.4", headers=[(b"authorization", b"Bearer alice-token")])
    bob = _request("GET", path, peer="198.51.100.4", headers=[(b"authorization", b"Bearer bob-token")])

    served, refusal = _serve(alice, 3)
    assert (served, refusal is not None) == (3, True)
    assert _serve(bob, 3)[0] == 3, "one account must not be able to spend another's budget"


def test_the_door_reads_forwarded_for_only_from_a_trusted_proxy(priced: Settings) -> None:
    """Behind the edge every caller shares the proxy's socket, so the header is the only thing that
    tells them apart — and a header anyone can type must not mint a new identity."""
    path = "/api/v1/boards"
    proxied_a = _request("GET", path, peer="127.0.0.1", headers=[(b"x-forwarded-for", b"203.0.113.7")])
    proxied_b = _request("GET", path, peer="127.0.0.1", headers=[(b"x-forwarded-for", b"203.0.113.8")])
    assert _serve(proxied_a, 2)[0] == 2
    assert _serve(proxied_b, 2)[0] == 2, "two callers behind one proxy are two budgets"

    get_limiter().reset()
    direct_a = _request("GET", path, peer="198.51.100.4", headers=[(b"x-forwarded-for", b"203.0.113.7")])
    direct_b = _request("GET", path, peer="198.51.100.4", headers=[(b"x-forwarded-for", b"203.0.113.8")])
    assert _serve(direct_a, 2)[0] == 2
    assert _serve(direct_b, 2)[0] == 0, "an untrusted peer's header must not buy a fresh budget"


def test_the_erase_bucket_is_per_account(priced: Settings) -> None:
    """The case a live walk exposed: `account_delete` was keyed by client address alone, so the Nth
    verification walk of the day — a fresh account every time — answered 429 for a caller that had
    never erased anything. The door now carries the account in its scope, because the door already
    requires a valid session: one hijacked session stays bounded at three an hour, and the
    address-rotating flood is the register and login limiters' problem, not this door's.
    """
    path = "/api/v1/auth/account"
    for account in ("usr_aaaaaaaa", "usr_bbbbbbbb"):
        request = _request("DELETE", path, peer="198.51.100.4")
        served, refusal = _serve(request, 3, 3600, scope=f"account_delete:{account}")
        assert served == 3, f"{account} behind a shared address must get its own three"
        assert refusal is not None


# --------------------------------------------------------------------------------------------------
# Which door is counted
# --------------------------------------------------------------------------------------------------


def test_a_read_door_and_a_write_door_on_one_path_keep_their_own_budgets(priced: Settings) -> None:
    """`/careers/{ident}/tickets` is a GET priced at 60 a minute and a PUT priced at 20.

    Same scope, same path, two prices. Without the verb in the key those are one bucket, and the
    measurement before the fix was blunt: twenty PUTs left the GET door serving **zero** against a
    ceiling it publishes as sixty. The write ceiling itself held — `_refill` clamps to the current
    policy's capacity — so this was never an over-admission hole, only a door throttled by traffic
    it does not own.
    """
    path = "/api/v1/careers/car_probe/tickets"
    read = _request("GET", path)
    write = _request("PUT", path)

    assert _serve(write, 20, scope="career_tickets")[0] == 20
    assert _serve(read, 60, scope="career_tickets")[0] == 60, "the read door's ceiling is not the write door's to spend"

    get_limiter().reset()
    assert _serve(read, 60, scope="career_tickets")[0] == 60
    assert _serve(write, 20, scope="career_tickets")[0] == 20, "and the other order holds too"


def test_the_door_asks_the_one_tier_with_a_door_key(priced: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """The seam itself: production must reach the shared tier, not merely have it available.

    A recorder in place of `get_limiter` reads the key and the policy the door actually passes, and
    the configured store URL is set to a value nothing else would produce — so a `limit()` that
    hardcoded `""` would be caught here rather than looking correct on a host with no Redis.
    """
    urls: list[str] = []
    asked: list[tuple[str, Policy]] = []
    tier = TwoTierLimiter(None)
    real_decide = tier.decide

    def record(url: str) -> TwoTierLimiter:
        urls.append(url)
        return tier

    def decide_spy(key: str, policy: Policy) -> Decision:
        asked.append((key, policy))
        return real_decide(key, policy)

    monkeypatch.setattr(security, "get_limiter", record)
    monkeypatch.setattr(tier, "decide", decide_spy)
    monkeypatch.setattr(security, "settings", replace(priced, rate_limit_redis_url="redis://127.0.0.1:6399/9"))

    path = "/api/v1/careers/car_probe/tickets"
    limit(_request("PUT", path, headers=[(b"authorization", b"Bearer secret-token")]), 20, 60, scope="career_tickets")

    assert urls == ["redis://127.0.0.1:6399/9"], "the configured store must reach the tier"
    assert len(asked) == 1
    key, policy = asked[0]
    parts = key.split(":")
    assert parts[0] == "door"
    assert parts[1] == "career_tickets"
    assert parts[2] == "PUT"
    assert parts[-1] == path
    assert "secret-token" not in key, "the credential must never be the key"
    assert policy.capacity == 20
    assert policy.refill_per_second == pytest.approx(20 / 60)


def test_no_second_limiter_survives_beside_the_tier(priced: Settings) -> None:
    """`ratelimit.py`'s first line says "the tier this replaces is `security.RateLimiter`". That is
    only true while nothing of it is left: a surviving class would be a second clock, a second
    identity rule and a second bound, and the doors would be split across them."""
    for retired in ("RateLimiter", "rate_limiter", "MAX_BUCKETS"):
        assert not hasattr(security, retired), f"security still exports {retired}"
    assert security.get_limiter is ratelimit.get_limiter, "the door must ask the one tier"

    from app.api.v1 import auth

    assert not hasattr(auth, "rate_limiter"), "the erase door must not hold a limiter of its own"


# --------------------------------------------------------------------------------------------------
# Why no route test can reach any of this
# --------------------------------------------------------------------------------------------------


def test_the_environment_bypass_is_what_keeps_route_tests_running() -> None:
    """Stated rather than assumed. `limit()` returns before touching the tier when
    `settings.env == "test"`, so a session that registers twenty times does not fail on the fourth.
    The tier behind the bypass is untouched by that decision, which is what makes the cases above
    possible at all."""
    assert settings.env == "test"
    reset_limiter()
    try:
        for _ in range(20):
            limit(_request(), 1, 60, scope="probe")  # would raise on the second call without the bypass
        tier = TwoTierLimiter(None)
        policy = Policy("probe", capacity=1, refill_per_second=1 / 60)
        assert tier.decide("probe", policy).allowed
        assert not tier.decide("probe", policy).allowed, "the tier behind the bypass still refuses at 1"
    finally:
        reset_limiter()
