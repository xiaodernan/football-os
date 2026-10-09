"""Structured logging configuration (M12 Observability).

Provides JSON-formatted logs with request correlation IDs, standardized fields,
and consistent formatting across the API.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings


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
        # Request ID is set by middleware via contextvars
        try:
            from contextvars import ContextVar

            request_id_var: ContextVar[str] = ContextVar("request_id", default="")
            record.request_id = request_id_var.get()
        except Exception:
            record.request_id = "-"
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
