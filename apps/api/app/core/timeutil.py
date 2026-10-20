"""SQLite returns naive datetimes, PostgreSQL returns aware ones.

Any Python-side comparison of a stored timestamp must go through these helpers so
the same code is correct on both dialects (ADR-002).

`utc_midnight` is here for a second reason, found by measuring rather than by reading. Three
queries built a window boundary as `str(date.today() - timedelta(days=N))` and compared a
`DateTime(timezone=True)` column against that string. On PostgreSQL the string is cast to
`timestamptz` *in the session's TimeZone*, so the same code answers "the last N days" with a
boundary at midnight UTC on one host and 04:00 UTC on another, and a different set of rows is
inside the window than the author wrote. The provided helper `_today_start` in
`app/services/progression.py` already showed the intended answer was UTC; these sites had gone
around it.
"""

from __future__ import annotations

from datetime import UTC, date, datetime


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def now_utc() -> datetime:
    return datetime.now(UTC)


def is_expired(value: datetime) -> bool:
    return as_utc(value) <= now_utc()


def utc_midnight(day: date) -> datetime:
    """The start of `day` as a UTC-aware datetime: an unambiguous window boundary.

    Bound as a datetime the value reaches the engine as a timestamptz in UTC, on every dialect,
    whatever the session's timezone. Bound as `str(day)` it reaches PostgreSQL as text that
    PostgreSQL reinterprets in its own `TimeZone`, and the window slides with the host.
    """
    return datetime(day.year, day.month, day.day, tzinfo=UTC)
