"""Structured logging configuration (M12 Observability).

Provides JSON-formatted logs with request correlation IDs, standardized fields,
and consistent formatting across the API.
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

# The one request-id variable. It lives here rather than in `main` because the filter that
# reads it lives here, and `main` already imports this module — so the direction of the
# import stays acyclic while both ends share a single object.
#
# ContextVars are identified by object, not by name: two variables created with the same
# name are two variables, and setting one leaves the other at its default. This module
# previously built its own `ContextVar("request_id")` here in the filter, so the middleware
# in `main` set a different variable and every log line carried `"request_id": ""`. That is
# a legal value for a string field, so nothing failed — an aggregator grouping on it would
# simply have put every request in one bucket.
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# When the request began, as `time.perf_counter()`, so the duration header can be built by whoever finally
# dresses the response. Normally that is `request_context`; on a 500 it cannot be, because the exception
# left that middleware before it reached the lines that add the headers, and the handler that renders the
# crash sits outside every user middleware. Keeping the start time here rather than as a local is what lets
# the crash answer report a real duration instead of none. `None` means no request has begun here yet.
request_started_var: ContextVar[float | None] = ContextVar("request_started", default=None)


class JSONFormatter(logging.Formatter):
    """JSON log formatter with standardized fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "asctime",
                "exc_info",
                "exc_text",
                "stack_info",
            }:
                if not key.startswith("_"):
                    log_obj[key] = value

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, ensure_ascii=False)


class RequestIDFilter(logging.Filter):
    """Add request ID to log records from context."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Read the shared variable, and only that one. A ContextVar constructed here would
        # share the name and none of the state.
        record.request_id = request_id_var.get()
        return True


def configure_logging() -> None:
    """Configure structured logging for the application."""
    root_logger = logging.getLogger()

    # Clear existing handlers
    root_logger.handlers.clear()

    # Set level from settings
    level = getattr(logging, getattr(settings, "log_level", "INFO").upper(), logging.INFO)
    root_logger.setLevel(level)

    # Console handler with JSON formatting
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RequestIDFilter())
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the standard configuration."""
    return logging.getLogger(name)
