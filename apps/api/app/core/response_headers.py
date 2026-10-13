"""The headers every answer this API sends carries, in one place.

`request_context` in `app/main.py` adds them after `await call_next(request)`, and being the outermost user
middleware it sees every response — except one. Starlette builds its stack as
`[ServerErrorMiddleware] + user_middleware + [ExceptionMiddleware]` (see `starlette/applications.py`), so an
exception raised inside a route propagates *out* of `request_context` before those lines run, and the 500 that
`ServerErrorMiddleware` renders on the way out reaches the client undressed: no `X-Request-ID`, no `nosniff`.

That is the wrong response to lose them on. A 500 is the one status a client quotes back at you; without an id
there is nothing to quote, and the `unhandled_error` line in the log would have to be matched to the wire by
timestamp and path alone. So the handler that renders a crash dresses its own answer from this same function,
and the header set has exactly one definition instead of two that can drift.

Two callers, and no third is possible: `request_context` for everything that flows normally, and
`install_error_handlers`'s `_unhandled` for the exception that never comes back to it.
"""

from __future__ import annotations

import time

from starlette.responses import Response

from app.core.logging import request_id_var, request_started_var


def dress_response(response: Response) -> None:
    """Put the identity and security headers on `response`, in place."""
    request_id = request_id_var.get()
    if request_id:
        # Only when one exists. An empty `X-Request-ID` is worse than none: it looks set, and no log line
        # carries it, so a client quoting it would be quoting an id this process never recorded.
        response.headers["X-Request-ID"] = request_id
    started = request_started_var.get()
    if started is not None:
        response.headers["X-Request-Duration-Ms"] = str(int((time.perf_counter() - started) * 1000))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
