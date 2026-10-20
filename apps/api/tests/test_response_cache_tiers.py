"""A second tier for the response cache: the part that makes four workers share.

The load runs in the verification doc found four workers lifting throughput 29% at
concurrency 10 but only 6% at concurrency 50, and one reason is visible without
measuring further: `_response_cache` is a module-level object, so four processes
have four independent caches and none of them can serve a response another one
already paid for.

`RedisCache` had landed and was, before these cases, called by nothing except the
metrics door that reports on it. These drive the two-tier read/write order with
`RedisCache` as the shared tier — which on a host with no usable instance degrades
to its own internal `TTLCache`, so the logic under test is the real class rather
than a stand-in for it.

The invariant the cases are built to protect: with no shared tier, or with a shared
tier that cannot serve, the behaviour is byte-for-byte what it was before.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.cache import TTLCache
from app.core.redis_cache import RedisCache
from app.main import cached_response_for, response_cache_key

Origin = Callable[[Request], Awaitable[Response]]


class _ServingRedis:
    """A stand-in that answers the four commands `RedisCache` issues.

    The real class was exercised against a live instance elsewhere; what is under test
    here is the *ordering* between two tiers, which needs a shared tier that serves
    without needing a server. `RedisCache` is still the class under test — only its
    connection is replaced, so the read-through, write-through and key prefixing are
    the production code's.
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def ping(self) -> bool:
        return True

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        return True

    def delete(self, *keys: str) -> int:
        return sum(1 for k in keys if self.store.pop(k, None) is not None)

    def scan_iter(self, match: str = "*"):
        yield from list(self.store)


def _serving_shared() -> RedisCache:
    shared = RedisCache()
    shared._redis = _ServingRedis()  # noqa: SLF001 - the seam the class exposes for this
    shared._available = True  # noqa: SLF001
    return shared


def _request(path: str = "/api/v1/healthz", query: str = "", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "query_string": query.encode(),
            "headers": headers or [],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
        }
    )


def _origin(body: dict[str, object] | None = None) -> tuple[Origin, list[int]]:
    """An origin that records how often it was actually reached."""
    calls: list[int] = []

    async def call_next(_request: Request) -> Response:
        calls.append(1)
        return JSONResponse(content=body if body is not None else {"status": "ok"}, status_code=200)

    return call_next, calls


def test_a_response_already_fetched_by_another_process_is_served_without_the_origin() -> None:
    """Process A pays for the response; process B must not have to."""
    shared = _serving_shared()
    process_a, calls_a = _origin({"answer": 42})
    process_b, calls_b = _origin({"answer": 42})

    async def run() -> tuple[str, str]:
        first = await cached_response_for(TTLCache(), _request(), process_a, shared=shared)
        second = await cached_response_for(TTLCache(), _request(), process_b, shared=shared)
        return first.headers["X-Cache"], second.headers["X-Cache"]

    first_header, second_header = asyncio.run(run())
    assert first_header == "MISS"
    assert second_header == "HIT", "a cold near-tier must still find the answer in the shared tier"
    assert len(calls_a) == 1
    assert len(calls_b) == 0, "the whole point of a shared tier is that the second process pays nothing"


def test_the_shared_tier_carries_the_body_intact() -> None:
    shared = _serving_shared()
    origin, _ = _origin({"nested": {"goals": 3}})

    async def run() -> bytes:
        await cached_response_for(TTLCache(), _request(), origin, shared=shared)
        replayed = await cached_response_for(TTLCache(), _request(), origin, shared=shared)
        return replayed.body

    body = asyncio.run(run())
    assert b'"goals"' in body and b"3" in body


def test_an_unusable_shared_tier_degrades_to_the_behaviour_it_replaced() -> None:
    """The case that matters most: nothing may depend on the second tier existing."""
    shared = RedisCache(redis_url="redis://127.0.0.1:1/0")  # nothing listens there
    assert shared.available is False

    near = TTLCache()
    origin, calls = _origin()

    async def run() -> tuple[str, str]:
        first = await cached_response_for(near, _request(), origin, shared=shared)
        second = await cached_response_for(near, _request(), origin, shared=shared)
        return first.headers["X-Cache"], second.headers["X-Cache"]

    first_header, second_header = asyncio.run(run())
    assert first_header == "MISS"
    assert second_header == "HIT", "the near tier alone must still serve a second request"
    assert len(calls) == 1


def test_a_tier_that_cannot_serve_is_not_written_to() -> None:
    """The failure mode that would have been invisible.

    `RedisCache` keeps an internal `TTLCache` for exactly the case where Redis is down,
    which is right for a standalone cache and wrong for a *shared* one: writing into it
    while Redis is unavailable would build a second process-local cache, and the shared
    tier would then look healthy to anyone reading its hit rate while sharing nothing.
    `available` is what stops that write.
    """
    shared = RedisCache(redis_url="redis://127.0.0.1:1/0")
    assert shared.available is False
    origin, _ = _origin()

    asyncio.run(cached_response_for(TTLCache(), _request(), origin, shared=shared))

    assert shared.get_stats()["fallback"]["sets"] == 0, "a tier that cannot serve must not be written to"
    assert shared.get(response_cache_key("/api/v1/healthz", "")) is None


def test_no_shared_tier_is_the_pre_two_tier_behaviour() -> None:
    near = TTLCache()
    origin, calls = _origin()

    async def run() -> tuple[str, str]:
        first = await cached_response_for(near, _request(), origin)
        second = await cached_response_for(near, _request(), origin)
        return first.headers["X-Cache"], second.headers["X-Cache"]

    assert asyncio.run(run()) == ("MISS", "HIT")
    assert len(calls) == 1


def test_the_key_is_the_same_for_both_tiers() -> None:
    """One key space, or the second tier would never be found by the first."""
    assert response_cache_key("/a", "b=1") == response_cache_key("/a", "b=1")


def test_the_shared_tier_does_not_hand_one_origins_answer_to_another() -> None:
    """The reason the origin is part of the key at all, checked where it matters most.

    The near tier can only ever be read by the process that wrote it. The shared one
    cannot: an entry written by a worker serving `localhost:3210` is read by every worker,
    so a key that ignored `Origin` would put one browser's `Access-Control-Allow-Origin`
    in front of another's across the whole deployment — not just for the life of one
    process's cache.
    """
    shared = _serving_shared()

    async def origin(request: Request) -> Response:
        response = JSONResponse(content={"status": "ok"})
        asking = request.headers.get("origin")
        if asking:
            response.headers["Access-Control-Allow-Origin"] = asking
        return response

    async def run() -> tuple[str, str]:
        first = await cached_response_for(TTLCache(), _request(headers=[(b"origin", b"http://localhost:3210")]), origin, shared=shared)
        second = await cached_response_for(TTLCache(), _request(headers=[(b"origin", b"http://127.0.0.1:3210")]), origin, shared=shared)
        return first.headers["X-Cache"], second.headers["X-Cache"]

    first_header, second_header = asyncio.run(run())
    assert first_header == "MISS"
    assert second_header == "MISS", "the shared tier must not answer a different origin from the one that wrote it"


PER_REQUEST_HEADERS = ("X-Request-ID", "X-Request-Duration-Ms")


def _origin_carrying_request_headers(body: dict[str, int] | None = None) -> tuple[Origin, list[Response]]:
    """An origin whose response already carries what `request_context` adds.

    Which is the real shape: `request_context` runs inside `response_cache`, so by the
    time the body is captured for storage those headers are already on the response.
    A stub that omits them would let every test below pass without exercising anything.
    """
    produced: list[Response] = []

    async def origin(_request: Request) -> Response:
        response = JSONResponse(content=body or {"goals": 1})
        response.headers["X-Request-ID"] = "req-origin-0001"
        response.headers["X-Request-Duration-Ms"] = "12"
        produced.append(response)
        return response

    return origin, produced


def test_per_request_headers_are_never_stored() -> None:
    """A cached response must not carry the previous caller's identity.

    Found live rather than by reading: two different requests returned the same
    `X-Request-ID` and the same `X-Request-Duration-Ms`, because both came from the
    headers captured on the MISS and replayed on the HIT. The second caller was
    attributed to the first in any log correlating on that header, and its duration
    was reported as someone else's.

    Storing them is also the wrong direction for a *shared* tier: a per-request
    identifier would cross a process boundary through Redis and outlive the request
    that produced it.
    """
    near = TTLCache()
    origin, _ = _origin_carrying_request_headers()

    async def run() -> dict[str, object]:
        await cached_response_for(near, _request(), origin)
        return near.get(response_cache_key("/api/v1/healthz", ""))

    payload = asyncio.run(run())
    stored_names = [name.lower() for name, _value in payload["headers"]]
    for header in PER_REQUEST_HEADERS:
        assert header.lower() not in stored_names, f"{header} belongs to one request and may not be shared"


def test_a_replay_carries_no_stale_identity() -> None:
    """The HIT is a different request; it may not answer under the MISS's name."""
    near = TTLCache()
    origin, _ = _origin_carrying_request_headers()

    async def run() -> Response:
        await cached_response_for(near, _request(), origin)
        return await cached_response_for(near, _request(), origin)

    replay = asyncio.run(run())
    assert replay.headers.get("X-Cache") == "HIT"
    for header in PER_REQUEST_HEADERS:
        assert header not in replay.headers, f"a replay may not answer as {header}"
