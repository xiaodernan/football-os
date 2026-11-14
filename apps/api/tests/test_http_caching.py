"""The revalidation gate: the validator on every JSON answer, and the 304 for the unchanged.

The server-side response cache keeps a repeat answer out of the database. It does not keep
it off the wire. This is the door that does: a strong `ETag` on every 200 `application/json`
`GET`, `Cache-Control` that pins revalidation to the caller, and a 304 — zero body bytes,
headers intact — when the caller sends a matching `If-None-Match`.

`RevalidationMiddleware` is a pure ASGI wrapper (a `BaseHTTPMiddleware` layer would copy the
contextvars `request_context` sets, and the crash answer would lose them), so the cases drive
it as ASGI: a stub origin app, a scope, a drained `send` list, and bytes in between.
"""

from __future__ import annotations

import gzip
import json

from starlette.types import Message

from app.core.compression import VIDEO_PREFIX, CompressionMiddleware
from app.core.http_caching import (
    REVALIDATE_CACHE_CONTROL,
    RevalidationMiddleware,
    compute_etag,
    if_none_match,
    is_validatable_json,
)

BIG_JSON: dict[str, object] = {"items": [{"i": index, "value": "x" * 8} for index in range(300)]}
_ETAG_LENGTH = 34  # 32 hex chars, quote-wrapped


def _scope(
    path: str = "/api/v1/world/search",
    method: str = "GET",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict:
    return {
        "type": "http",
        "method": method,
        "scheme": "http",
        "path": path,
        "query_string": b"",
        "headers": headers or [],
        "client": ("127.0.0.1", 1),
        "server": ("testserver", 80),
    }


def _stub_origin(body: bytes, status_code: int = 200, content_type: bytes = b"application/json", extra_headers: list[tuple[bytes, bytes]] | None = None):
    headers: list[tuple[bytes, bytes]] = [(b"content-type", content_type), (b"content-length", str(len(body)).encode("ascii"))]
    headers.extend(extra_headers or [])

    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status_code, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    return app


def _probe(app, path: str = "/api/v1/world/search", method: str = "GET", headers: list[tuple[bytes, bytes]] | None = None):
    messages: list[Message] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    scope = _scope(path=path, method=method, headers=headers)

    import asyncio

    asyncio.run(app(scope, receive, send))
    start = next(m for m in messages if m["type"] == "http.response.start")
    out_body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    response_headers = {k.lower(): v for k, v in start["headers"]}
    return start["status"], response_headers, out_body


def _json_probe(**kwargs) -> tuple[int, dict, bytes]:
    origin = _stub_origin(json.dumps(BIG_JSON).encode("utf-8"), **kwargs)
    return _probe(RevalidationMiddleware(origin))  # type: ignore[arg-type]


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
        assert is_validatable_json(200, "application/json", None) is True

    def test_json_201_is_not(self) -> None:
        assert is_validatable_json(201, "application/json", None) is False

    def test_json_404_is_not(self) -> None:
        assert is_validatable_json(404, "application/json", None) is False

    def test_plain_text_is_not(self) -> None:
        assert is_validatable_json(200, "text/plain", None) is False

    def test_content_encoding_blocks_the_gate(self) -> None:
        assert is_validatable_json(200, "application/json", "gzip") is False


class TestIfNoneMatch:
    def test_star_matches_anything(self) -> None:
        assert if_none_match("*", '"a"') is True

    def test_exact_match(self) -> None:
        assert if_none_match('"deadbeef"', '"deadbeef"') is True

    def test_comma_list_match(self) -> None:
        assert if_none_match('"nope", "deadbeef", "nah"', '"deadbeef"') is True

    def test_weak_etag_matches_weakly(self) -> None:
        assert if_none_match('W/"deadbeef"', '"deadbeef"') is True

    def test_a_miss_is_a_miss(self) -> None:
        assert if_none_match('"other"', '"deadbeef"') is False

    def test_no_header_is_no_match(self) -> None:
        assert if_none_match(None, '"deadbeef"') is False

    def test_unquoted_bare_token_matches_byte_strictly(self) -> None:
        """The shell-stripped quoting a browser is never billed for. Deliberate tolerance."""
        assert if_none_match("deadbeef", '"deadbeef"') is True
        assert if_none_match("deadbeef", '"different"') is False


class TestTheGate:
    def test_a_first_answer_carries_a_validator_and_private_revalidation(self) -> None:
        status_code, headers, body = _json_probe()
        assert status_code == 200
        assert len(headers[b"etag"]) == _ETAG_LENGTH
        assert headers[b"cache-control"] == REVALIDATE_CACHE_CONTROL.encode("latin-1")
        assert json.loads(body) == BIG_JSON

    def test_a_repeat_gets_304_not_the_body(self) -> None:
        _, headers, _ = _json_probe()
        etag = headers[b"etag"]
        status_code, headers, body = _probe(
            RevalidationMiddleware(_stub_origin(json.dumps(BIG_JSON).encode("utf-8"))),
            headers=[(b"if-none-match", etag)],
        )  # type: ignore[arg-type]
        assert status_code == 304
        assert body == b""
        assert headers[b"etag"] == etag
        assert headers[b"content-length"] == b"0"

    def test_the_304_keeps_the_dressed_headers(self) -> None:
        origin = _stub_origin(
            json.dumps(BIG_JSON).encode("utf-8"),
            extra_headers=[(b"x-request-id", b"req-123"), (b"x-test-security", b"helmet-on")],
        )
        _, headers, _ = _probe(RevalidationMiddleware(origin))  # type: ignore[arg-type]
        etag = headers[b"etag"]
        origin = _stub_origin(
            json.dumps(BIG_JSON).encode("utf-8"),
            extra_headers=[(b"x-request-id", b"req-456"), (b"x-test-security", b"helmet-on")],
        )
        status_code, repeat_headers, body = _probe(
            RevalidationMiddleware(origin),
            headers=[(b"if-none-match", etag)],
        )  # type: ignore[arg-type]
        assert status_code == 304
        assert repeat_headers[b"x-request-id"] == b"req-456"
        assert repeat_headers[b"x-test-security"] == b"helmet-on"
        assert repeat_headers[b"cache-control"] == REVALIDATE_CACHE_CONTROL.encode("latin-1")
        assert body == b""

    def test_a_changed_body_busts_the_validator(self) -> None:
        _, headers, _ = _probe(
            RevalidationMiddleware(_stub_origin(json.dumps({"version": 1}).encode("utf-8"))),
        )  # type: ignore[arg-type]
        etag = headers[b"etag"]
        status_code, repeat_headers, body = _probe(
            RevalidationMiddleware(_stub_origin(json.dumps({"version": 2}).encode("utf-8"))),
            headers=[(b"if-none-match", etag)],
        )  # type: ignore[arg-type]
        assert status_code == 200
        assert json.loads(body) == {"version": 2}
        assert repeat_headers[b"etag"] != etag

    def test_a_weak_match_gets_304(self) -> None:
        _, headers, _ = _json_probe()
        etag = headers[b"etag"]
        status_code, _, body = _probe(
            RevalidationMiddleware(_stub_origin(json.dumps(BIG_JSON).encode("utf-8"))),
            headers=[(b"if-none-match", b"W/" + etag)],
        )  # type: ignore[arg-type]
        assert status_code == 304
        assert body == b""

    def test_posts_are_not_gated(self) -> None:
        status_code, headers, body = _probe(
            RevalidationMiddleware(_stub_origin(json.dumps(BIG_JSON).encode("utf-8"))),
            method="POST",
        )  # type: ignore[arg-type]
        assert status_code == 200
        assert b"etag" not in headers
        assert json.loads(body) == BIG_JSON

    def test_non_json_answers_are_not_gated(self) -> None:
        status_code, headers, body = _probe(
            RevalidationMiddleware(_stub_origin(b"hi", content_type=b"text/plain")),
        )  # type: ignore[arg-type]
        assert status_code == 200
        assert b"etag" not in headers
        assert body == b"hi"

    def test_a_pre_encoded_body_is_not_double_stamped(self) -> None:
        status_code, headers, body = _probe(
            RevalidationMiddleware(_stub_origin(gzip.compress(b'{"a":1}'), extra_headers=[(b"content-encoding", b"gzip")])),
        )  # type: ignore[arg-type]
        assert status_code == 200
        assert b"etag" not in headers
        assert gzip.decompress(body) == b'{"a":1}'

    def test_streaming_json_bodies_are_drained_and_revalidatable(self) -> None:
        chunks = [json.dumps(BIG_JSON).encode("utf-8")[:200], json.dumps(BIG_JSON).encode("utf-8")[200:]]

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
            for chunk in chunks:
                await send({"type": "http.response.body", "body": chunk, "more_body": True})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        status_code, headers, body = _probe(RevalidationMiddleware(app))
        assert status_code == 200
        assert json.loads(body) == BIG_JSON
        assert b"etag" in headers


class TestTheCompressionDoor:
    def test_gzip_when_client_asked_and_body_is_big(self) -> None:
        stub = _stub_origin(json.dumps(BIG_JSON).encode("utf-8"))
        wrapped = CompressionMiddleware(stub, minimum_size=512)  # type: ignore[arg-type]
        status_code, headers, body = _probe(wrapped, headers=[(b"accept-encoding", b"gzip")])
        assert status_code == 200
        assert headers[b"content-encoding"] == b"gzip"
        assert b"accept-encoding" in headers.get(b"vary", b"").lower()
        assert gzip.decompress(body) == json.dumps(BIG_JSON).encode("utf-8")

    def test_no_gzip_when_client_did_not_ask(self) -> None:
        payload = json.dumps(BIG_JSON).encode("utf-8")
        stub = _stub_origin(payload)
        wrapped = CompressionMiddleware(stub, minimum_size=512)  # type: ignore[arg-type]
        status_code, headers, body = _probe(wrapped)
        assert headers.get(b"content-encoding") is None
        assert body == payload

    def test_small_json_is_not_worth_the_envelope(self) -> None:
        payload = b'{"ok": true}'
        stub = _stub_origin(payload)
        wrapped = CompressionMiddleware(stub, minimum_size=512)  # type: ignore[arg-type]
        _, headers, body = _probe(wrapped, headers=[(b"accept-encoding", b"gzip")])
        assert headers.get(b"content-encoding") is None
        assert body == payload

    def test_the_video_doors_are_never_compressed(self) -> None:
        payload = json.dumps(BIG_JSON).encode("utf-8")
        stub = _stub_origin(payload)
        wrapped = CompressionMiddleware(stub, minimum_size=512)  # type: ignore[arg-type]
        _, headers, body = _probe(wrapped, path=f"{VIDEO_PREFIX}abc123/file", headers=[(b"accept-encoding", b"gzip")])
        assert headers.get(b"content-encoding") is None
        assert body == payload
