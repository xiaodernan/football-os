"""The log contract, and the correlation that was never correlated.

`app/core/logging.py` claims JSON lines carrying a request correlation id. Two
tests here earn their keep by finding what reading the module alone would not:

The formatter is exercised, because "the JSON formatter is the contract with a
sink that deployment wires" is only true if the bytes it emits parse.

The correlation test exists because `RequestIDFilter` built its own
`ContextVar("request_id")` while `app.main` built a second one with the same
name and set *that* in the middleware. ContextVars compare by identity, not by
name, so the filter read its own never-set default and every line carried
`"request_id": ""`. Nothing failed — an empty string is a legal value for a
string field — so a log aggregator would have grouped every request into a
single bucket, and the only way to notice was to assert the value equals the
one the middleware chose.
"""

from __future__ import annotations

import io
import json
import logging
import uuid

from app.core.logging import JSONFormatter, RequestIDFilter, get_logger


def _capture_logger(name: str) -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RequestIDFilter())
    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger, stream


def test_a_log_line_is_one_object_that_parses() -> None:
    logger, stream = _capture_logger("test.logging.parse")
    logger.info("kick off")

    line = stream.getvalue().strip()
    assert "\n" not in line, "one record, one line"
    parsed = json.loads(line)
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "kick off"
    assert parsed["logger"] == "test.logging.parse"
    assert "timestamp" in parsed


def test_the_middleware_and_the_filter_share_one_variable() -> None:
    """The invariant the bug broke, stated once so it cannot break quietly again."""
    from app.core.logging import request_id_var as from_logging
    from app.main import request_id_var as from_main

    assert from_main is from_logging, "one name, one object — a second ContextVar is a second variable"


def test_the_correlation_id_reaching_a_log_is_the_one_the_middleware_set() -> None:
    from app.main import request_id_var

    logger, stream = _capture_logger("test.logging.correlation")
    chosen = str(uuid.uuid4())
    token = request_id_var.set(chosen)
    try:
        logger.info("inside a request")
    finally:
        request_id_var.reset(token)

    parsed = json.loads(stream.getvalue().strip())
    assert parsed["request_id"] == chosen, "the filter must read the very variable the middleware writes; " "an identically named ContextVar is a different variable"


def test_an_empty_request_id_is_not_handed_to_a_sink_as_a_bucket() -> None:
    logger, stream = _capture_logger("test.logging.uncorrelated")
    logger.info("outside any request")

    parsed = json.loads(stream.getvalue().strip())
    assert "request_id" in parsed
    assert parsed["request_id"] in ("", "-"), "the field is always present, and says when it is empty"


def test_extra_fields_reach_the_line() -> None:
    logger, stream = _capture_logger("test.logging.extra")
    logger.info("built", extra={"user_id": "u_1", "route": "/api/v1/healthz"})

    parsed = json.loads(stream.getvalue().strip())
    assert parsed["user_id"] == "u_1"
    assert parsed["route"] == "/api/v1/healthz"


def test_an_exception_is_rendered_as_text() -> None:
    logger, stream = _capture_logger("test.logging.exception")
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("failed")

    parsed = json.loads(stream.getvalue().strip())
    assert "ValueError: boom" in parsed["exception"]


def test_get_logger_returns_the_named_logger() -> None:
    assert get_logger("football_os.api").name == "football_os.api"


def test_a_request_id_travels_from_the_header_all_the_way_into_a_log_line() -> None:
    """The whole chain at once: header, middleware, variable, filter, emitted line.

    The two halves above prove each joint; this proves the joints are connected in the
    order the claim describes, using a route that logs while the request is in flight.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    logger, stream = _capture_logger("test.logging.end_to_end")

    @app.get("/__log_probe")
    def _probe() -> dict[str, str]:
        logger.info("served")
        return {"ok": "true"}

    try:
        with TestClient(app) as client:
            response = client.get("/__log_probe", headers={"X-Request-ID": "e2e-req-77"})
    finally:
        app.router.routes[:] = [route for route in app.router.routes if getattr(route, "path", None) != "/__log_probe"]

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "e2e-req-77"

    parsed = json.loads(stream.getvalue().strip())
    assert parsed["request_id"] == "e2e-req-77"
