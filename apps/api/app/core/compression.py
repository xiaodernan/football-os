"""GZip for the JSON doors — honest about what it costs the wire.

Starlette's `GZipMiddleware` decides what to compress from the *shape* of the ASGI messages,
not from the size of the answer. This app's user middleware is `BaseHTTPMiddleware`, which
pumps every answer through a memory stream and re-emits it as more than one body message —
so the "don't compress under N bytes" branch of starlette never triggers, a 22-byte JSON
went out as a 42-byte gzip stream, and the `minimum_size` parameter was a lie in this
topology.

This middleware measures first, then decides. It buffers the whole answer — the exact
trade `cached_response_for` already makes sixty seconds later, which drains every body it
caches — redirects nothing, and picks between two byte-exact sends:

* total body under `minimum_size` bytes → the wire keeps the plain bytes; `Vary: Accept-Encoding`
  still goes on (a cache must know the answer was negotiated);
* otherwise → gzip at `compresslevel`, `Content-Encoding: gzip`, a fresh `Content-Length`,
  `Vary: Accept-Encoding` — both RFC-correct and chunk-free.

Paths in `skip_prefixes` (the video doors) and anything already carrying a
`Content-Encoding` pass through untouched, and non-http scopes are none of its business.
The posture is stated, not implied: one bounded buffer the size of one answer, no
streaming pretense this stack cannot honour.
"""

from __future__ import annotations

import gzip

from starlette.types import ASGIApp, Message, Receive, Scope, Send

VIDEO_PREFIX = "/api/v1/video/"
_SKIP = (VIDEO_PREFIX,)


class CompressionMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        minimum_size: int = 512,
        compresslevel: int = 6,
        skip_prefixes: tuple[str, ...] = _SKIP,
    ) -> None:
        self.app = app
        self.minimum_size = minimum_size
        self.compresslevel = compresslevel
        self.skip_prefixes = skip_prefixes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        if any(path.startswith(prefix) for prefix in self.skip_prefixes):
            await self.app(scope, receive, send)
            return
        accept = ",".join(
            value.decode("latin-1") for key, value in scope.get("headers", []) if key.lower() == b"accept-encoding"
        )
        if "gzip" not in accept:
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

        payload = bytes(body)
        headers = [(k, v) for k, v in start["headers"]]
        header_map = {k.lower(): value for k, value in headers}
        already_encoded = b"content-encoding" in header_map

        if not already_encoded and len(payload) < self.minimum_size:
            headers.append((b"vary", b"Accept-Encoding"))
            await send({"type": "http.response.start", "status": start["status"], "headers": headers})
            await send({"type": "http.response.body", "body": payload})
            return

        if already_encoded:
            await send(start)
            await send({"type": "http.response.body", "body": payload})
            return

        compressed = gzip.compress(payload, compresslevel=self.compresslevel, mtime=0)
        keep_headers = [(k, v) for k, v in headers if k.lower() not in (b"content-length", b"vary")]
        keep_headers.append((b"content-encoding", b"gzip"))
        keep_headers.append((b"content-length", str(len(compressed)).encode("ascii")))
        keep_headers.append((b"vary", b"Accept-Encoding"))
        await send({"type": "http.response.start", "status": start["status"], "headers": keep_headers})
        await send({"type": "http.response.body", "body": compressed})
