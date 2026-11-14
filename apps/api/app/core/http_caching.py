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

This module never counts a metric. `request_context`, which sits inside the gate, has already
recorded the answer it forwarded (a 200 that this gate converts to a 304 is counted there
visibly and the mismatch is named here). The one outcome it cannot see is the 304 itself, so
that outcome alone is counted, once.

Kept out of the middleware body so a test can ask the question directly, with a request it
built, rather than starting a server to find out what a client is told. The middleware in
`app.main` holds nothing but the registration.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Awaitable, Callable

from starlette import status
from starlette.requests import Request
from starlette.responses import Response

from app.core.request_metrics import record

REVALIDATE_CACHE_CONTROL = "private, max-age=0, must-revalidate"
_ETAG_HEX_CHARS = 32

Origin = Callable[[Request], Awaitable[Response]]


def compute_etag(body: bytes) -> str:
    """The strong validator: the first 32 hex chars of the SHA-256 of the exact bytes served."""
    return '"' + hashlib.sha256(body).hexdigest()[:_ETAG_HEX_CHARS] + '"'


def is_validatable_json(response: Response) -> bool:
    """A JSON answer that may be validated — nothing else carries this door's validator."""
    if response.status_code != status.HTTP_200_OK:
        return False
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        return False
    if response.headers.get("content-encoding"):
        # The gate owns the hash of the bytes it reads; a body already encoded by whoever
        # built it belongs to somebody else's invariant, and a validator over the wrong bytes
        # is worse than no validator.
        return False
    return True


def if_none_match(request: Request, etag: str) -> bool:
    """RFC 7232 weak comparison against the caller's `If-None-Match`, when present.

    Beyond the RFC (a quoted entity-tag, `W/` weak prefix, `*`, comma list), this also
    accepts the bare hex token — the shape a shell strips the quotes into — because the
    comparison stays byte-strict anyway: a 304 is only minted when the bare token equals
    the validator for the exact bytes held; anything else keeps the body.
    """
    header = request.headers.get("if-none-match")
    if not header:
        return False
    for raw in header.split(","):
        candidate = raw.strip()
        if candidate == "*":
            return True
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        if candidate == etag or candidate == etag.strip('"'):
            return True
    return False


def _clone_headers(response: Response, drop: tuple[str, ...] = ()) -> dict[str, str]:
    """The answer's headers, keys lower-cased (as the wire wants) minus the ones being re-decided."""
    re_decided = ("content-length", "etag", "cache-control") + drop
    out: dict[str, str] = {}
    for key, value in response.headers.items():
        lowered = key.lower()
        if lowered in re_decided:
            continue
        out[lowered] = value
    return out


def _strip_for_not_modified(response: Response, etag: str) -> Response:
    """The 304: the dressed answer's headers kept, the body emptied, nothing recomputed."""
    headers = _clone_headers(response, drop=("content-encoding", "transfer-encoding"))
    headers["etag"] = etag
    headers["cache-control"] = REVALIDATE_CACHE_CONTROL
    headers["content-length"] = "0"
    return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)


def _with_validator(response: Response, body: bytes, etag: str) -> Response:
    """The same answer, re-tagged: bytes identical, headers extend the original, never replace it."""
    headers = _clone_headers(response)
    headers["etag"] = etag
    headers["cache-control"] = REVALIDATE_CACHE_CONTROL
    headers["content-length"] = str(len(body))
    return Response(
        status_code=response.status_code,
        headers=headers,
        content=body,
    )


async def _read_body(response: Response) -> bytes:
    """Drain whichever shape the answered body arrived in."""
    iterator = getattr(response, "body_iterator", None)
    if iterator is None:
        return getattr(response, "body", b"")
    chunks: list[bytes] = []
    async for chunk in iterator:
        chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode("utf-8"))
    return b"".join(chunks)


async def revalidate_if_stale(request: Request, call_next: Origin) -> Response:
    """The gate: hash a JSON 200 GET answer, honour `If-None-Match`, re-tag the body otherwise."""
    started = time.perf_counter()
    response = await call_next(request)
    if request.method != "GET" or not is_validatable_json(response):
        return response
    body = await _read_body(response)
    etag = compute_etag(body)
    if if_none_match(request, etag):
        record(status.HTTP_304_NOT_MODIFIED, (time.perf_counter() - started) * 1000)
        return _strip_for_not_modified(response, etag)
    return _with_validator(response, body, etag)
