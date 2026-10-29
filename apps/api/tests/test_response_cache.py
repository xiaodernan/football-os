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
from app.main import cached_response_for, caller_identity, response_cache_key

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


def test_the_key_carries_the_path_the_query_and_the_origin() -> None:
    assert response_cache_key("/api/v1/healthz", "") == "http:%2Fapi%2Fv1%2Fhealthz:::"
    assert response_cache_key("/x", "a=1") != response_cache_key("/x", "a=2"), "a different query is a different answer"
    assert response_cache_key("/x", "") != response_cache_key("/y", ""), "a different path is a different answer"
    assert response_cache_key("/x", "", "http://localhost:3210") != response_cache_key("/x", "", "http://127.0.0.1:3210"), "a different origin is a different answer"
    assert response_cache_key("/a:b", "c") != response_cache_key("/a", "b:c"), "encoding each part is what keeps the separators unambiguous"


def test_the_key_also_carries_the_caller() -> None:
    """The fourth component, and the one whose absence leaked one account's answer to another."""
    first = response_cache_key("/api/v1/players", "", "", "caller-a")
    second = response_cache_key("/api/v1/players", "", "", "caller-b")
    public = response_cache_key("/api/v1/players", "", "")
    assert first != second, "two callers must not share a key"
    assert first != public, "a private answer must not sit under the public key"


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


def _authed_request(method: str = "GET", token: bytes = b"Bearer token-a") -> Request:
    return _request(method=method, headers=[(b"authorization", token)])


def _counting_origin(body: dict[str, object] | None = None, status: int = 200) -> tuple[Origin, list[int]]:
    """An origin that reports how many times its GET was reached — a POST is a write, not a read."""
    calls: list[int] = []

    async def call_next(request: Request) -> Response:
        if request.method == "GET":
            calls.append(len(calls) + 1)
        return JSONResponse(content=body if body is not None else {"read": max(len(calls), 1)}, status_code=status)

    return call_next, calls


def test_a_successful_write_drops_the_callers_cached_answers() -> None:
    cache: TTLCache = TTLCache()
    origin, calls = _counting_origin()

    async def run() -> tuple[str, str, int]:
        await cached_response_for(cache, _authed_request(), origin)
        assert len(calls) == 1
        await cached_response_for(cache, _authed_request(method="POST"), origin)
        third = await cached_response_for(cache, _authed_request(), origin)
        return third.headers["X-Cache"], third.body.decode(), len(calls)

    header, body, reached = asyncio.run(run())
    assert header == "MISS", "the write's own caller may not be served the answer the write made false"
    assert reached == 2, f"the read after the write must reach the origin again, reached {reached}"
    assert '"read":2' in body


def test_a_failed_write_leaves_the_callers_cache_warm() -> None:
    cache: TTLCache = TTLCache()
    origin, calls = _counting_origin()

    async def run() -> str:
        await cached_response_for(cache, _authed_request(), origin)
        await cached_response_for(cache, _authed_request(method="POST"), _origin(status=500))
        replayed = await cached_response_for(cache, _authed_request(), origin)
        return replayed.headers["X-Cache"]

    header = asyncio.run(run())
    assert header == "HIT", "a write that changed nothing may not drop answers that are still true"


def test_another_callers_answers_survive_one_callers_write() -> None:
    cache: TTLCache = TTLCache()
    origin, calls = _counting_origin()

    async def run() -> tuple[str, str]:
        await cached_response_for(cache, _authed_request(token=b"Bearer token-a"), origin)
        await cached_response_for(cache, _authed_request(token=b"Bearer token-b"), origin)
        assert len(calls) == 2
        await cached_response_for(cache, _authed_request(method="POST", token=b"Bearer token-a"), origin)
        a_again = await cached_response_for(cache, _authed_request(token=b"Bearer token-a"), origin)
        b_again = await cached_response_for(cache, _authed_request(token=b"Bearer token-b"), origin)
        return a_again.headers["X-Cache"], b_again.headers["X-Cache"]

    a_header, b_header = asyncio.run(run())
    assert a_header == "MISS", "the writer's own next read goes to the origin"
    assert b_header == "HIT", "another caller's answer is not false just because someone else wrote"


def test_an_anonymous_write_drops_nothing() -> None:
    cache: TTLCache = TTLCache()
    origin, calls = _counting_origin()

    async def run() -> str:
        await cached_response_for(cache, _request(), origin)
        await cached_response_for(cache, _request(method="POST"), origin)
        replayed = await cached_response_for(cache, _request(), origin)
        return replayed.headers["X-Cache"]

    header = asyncio.run(run())
    assert header == "HIT", "an anonymous caller's future reads run under a fresh identity, so there is nothing to drop"
    assert len(calls) == 1


def test_drop_identity_deletes_only_the_entries_that_name_the_caller() -> None:
    cache: TTLCache = TTLCache()
    key_a = response_cache_key("/api/v1/careers/x", "", identity=caller_identity("Bearer token-a"))
    key_b = response_cache_key("/api/v1/careers/x", "", identity=caller_identity("Bearer token-b"))
    key_anon = response_cache_key("/api/v1/world", "")
    cache.set(key_a, {"answer": "a"})
    cache.set(key_b, {"answer": "b"})
    cache.set(key_anon, {"answer": "anon"})

    assert cache.drop_identity(caller_identity("Bearer token-a")) == 1
    assert cache.get(key_b) == {"answer": "b"}, "another caller's entry survives"
    assert cache.get(key_anon) == {"answer": "anon"}, "an anonymous entry survives a named caller's drop"
    assert cache.drop_identity(caller_identity("Bearer token-b")) == 1
    assert cache.drop_identity("") == 1, 'the empty identity names the anonymous keys, whose keys end in ":"'
    assert cache.get(key_anon) is None


def test_drop_public_path_sweeps_every_anonymous_origin_and_no_credentialed_answer() -> None:
    """§24's closed link: the answer names nobody, so the sweep has to name the path instead.

    A public answer can sit under one key per allowlisted `Origin`, and a closed link must close for all of
    them. A credentialed answer for the same path shares the prefix but carries an identity after the origin,
    and a write about one link must never take another caller's answer with it.
    """
    cache: TTLCache = TTLCache()
    path = "/api/v1/scout/shared/" + "a" * 32
    origin_a = response_cache_key(path, "", "http://localhost:3210")
    origin_b = response_cache_key(path, "", "http://127.0.0.1:3210")
    plain = response_cache_key(path, "")
    credentialed = response_cache_key(path, "", "http://localhost:3210", caller_identity("Bearer token-a"))
    other_path = response_cache_key("/api/v1/scout/shared/" + "b" * 32, "")
    for key in (origin_a, origin_b, plain, credentialed, other_path):
        cache.set(key, {"answer": key})

    assert cache.drop_public_path(path) == 3, "both origin keys and the originless one are the same public answer"
    assert cache.get(origin_a) is None
    assert cache.get(origin_b) is None
    assert cache.get(plain) is None
    assert cache.get(credentialed) == {"answer": credentialed}, "a credentialed answer is not a public one"
    assert cache.get(other_path) == {"answer": other_path}, "another token's answer survives"


def test_a_miss_is_labelled_and_a_non_candidate_is_not() -> None:
    """The distinction the two cases above turn on, stated once.

    `MISS` means the cache was consulted and could not answer. A POST and a `no-cache` caller are never
    consulted, and labelling them MISS would tell an operator their cache was missing work it was never
    asked to do.
    """
    cache: TTLCache = TTLCache()
    origin = _origin(status=404)

    async def run() -> str:
        response = await cached_response_for(cache, _request(), origin)
        return response.headers["X-Cache"]

    assert asyncio.run(run()) == "MISS"


def test_which_requests_the_cache_is_actually_consulted_for() -> None:
    """Which of these three the cache looks up, measured on its own counters rather than argued about.

    The case above says a non-JSON body is never consulted, and the code does consult it. The lookup has
    to run before the body's content type is known — the response does not exist until the origin has
    been called — so for a non-JSON GET the cache is asked, and answers nothing. `MISS` is therefore the
    truthful label for one: it means "consulted and could not answer", and it was. A POST and a `no-cache`
    caller are known to be non-candidates before any of that happens, so neither counter moves.
    """
    cache: TTLCache = TTLCache()

    async def run(origin: Origin, request: Request) -> None:
        await cached_response_for(cache, request, origin)

    async def drive() -> tuple[int, int, int, int, int, int]:
        # A POST: refused on the method, before the cache is touched at all.
        post = cache.get_stats()["misses"]
        await run(_origin(), _request(method="POST"))
        post_after = cache.get_stats()["misses"]

        # A GET a caller marked `no-cache`: also refused before the cache is touched.
        want_fresh = cache.get_stats()["misses"]
        await run(_origin(), _request(headers=[(b"cache-control", b"no-cache")]))
        fresh_after = cache.get_stats()["misses"]

        # A non-JSON 200: only its answer's content type rules it out, and that arrives after the lookup.
        plain = cache.get_stats()["misses"]
        await run(_origin(content_type="text"), _request())
        plain_after = cache.get_stats()["misses"]

        return post, post_after, want_fresh, fresh_after, plain, plain_after

    post, post_after, want_fresh, fresh_after, plain, plain_after = asyncio.run(drive())

    assert post == post_after, "a POST is not a cache candidate before the cache is asked"
    assert want_fresh == fresh_after, "a `no-cache` caller asked for a fresh answer, not a warm one"
    assert plain_after == plain + 1, "a non-JSON GET is consulted; only its content type rules it out"


def _origin_echoing_acao() -> Origin:
    """What `CORSMiddleware` does to a response, reduced to the part that varies.

    `Access-Control-Allow-Origin` is a function of the request's `Origin`, so a response
    carrying it is not the same answer for every caller. That is the whole reason this
    shape exists: a cache keyed only on path and query cannot tell the two apart.
    """

    async def call_next(request: Request) -> Response:
        response = JSONResponse(content={"status": "ok"})
        origin = request.headers.get("origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
        return response

    return call_next


def _with_origin(origin: str) -> list[tuple[bytes, bytes]]:
    return [(b"origin", origin.encode())]


def test_a_second_allowlisted_origin_gets_its_own_answer_not_the_first_ones() -> None:
    """The defect found live, in the smallest form that shows it.

    With two allowlisted origins — which is this project's own configuration, `localhost:3210`
    and `127.0.0.1:3210` — the first caller to fetch a path warmed the cache and every later
    caller was served the first caller's `Access-Control-Allow-Origin`. A browser compares
    that header against *its* origin and rejects the mismatch, so the second allowlisted
    origin silently stopped working the moment a path was warm.
    """
    cache: TTLCache = TTLCache()
    origin = _origin_echoing_acao()

    async def run() -> tuple[str, str, str]:
        first = await cached_response_for(cache, _request(headers=_with_origin("http://localhost:3210")), origin)
        second = await cached_response_for(cache, _request(headers=_with_origin("http://127.0.0.1:3210")), origin)
        return first.headers["X-Cache"], second.headers["X-Cache"], second.headers.get("Access-Control-Allow-Origin", "")

    first_header, second_header, acao = asyncio.run(run())
    assert first_header == "MISS"
    assert second_header == "MISS", "a different origin is a different question, so it must not be a hit"
    assert acao == "http://127.0.0.1:3210", "the answer must name the origin that asked"


def test_the_same_origin_still_gets_a_hit() -> None:
    """The other half: keying on `Origin` must not simply disable the cache."""
    cache: TTLCache = TTLCache()
    origin = _origin_echoing_acao()

    async def run() -> tuple[str, str]:
        first = await cached_response_for(cache, _request(headers=_with_origin("http://localhost:3210")), origin)
        second = await cached_response_for(cache, _request(headers=_with_origin("http://localhost:3210")), origin)
        return first.headers["X-Cache"], second.headers["X-Cache"]

    assert asyncio.run(run()) == ("MISS", "HIT")


def test_an_origin_header_does_not_leak_into_an_uncached_caller() -> None:
    """A caller that sends no `Origin` must not be answered with someone else's."""
    cache: TTLCache = TTLCache()
    origin = _origin_echoing_acao()

    async def run() -> tuple[str, str | None]:
        await cached_response_for(cache, _request(headers=_with_origin("http://localhost:3210")), origin)
        plain = await cached_response_for(cache, _request(), origin)
        return plain.headers["X-Cache"], plain.headers.get("Access-Control-Allow-Origin")

    header, acao = asyncio.run(run())
    assert header == "MISS"
    assert acao is None, "a same-origin caller never sent an origin and must not be handed one"


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
