"""The span store: a trace backend that needs no collector (M12 observability).

OpenTelemetry was wired with an OTLP exporter, so a span went wherever a collector was listening
and nowhere at all on a host that runs none — which is every host this project measures on. The
verification document said so: "no span has reached a real backend".

This module is that backend. It is an ordinary OpenTelemetry *exporter*, so the SDK's
`BatchSpanProcessor` calls it from its own thread: the request path never pays for the write, and
a database that is down cannot slow a request down. The exporter writes each finished span into
`request_spans`, and `GET /api/v1/traces/{trace_id}` reads a request's spans back.

Two rules the exporter holds to:

* **A store failure is never a request failure.** The exporter catches everything and returns a
  failure result; the SDK's batch processor then drops the batch. A trace backend that can take
  the API down is worse than no trace backend.
* **The store is bounded.** Every export also deletes the spans older than the retention window,
  so a long-running instance does not accumulate traces forever. The window is seven days, which
  is longer than any incident review reaches back.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.models import RequestSpan

logger = logging.getLogger(__name__)

#: How long a span is kept before the exporter prunes it.
RETENTION = timedelta(days=7)


def _as_utc(value: int | float | None) -> datetime:
    """A span's nanosecond timestamp as a UTC datetime."""
    if not value:
        return datetime.now(UTC)
    return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC)


def _span_values(span: ReadableSpan) -> dict[str, Any]:
    """The row values for one finished span."""
    context = span.get_span_context()
    # `span.parent` is a SpanContext, not an id: the parent's own span id is what the tree needs.
    parent = span.parent
    start = _as_utc(span.start_time)
    end = _as_utc(span.end_time)
    duration_ms = int(max(0, (end - start).total_seconds() * 1000))
    status = getattr(span.status, "status_code", None)
    return {
        "trace_id": f"{context.trace_id:032x}" if context else "",
        "span_id": f"{context.span_id:016x}" if context else "",
        "parent_span_id": f"{parent.span_id:016x}" if parent and parent.span_id else None,
        "name": (span.name or "")[:200],
        "kind": str(getattr(span.kind, "name", span.kind))[:40],
        "status": str(getattr(status, "name", status or "unset"))[:40],
        "start_time": start,
        "end_time": end,
        "duration_ms": duration_ms,
        "attributes_json": {str(key): value for key, value in dict(span.attributes or {}).items()},
    }


class SpanStoreExporter(SpanExporter):
    """Writes finished spans into `request_spans`."""

    def __init__(self, session_factory: sessionmaker[Session], *, retention: timedelta = RETENTION) -> None:
        self._session_factory = session_factory
        self._retention = retention

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Store one batch of spans. Never raises: the SDK's batch processor drops a failed batch."""
        if not spans:
            return SpanExportResult.SUCCESS
        try:
            with self._session_factory() as db:
                for span in spans:
                    db.add(RequestSpan(**_span_values(span)))
                db.commit()
                self._prune(db)
                db.commit()
        except Exception as exc:  # noqa: BLE001 - a store failure must not reach the request
            logger.warning("the span store could not write a batch: %s", exc)
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def _prune(self, db: Session) -> None:
        """Delete the spans older than the retention window."""
        cutoff = datetime.now(UTC) - self._retention
        db.execute(delete(RequestSpan).where(RequestSpan.start_time < cutoff))

    def shutdown(self) -> None:
        """Nothing to close: the exporter opens a session per batch and closes it again."""
        return None


def read_trace(db: Session, trace_id: str) -> list[RequestSpan]:
    """Every span of one trace, oldest first."""
    rows = db.scalars(select(RequestSpan).where(RequestSpan.trace_id == trace_id).order_by(RequestSpan.start_time)).all()
    return list(rows)


#: What the route summary groups and how its figures are derived, published beside them.
ROUTE_SUMMARY_FORMULA: Final = (
    "SERVER spans started in the window, grouped by the route the span names (attributes.http.route, else its name); "
    "a span counts as an error when its status is ERROR or its attributes.http_status_code is 500 or more; "
    "error rate is errors ÷ the group's count; p50/p95 are nearest-rank over the group's duration_ms"
)


def _nearest_rank(sorted_values: list[int], percentile: int) -> int:
    """The nearest-rank percentile of an ascending list (0 for an empty one)."""
    if not sorted_values:
        return 0
    rank = max(1, math.ceil(percentile / 100 * len(sorted_values)))
    return sorted_values[min(rank, len(sorted_values)) - 1]


def route_summary(db: Session, *, window_minutes: int = 60, limit: int = 50_000) -> dict[str, Any]:
    """Slowest routes and error rate over the recent SERVER spans — an operator's read, not a counter.

    The store keeps seven days; the window bounds what this reads, and `limit` bounds the scan so a
    busy instance cannot make the dashboard the thing that falls over. `truncated` says when the scan
    hit the cap, because a summary that silently read only part of the window is a wrong summary.
    """
    since = datetime.now(UTC) - timedelta(minutes=window_minutes)
    rows = list(
        db.scalars(
            select(RequestSpan)
            .where(RequestSpan.kind == "SERVER", RequestSpan.start_time >= since)
            .order_by(RequestSpan.start_time.desc())
            .limit(limit + 1)
        ).all()
    )
    truncated = len(rows) > limit
    rows = rows[:limit]
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        attributes = row.attributes_json if isinstance(row.attributes_json, dict) else {}
        route = str(attributes.get("http.route") or row.name or "")
        slot = groups.setdefault(route, {"route": route, "count": 0, "errors": 0, "durations": []})
        slot["count"] += 1
        status_code = attributes.get("http.status_code")
        if str(row.status or "").upper() == "ERROR" or (isinstance(status_code, int) and status_code >= 500):
            slot["errors"] += 1
        slot["durations"].append(int(row.duration_ms or 0))
    routes: list[dict[str, Any]] = []
    for slot in groups.values():
        durations = sorted(slot["durations"])
        routes.append(
            {
                "route": slot["route"],
                "count": slot["count"],
                "errors": slot["errors"],
                "error_rate": round(slot["errors"] / slot["count"], 4) if slot["count"] else 0.0,
                "p50_ms": _nearest_rank(durations, 50),
                "p95_ms": _nearest_rank(durations, 95),
                "max_ms": durations[-1] if durations else 0,
            }
        )
    routes.sort(key=lambda item: (-item["p95_ms"], -item["count"], item["route"]))
    return {
        "window_minutes": window_minutes,
        "since": since.isoformat(),
        "spans_scanned": len(rows),
        "truncated": truncated,
        "routes": routes,
        "formula": ROUTE_SUMMARY_FORMULA,
        "note": "read from the span store over the window, recomputed on every request; no counter is stored",
    }
