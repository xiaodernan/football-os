"""The crash answer is the one answer that never reaches the middleware that dresses the rest.

`request_context` in `app/main.py` puts `X-Request-ID`, `X-Request-Duration-Ms`, `X-Content-Type-Options` and
`Referrer-Policy` on every response — but it does so *after* `await call_next(request)`, and Starlette builds
its stack as `[ServerErrorMiddleware] + user_middleware + [ExceptionMiddleware]` (`starlette/applications.py`).
An exception raised by a route propagates out of `request_context` before those lines run, and the 500 that
`ServerErrorMiddleware` renders on the way out is undressed: no correlation id on the wire, no `nosniff`.

That inverts what matters most. A 200 nobody looked at can lose its id quietly; a 500 is the one status a
client quotes back at you, and without `X-Request-ID` there is nothing to quote — the log line and the wire
would have to be matched by timestamp and path alone. The crash must dress itself.
"""

from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from app.core.logging import RequestIDFilter


class _Grab(logging.Handler):
    """Capture the app's records, carrying the same filter the real log handler carries."""

    def __init__(self) -> None:
        super().__init__()
        self.addFilter(RequestIDFilter())
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _app_that_raises() -> object:
    from app.main import create_app

    app = create_app()

    @app.get("/__probe_boom")
    def _boom() -> None:
        raise RuntimeError("deliberate probe failure")

    return app


def test_a_500_answer_carries_the_identity_and_security_headers_every_other_answer_carries() -> None:
    grab = _Grab()
    logger = logging.getLogger("football_os.api")
    logger.addHandler(grab)
    try:
        with TestClient(_app_that_raises(), raise_server_exceptions=False) as test_client:
            response = test_client.get("/__probe_boom")
    finally:
        logger.removeHandler(grab)

    assert response.status_code == 500
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("X-Request-Duration-Ms")

    request_id = response.headers.get("X-Request-ID")
    assert request_id, "a 500 is the status a client quotes back; without an id there is nothing to quote"

    crashed = [record for record in grab.records if "unhandled_error" in record.getMessage()]
    assert crashed, "the crash must be logged"
    assert getattr(crashed[0], "request_id", "") == request_id, "the id on the wire must be the id in the log"
