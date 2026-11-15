"""The upstream LLM-provider failure line must say code, reason and body.

The 2026-11 incident: every wkapi.pro call answered `403 insufficient_user_quota`, the provider collapsed all of that into `HTTPError` in the log line, and the operator spent half an hour chasing network paths that had already answered with the body in ASCII.
"""
from __future__ import annotations

import urllib.error

from app.providers import _http_failure_detail


def _raise_http_error(body: bytes) -> urllib.error.HTTPError:
    import io

    return urllib.error.HTTPError(
        url="https://wkapi.pro/v1/chat/completions",
        code=403,
        msg="Forbidden",
        hdrs={},  # type: ignore[arg-type]
        fp=io.BytesIO(body),
    )


def test_code_and_reason_are_lifted() -> None:
    detail = _http_failure_detail(_raise_http_error(b'{"code":"insufficient_user_quota"}'))
    assert "HTTPError" in detail
    assert "code=403" in detail
    assert "reason=Forbidden" in detail


def test_body_is_sliced_and_included() -> None:
    detail = _http_failure_detail(_raise_http_error(b'{"code":"insufficient_user_quota","request_id":"x"}'))
    assert "insufficient_user_quota" in detail


def test_body_length_is_capped() -> None:
    detail = _http_failure_detail(_raise_http_error(b"x" * 5000))
    assert len(detail) < 500


def test_url_error_renders_without_body_without_crashing() -> None:
    import urllib.error

    detail = _http_failure_detail(urllib.error.URLError("connection refused"))
    assert "URLError" in detail
