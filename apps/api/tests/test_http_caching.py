"""The revalidation gate: the validator on every JSON answer, and the 304 for the unchanged.

The server-side response cache keeps a repeat answer out of the database. It does not keep
it off the wire. This is the door that does: a strong `ETag` on every 200 `application/json`
`GET`, `Cache-Control` that pins revalidation to the caller, and a 304 — zero body bytes,
headers intact — when the caller sends a matching `If-None-Match`.

The tests here drive the extracted gate directly, with a request they built, the way
`test_response_cache.py` drives the response cache. Nothing below starts a server.
"""

from __future__ import annotations

import asyncio
import gzip
import json

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.responses import StreamingResponse as StarletteStreamingResponse

from app.core.compression import VIDEO_PREFIX, CompressionMiddleware
from app.core.http_caching import (
    REVALIDATE_CACHE_CONTROL,
    compute_etag,
    if_none_match,
    is_validatable_json,
    revalidate_if_stale,
)

BIG_JSON = {"items": [{"i": index, "value": "x" * 8} for index in range(300)]}
_ETAG_LENGTH = 34  # 32 hex chars, quote-wrapped


def _request(path: str = "/api/v1/world/search", method: str = "GET", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": "http",
            "path": path,
            "query_string": b"",
            "headers": headers or [],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
        }
    )


def _json_origin(body: dict[str, object] | list[object] | None = None, status_code: int = 200):
    async def call_next(_request: Request):
        return JSONResponse(content=BIG_JSON if body is None else body, status_code=status_code)

    return call_next


class TestTheValidator:
    def test_same_bytes_same_etag(self) -> None:
        assert compute_etag(b'{"a": 1}') == compute_etag(b'{"a": 1}')

    def test_different_bytes_different_etag(self) -> None:
        assert compute_etag(b'{"a": 1}') != compute_etag(b'{"a": 2}')

    def test_quote_wrapped_so_it_is_a_quoted_string(self) -> None:
        etag = compute_etag(b"payload")
        assert etag.startswith('"') and etag.endswith('"')


class TestWhatCarriesTheValidator:
    def test_json_200_is_validatable(self) -> None:
        assert is_validatable_json(JSONResponse(content={})) is True

    def test_json_201_is_not(self) -> None:
        assert is_validatable_json(JSONResponse(content={}, status_code=201)) is False

    def test_json_404_is_not(self) -> None:
        assert is_validatable_json(JSONResponse(content={"detail": {}}, status_code=404)) is False

    def test_plain_text_is_not(self) -> None:
        assert is_validatable_json(PlainTextResponse(content="hello")) is False

    def test_content_encoding_blocks_the_gate(self) -> None:
        response = JSONResponse(content={})
        response.headers["content-encoding"] = "gzip"
        assert is_validatable_json(response) is False


class TestIfNoneMatch:
    def test_star_matches_anything(self) -> None:
        request = _request(headers=[(b"if-none-match", b"*")])
        assert if_none_match(request, '"a"') is True

    def test_exact_match(self) -> None:
        request = _request(headers=[(b"if-none-match", b'"deadbeef"')])
        assert if_none_match(request, '"deadbeef"') is True

    def test_comma_list_match(self) -> None:
        request = _request(headers=[(b"if-none-match", b'"nope", "deadbeef", "nah"')])
        assert if_none_match(request, '"deadbeef"') is True

    def test_weak_etag_matches_weakly(self) -> None:
        """RFC 7232 compares `If-None-Match` weakly, so a `W/` client still validates."""
        request = _request(headers=[(b"if-none-match", b'W/"deadbeef"')])
        assert if_none_match(request, '"deadbeef"') is True

    def test_a_miss_is_a_miss(self) -> None:
        request = _request(headers=[(b"if-none-match", b'"other"')])
        assert if_none_match(request, '"deadbeef"') is False

    def test_unquoted_bare_token_matches_byte_strictly(self) -> None:
        """The shell-stripped quoting a browser is never billed for. Deliberate tolerance."""
        request = _request(headers=[(b"if-none-match", b"deadbeef")])
        assert if_none_match(request, '"deadbeef"') is True
        assert if_none_match(request, '"different"') is False

    def test_no_header_is_no_match(self) -> None:
        assert if_none_match(_request(), '"deadbeef"') is False


class TestTheGate:
    def test_a_first_answer_carries_a_validator_and_private_revalidation(self) -> None:
        async def run() -> tuple[str, str, bytes]:
            response = await revalidate_if_stale(_request(), _json_origin())
            return response.headers["etag"], response.headers["cache-control"], await response_to_bytes(response)

        etag, cache_control, body = asyncio.run(run())
        assert len(etag) == _ETAG_LENGTH
        assert cache_control == REVALIDATE_CACHE_CONTROL
        assert json.loads(body) == BIG_JSON

    def test_a_repeat_gets_304_not_the_body(self) -> None:
        async def run() -> tuple[str, str, bytes, bytes]:
            first = await revalidate_if_stale(_request(), _json_origin())
            first_body = await response_to_bytes(first)
            etag = first.headers["etag"]
            repeat = await revalidate_if_stale(
                _request(headers=[(b"if-none-match", etag.encode("ascii"))]),
                _json_origin(),
            )
            repeat_body = await response_to_bytes(repeat)
            return repeat.status_code, repeat.headers["etag"], repeat_body, first_body

        status_code, etag, repeat_body, first_body = asyncio.run(run())
        assert status_code == 304
        assert repeat_body == b""
        assert etag

    def test_the_304_keeps_the_dressed_headers(self) -> None:
        async def dressed_origin(_request: Request):
            response = JSONResponse(content=BIG_JSON)
            response.headers["x-request-id"] = "req-123"
            response.headers["x-test-security"] = "helmet-on"
            return response

        async def run() -> list[tuple[str, str]]:
            first = await revalidate_if_stale(_request(), dressed_origin)
            etag = first.headers["etag"]
            repeat = await revalidate_if_stale(_request(headers=[(b"if-none-match", etag.encode("ascii"))]), dressed_origin)
            return list(repeat.headers.items())

        headers = dict(asyncio.run(run()))
        assert headers["x-request-id"] == "req-123"
        assert headers["x-test-security"] == "helmet-on"
        assert headers["content-length"] == "0"
        assert headers["cache-control"] == REVALIDATE_CACHE_CONTROL

    def test_a_changed_body_busts_the_validator(self) -> None:
        async def run() -> tuple[str, int]:
            first = await revalidate_if_stale(_request(), _json_origin({"version": 1}))
            etag = first.headers["etag"]
            repeat = await revalidate_if_stale(
                _request(headers=[(b"if-none-match", etag.encode("ascii"))]),
                _json_origin({"version": 2}),
            )
            return repeat.headers["etag"], repeat.status_code

        etag, status_code = asyncio.run(run())
        assert status_code == 200
        assert etag

    def test_a_weak_match_gets_304(self) -> None:
        async def run() -> int:
            first = await revalidate_if_stale(_request(), _json_origin())
            etag = first.headers["etag"]
            repeat = await revalidate_if_stale(
                _request(headers=[(b"if-none-match", f"W/{etag}".encode("ascii"))]),
                _json_origin(),
            )
            return repeat.status_code

        assert asyncio.run(run()) == 304

    def test_posts_are_not_gated(self) -> None:
        async def run() -> tuple[int, str | None]:
            response = await revalidate_if_stale(_request(method="POST"), _json_origin())
            return response.status_code, response.headers.get("etag")

        status_code, etag = asyncio.run(run())
        assert status_code == 200
        assert etag is None

    def test_non_json_answers_are_not_gated(self) -> None:
        async def plain_origin(_request: Request):
            return PlainTextResponse("hi")

        async def run() -> tuple[int, str | None]:
            response = await revalidate_if_stale(_request(), plain_origin)
            return response.status_code, response.headers.get("etag")

        status_code, etag = asyncio.run(run())
        assert status_code == 200
        assert etag is None

    def test_streaming_json_bodies_are_drained_and_revalidatable(self) -> None:
        async def call_next(_request: Request):
            async def body():
                yield json.dumps(BIG_JSON).encode("utf-8")[:200]
                yield json.dumps(BIG_JSON).encode("utf-8")[200:]

            return StarletteStreamingResponse(body(), media_type="application/json")

        async def run() -> tuple[int, bytes]:
            response = await revalidate_if_stale(_request(), call_next)
            return response.status_code, await response_to_bytes(response)

        status_code, body = asyncio.run(run())
        assert status_code == 200
        assert json.loads(body) == BIG_JSON


async def response_to_bytes(response) -> bytes:
    body = getattr(response, "body", None)
    if body is not None:
        return body
    chunks = bytearray()
    async for chunk in response.body_iterator:  # type: ignore[union-attr]
        chunks.extend(chunk)
    return bytes(chunks)


def _asgi_probe(app, path: str, headers: list[tuple[bytes, bytes]]) -> list[dict]:
    messages: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
    }

    asyncio.run(app(scope, receive, send))
    return messages


def _stub_json_app(size_ok: bool = True):
    payload = json.dumps(BIG_JSON if size_ok else {"ok": True}).encode("utf-8")

    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": payload, "more_body": False})

    return app, payload


class TestTheCompressionDoor:
    def test_gzip_when_client_asked_and_body_is_big(self) -> None:
        stub, payload = _stub_json_app(size_ok=True)
        wrapped = CompressionMiddleware(stub, minimum_size=512)  # type: ignore[arg-type]
        messages = _asgi_probe(wrapped, "/api/v1/world/search", [(b"accept-encoding", b"gzip")])
        start, body = messages[0], messages[-1]
        headers = dict(start["headers"])
        assert headers[b"content-encoding"] == b"gzip"
        assert b"accept-encoding" in headers.get(b"vary", b"").lower()
        assert gzip.decompress(body["body"]) == payload

    def test_no_gzip_when_client_did_not_ask(self) -> None:
        stub, payload = _stub_json_app(size_ok=True)
        wrapped = CompressionMiddleware(stub, minimum_size=512)  # type: ignore[arg-type]
        messages = _asgi_probe(wrapped, "/api/v1/world/search", [])
        start, body = messages[0], messages[-1]
        headers = dict(start["headers"])
        assert b"content-encoding" not in headers
        assert body["body"] == payload

    def test_small_json_is_not_worth_the_envelope(self) -> None:
        stub, payload = _stub_json_app(size_ok=False)
        wrapped = CompressionMiddleware(stub, minimum_size=512)  # type: ignore[arg-type]
        messages = _asgi_probe(wrapped, "/api/v1/world/search", [(b"accept-encoding", b"gzip")])
        start, body = messages[0], messages[-1]
        headers = dict(start["headers"])
        assert b"content-encoding" not in headers
        assert body["body"] == payload

    def test_the_video_doors_are_never_compressed(self) -> None:
        stub, payload = _stub_json_app(size_ok=True)
        wrapped = CompressionMiddleware(stub, minimum_size=512)  # type: ignore[arg-type]
        messages = _asgi_probe(wrapped, f"{VIDEO_PREFIX}abc123/file", [(b"accept-encoding", b"gzip")])
        start, body = messages[0], messages[-1]
        headers = dict(start["headers"])
        assert b"content-encoding" not in headers
        assert body["body"] == payload
