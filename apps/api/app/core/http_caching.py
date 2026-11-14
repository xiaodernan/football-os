"""HTTP revalidation for the JSON doors: a validator on every answer, a 304 for the unchanged.

The 60-second server-side response cache keeps a repeat answer out of the database. It does
nothing for the wire: the second caller — a browser, a scraper, a CDN — re-downloads the full
body to be told what it already has. This module is the missing half:

* a **strong validator** (`ETag` = a truncated SHA-256 of the body) on every 200 `application/json`
  `GET` answer, so revalidation is byte-precise — neither a clock nor a size heuristic is asked
  to guess freshness;
* **`Cache-Control: private, max-age=0, must-revalidate`**, which pins revalidation on anyone
  holding this answer — the body is account-shaped, so no shared cache may serve it, and the
  browser must ask before reusing it;
* **304 Not Modified** with the dressed headers kept and the body emptied, when the caller's
  `If-None-Match` matches — the one answer this door exists to make cheap.

`RevalidationMiddleware` is a pure ASGI wrapper, deliberately not a `BaseHTTPMiddleware`:
the crash-answer dresser needs the contextvars `request_context` sets
(`rate_decision_var`, `request_id_var`) to be visible *above* it, and every
`BaseHTTPMiddleware` layer copies and isolates that context. A pure ASGI pass keeps the
chain: server error → gzip → revalidation → `request_context`, one context.

This module never counts a metric. `request_context`, which sits inside the gate, has already
recorded the answer it forwarded (a 200 that this gate converts to a 304 is counted there). The
one outcome it cannot see is the 304 itself, so that outcome alone is counted, once.
"""

from __future__ import annotations

import hashlib
import time
from starlette import status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.request_metrics import record

REVALIDATE_CACHE_CONTROL = "private, max-age=0, must-revalidate"
_ETAG_HEX_CHARS = 32


def compute_etag(body: bytes) -> str:
    """The strong validator: the first 32 hex chars of the SHA-256 of the exact bytes served."""
    return '"' + hashlib.sha256(body).hexdigest()[:_ETAG_HEX_CHARS] + '"'


def is_validatable_json(status_code: int, content_type: str, content_encoding: str | None) -> bool:
    """A JSON answer that may be validated — nothing else carries this door's validator."""
    if status_code != status.HTTP_200_OK:
        return False
    if not content_type.startswith("application/json"):
        return False
    if content_encoding:
        # The gate owns the hash of the bytes it reads; a body already encoded by whoever
        # built it belongs to somebody else's invariant, and a validator over the wrong bytes
        # is worse than no validator.
        return False
    return True


def if_none_match(header_value: str | None, etag: str) -> bool:
    """RFC 7232 weak comparison against the caller's `If-None-Match`, when present.

    Beyond the RFC (a quoted entity-tag, `W/` weak prefix, `*`, comma list), this also
    accepts the bare hex token — the shape a shell strips the quotes into — because the
    comparison stays byte-strict anyway: a 304 is only minted when the bare token equals
    the validator for the exact bytes held; anything else keeps the body.
    """
    if not header_value:
        return False
    for raw in header_value.split(","):
        candidate = raw.strip()
        if candidate == "*":
            return True
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        if candidate == etag or candidate == etag.strip('"'):
            return True
    return False


def _header_map(headers: list[tuple[bytes, bytes]]) -> dict[bytes, bytes]:
    return {key.lower(): value for key, value in headers}


class RevalidationMiddleware:
    """Pure ASGI gate: buffer the answer, tag it, answer 304 when the validator holds."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        started = time.perf_counter()
        if scope.get("type") != "http" or scope.get("method", "GET") != "GET":
            await self.app(scope, receive, send)
            return

        start: Message | None = None
        body = bytearray()

        async def gather(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
            elif message["type"] == "http.response.body":
                body.extend(message.get("body", b""))

        await self.app(scope, receive, gather)
        assert start is not None, "the inner app answered without an http.response.start"

        headers = _header_map(start["headers"])
        etag = compute_etag(bytes(body))
        content_type = headers.get(b"content-type", b"").decode("latin-1")
        content_encoding_header = headers.get(b"content-encoding")
        if is_validatable_json(start["status"], content_type, content_encoding_header.decode("latin-1") if content_encoding_header else None):
            request_headers = {k.lower(): v for k, v in scope.get("headers", [])}
            if_none = request_headers.get(b"if-none-match")
            if if_none_match(if_none.decode("latin-1") if if_none else None, etag):
                record(status.HTTP_304_NOT_MODIFIED, (time.perf_counter() - started) * 1000)
                keep = dict(headers)
                keep.pop(b"content-length", None)
                keep.pop(b"content-encoding", None)
                keep.pop(b"transfer-encoding", None)
                keep[b"etag"] = etag.encode("latin-1")
                keep[b"cache-control"] = REVALIDATE_CACHE_CONTROL.encode("latin-1")
                keep[b"content-length"] = b"0"
                await send({"type": "http.response.start", "status": status.HTTP_304_NOT_MODIFIED, "headers": [(k, v) for k, v in keep.items()]})
                await send({"type": "http.response.body", "body": b""})
                return
            keep = dict(headers)
            keep[b"etag"] = etag.encode("latin-1")
            keep[b"cache-control"] = REVALIDATE_CACHE_CONTROL.encode("latin-1")
            keep[b"content-length"] = str(len(body)).encode("ascii")
            await send({"type": "http.response.start", "status": start["status"], "headers": [(k, v) for k, v in keep.items()]})
            await send({"type": "http.response.body", "body": bytes(body)})
            return

        await send(start)
        await send({"type": "http.response.body", "body": bytes(body)})


__all__ = [
    "REVALIDATE_CACHE_CONTROL",
    "RevalidationMiddleware",
    "compute_etag",
    "if_none_match",
    "is_validatable_json",
]
