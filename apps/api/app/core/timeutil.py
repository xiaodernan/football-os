"""SQLite returns naive datetimes, PostgreSQL returns aware ones.

Any Python-side comparison of a stored timestamp must go through these helpers so
the same code is correct on both dialects (ADR-002).
"""

from __future__ import annotations

from datetime import UTC, datetime


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def now_utc() -> datetime:
    return datetime.now(UTC)


def is_expired(value: datetime) -> bool:
    return as_utc(value) <= now_utc()
