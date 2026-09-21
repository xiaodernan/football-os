"""Uniform error envelope + handlers (spec §74): stack traces never reach clients."""

from __future__ import annotations

import json as _json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
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


def _envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = _serialisable(details)
    return body


class AppError(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, details: Any = None) -> None:
        super().__init__(status_code=status_code, detail=_envelope(code, message, details))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(_envelope("validation_error", "Request validation failed", exc.errors()), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(ValidationError)
    async def _pydantic(_request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(_envelope("validation_error", "Request validation failed", exc.errors()), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(IntegrityError)
    async def _integrity(_request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("integrity_error %s", type(exc.orig).__name__)
        return JSONResponse(_envelope("conflict", "That record conflicts with existing data"), status_code=status.HTTP_409_CONFLICT)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error path=%s", request.url.path)
        return JSONResponse(_envelope("internal_error", "Unexpected server error"), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
