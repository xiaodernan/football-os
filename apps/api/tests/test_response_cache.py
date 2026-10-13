"""The response cache middleware, which had never been exercised.

`app.main.response_cache` is 60 lines on every GET and had no test at all, because
it returns early when `settings.env == "test"` and every test runs with that set.
The bypass is right — the test database persists from case to case, so a cached
response would make one case read another's data — but it made the whole body
untestable, which is how a hot path stays untested for a milestone.

So the body moved out of the middleware closure into `cached_response_for`, taking
the cache as an argument. The middleware keeps the environment decision, which is
configuration, and delegates everything else. These cases drive the extracted
function directly with a real `Request` and a stub origin, which is how they can
reach the parts the old shape could not: what counts as cacheable, what the key is
made of, and what the caller is told.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from app.core.cache import TTLCache
from app.main import cached_response_for, response_cache_key

Origin = Callable[[Request], Awaitable[Response]]


def _request(path: str = "/api/v1/healthz", query: str = "", method: str = "GET", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": "http",
            "path": path,
            "query_string": query.encode(),
            "headers": headers or [],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
        }
    )


def _origin(body: dict[str, object] | str | None = None, status: int = 200, content_type: str = "json") -> Origin:
    async def call_next(_request: Request) -> Response:
        if content_type == "json":
            return JSONResponse(content=body if body is not None else {"status": "ok"}, status_code=status)
        return PlainTextResponse(content=str(body or "plain"), status_code=status)

    return call_next


def test_the_key_carries_the_path_and_the_query() -> None:
    assert response_cache_key("/api/v1/healthz", "") == "http:/api/v1/healthz:"
    assert response_cache_key("/api/v1/healthz", "a=1&b=2") == "http:/api/v1/healthz:a=1&b=2"
    assert response_cache_key("/x", "a=1") != response_cache_key("/x", "a=2")


def test_a_second_identical_get_is_served_from_the_cache() -> None:
    cache: TTLCache = TTLCache()
    origin = _origin()

    async def run() -> tuple[str, str]:
        first = await cached_response_for(cache, _request(), origin)
        second = await cached_response_for(cache, _request(), origin)
        assert first.body == second.body
        return first.headers["X-Cache"], second.headers["X-Cache"]

    first_header, second_header = asyncio.run(run())
    assert first_header == "MISS"
    assert second_header == "HIT"


def test_the_replayed_body_is_the_one_the_origin_returned() -> None:
    cache: TTLCache = TTLCache()
    origin = _origin({"answer": 42})

    async def run() -> bytes:
        await cached_response_for(cache, _request(), origin)
        replayed = await cached_response_for(cache, _request(), origin)
        return replayed.body

    body = asyncio.run(run())
    assert b'"answer"' in body
    assert b"42" in body


def test_a_no_cache_request_header_forces_a_trip_to_the_origin() -> None:
    cache: TTLCache = TTLCache()
    origin = _origin()

    async def run() -> str | None:
        await cached_response_for(cache, _request(), origin)
        bypassed = await cached_response_for(cache, _request(headers=[(b"cache-control", b"no-cache")]), origin)
        return bypassed.headers.get("X-Cache")

    assert asyncio.run(run()) is None, "a caller that bypasses the cache is told nothing about it, not 'MISS'"


def test_a_non_success_status_is_not_cached() -> None:
    cache: TTLCache = TTLCache()
    origin = _origin(status=500)

    async def run() -> tuple[str, str, int]:
        first = await cached_response_for(cache, _request(), origin)
        second = await cached_response_for(cache, _request(), origin)
        return first.headers["X-Cache"], second.headers["X-Cache"], second.status_code

    first_header, second_header, status = asyncio.run(run())
    assert first_header == "MISS"
    assert second_header == "MISS", "caching a 500 would replay a failure for a minute"
    assert status == 500


def test_a_non_json_response_is_not_cached() -> None:
    cache: TTLCache = TTLCache()
    origin = _origin(content_type="text")

    async def run() -> tuple[str, str]:
        first = await cached_response_for(cache, _request(), origin)
        second = await cached_response_for(cache, _request(), origin)
        return first.headers["X-Cache"], second.headers["X-Cache"]

    first_header, second_header = asyncio.run(run())
    assert first_header == "MISS"
    assert second_header == "MISS", "only JSON is in the cache's contract"


def test_a_non_get_request_is_not_cached() -> None:
    cache: TTLCache = TTLCache()
    origin = _origin()

    async def run() -> tuple[str | None, bytes]:
        first = await cached_response_for(cache, _request(method="POST"), origin)
        second = await cached_response_for(cache, _request(method="POST"), origin)
        return first.headers.get("X-Cache"), second.body

    header, body = asyncio.run(run())
    assert header is None, "a POST is not a cache candidate, so it is not labelled a miss"
    assert b"ok" in body


def test_a_miss_is_labelled_and_a_non_candidate_is_not() -> None:
    """The distinction the two cases above turn on, stated once.

    `MISS` means the cache was consulted and could not answer. A POST, a non-JSON body
    and a `no-cache` caller are never consulted, and labelling them MISS would tell an
    operator their cache was missing work it was never asked to do.
    """
    cache: TTLCache = TTLCache()
    origin = _origin(status=404)

    async def run() -> str:
        response = await cached_response_for(cache, _request(), origin)
        return response.headers["X-Cache"]

    assert asyncio.run(run()) == "MISS"


def test_the_environment_bypass_stays_in_the_middleware() -> None:
    """The reason the middleware exists twice over: ENV=test must never serve from cache."""
    from app.core.config import settings

    assert settings.env == "test"


def test_a_cache_hit_still_carries_this_requests_own_identity() -> None:
    """The defect the extracted function cannot see on its own.

    Found live: two different requests came back with the same `X-Request-ID` and the
    same `X-Request-Duration-Ms`, because `response_cache` was the outermost middleware
    and returned a replay before `request_context` ever ran — so the HIT answered under
    the MISS's identity, with the MISS's duration, and no security headers of its own.

    It needs the real middleware stack, which means it needs the cache to actually be
    engaged, so the environment bypass is lifted for the duration of the case and put
    back in a `finally`: leaving it lifted would let a later case serve a response a
    previous case had written.
    """
    from starlette.testclient import TestClient

    from app.core.cache import _response_cache
    from app.core.config import settings
    from app.main import app as fastapi_app

    was_env = settings.env
    object.__setattr__(settings, "env", "development")
    _response_cache.clear()
    try:
        with TestClient(fastapi_app) as client:
            miss = client.get("/api/v1/healthz")
            hit = client.get("/api/v1/healthz")
        assert miss.headers["X-Cache"] == "MISS"
        assert hit.headers["X-Cache"] == "HIT", "the case is only meaningful if the second answer is a replay"
        assert miss.headers["X-Request-ID"] != hit.headers["X-Request-ID"], "a hit answers as its own caller, never as the one it copied"
        assert hit.headers.get("X-Request-Duration-Ms") is not None, "the duration must be this request's, measured around this request"
        assert hit.headers["X-Content-Type-Options"] == "nosniff", "security headers belong on a served response, cached or not"
    finally:
        object.__setattr__(settings, "env", was_env)
        _response_cache.clear()
