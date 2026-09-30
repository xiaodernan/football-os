"""Uniform error *answer* + handlers (spec §74): stack traces never reach clients, and neither does a second shape.

One shape, one place: every refusal this API answers — a door's `HTTPException(…, detail={"code", …})`, a
service's `ClubRefusal.to_dict()`, or one of the four handlers below — puts its code at `detail.code`. The
handlers used to wrap theirs at the top level as `{"error": …}`, which is a shape no client of this project
reads: `normalizeError` in `apps/web/lib/api.ts` looks for `payload.detail`, and without it the user got the
fallback string "Request failed" while the API had already produced the field-and-rule list behind it.
"""

from __future__ import annotations

import json as _json
import logging
from collections.abc import Iterable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("football_os.api")


def _serialisable(details: Any) -> Any:
    """Pydantic error contexts can carry exception objects; keep the payload JSON-safe."""
    try:
        return _json.loads(_json.dumps(details, default=str))
    except (TypeError, ValueError):
        return str(details)


def _rejected(details: Iterable[Any]) -> list[dict[str, Any]]:
    """Each error as *which field, what rule* — and never the value that failed it.

    Pydantic v2 puts the offending input into every entry (`input`, and `ctx` for a custom validator), so the
    default 422 body repeats back whatever a client typed. For most tiers that is only unkind. §40's academy
    tier is the case that makes it a bug: its whole promise is that a home address or a telephone number is
    held nowhere, and the door that refuses such a field would be the one that prints it — into the response,
    into whatever logged the response, and into the browser history of the guardian who typed it. A page can
    still say which box was wrong and why, which is all a validation error is for.
    """
    return [{"type": item.get("type"), "loc": list(item.get("loc") or []), "msg": item.get("msg")} for item in details]


def _answer(code: str, message: str, details: Any = None) -> dict[str, Any]:
    """The one body shape a refusal has project-wide: the code sits at `detail.code`, where every door puts it.

    §51's doors all answer `{"detail": {"code", "message", …}}`. The four handlers below answered
    `{"error": {…}}` — a second shape for the same kind of answer — and the product's only client reads the
    first one: `normalizeError` in `apps/web/lib/api.ts` takes `payload.detail` when the key is present and
    otherwise falls back to the whole payload, so a schema refusal arrived as `code: "error"`,
    `message: "Request failed"` with the field list dropped. That drop is not cosmetic: `_rejected` exists to
    say *which field broke which rule* while never echoing the value that failed (§40's minors' data promise),
    and the page that renders `result.error.details` was receiving nothing. Wrapping here rather than at each
    handler is what makes the shape impossible to half-apply.
    """
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = _serialisable(details)
    return {"detail": body}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(_answer("validation_error", "Request validation failed", _rejected(exc.errors())), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(ValidationError)
    async def _pydantic(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(_answer("validation_error", "Request validation failed", _rejected(exc.errors())), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(IntegrityError)
    async def _integrity(_request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("integrity_error %s", type(exc.orig).__name__)
        return JSONResponse(_answer("conflict", "That record conflicts with existing data"), status_code=status.HTTP_409_CONFLICT)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error path=%s", request.url.path)
        return JSONResponse(_answer("internal_error", "Unexpected server error"), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
