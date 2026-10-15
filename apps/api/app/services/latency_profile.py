"""Latency percentiles over the ledger's own timings (spec §58-§60, M12 Performance).

`/metrics/system` answered `p95_latency_ms: None` with a comment saying a percentile would need
computing. SQL has `percentile_cont` on PostgreSQL and nothing equivalent on SQLite, and this project
runs both, so the honest way to answer the same figure on both engines is to read a bounded sample of
the newest rows and compute it here.

The sample is stated in the answer rather than hidden: `sample_size` is how many rows it read,
`sampled_from` is how many rows exist in the window, and a percentile over a sample is an estimate, so
the field `p95_latency_ms_estimated` says so. The reader gets the truth about the arithmetic instead of
a number that looks exact.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Float, Integer, case, func, select
from sqlalchemy.orm import Session

from app.core.percentile import nearest_rank
from app.models import ModelCall

#: How many of the newest rows to read for the percentile. Large enough that a p95 over the sample is
#: within a few percent of the whole window, small enough that the query stays cheap on both engines.
SAMPLE_SIZE: int = 2000

#: The window the profile reads by default.
DEFAULT_WINDOW_DAYS: int = 30


def profile(db: Session, *, days: int = DEFAULT_WINDOW_DAYS, feature: str | None = None) -> dict[str, Any]:
    """Latency percentiles over the newest `SAMPLE_SIZE` calls in the window."""
    since = (datetime.now(UTC) - timedelta(days=max(1, days))).replace(microsecond=0)

    conditions = [ModelCall.created_at >= since]
    if feature:
        conditions.append(ModelCall.feature == feature)

    totals = db.execute(
        select(
            func.count(ModelCall.id).cast(Integer),
            func.coalesce(func.sum(case((ModelCall.success.is_(False), 1), else_=0)), 0).cast(Integer),
            func.coalesce(func.avg(ModelCall.latency_ms), 0.0).cast(Float),
        ).where(*conditions)
    ).one()
    rows_in_window = int(totals[0] or 0)
    failures = int(totals[1] or 0)
    average = float(totals[2] or 0.0)

    sample = [float(value) for value in db.execute(select(ModelCall.latency_ms).where(*conditions).order_by(ModelCall.created_at.desc(), ModelCall.id.desc()).limit(SAMPLE_SIZE)).scalars()]
    sample.sort()

    return {
        "window_days": max(1, days),
        "feature": feature,
        "sample_size": len(sample),
        "sampled_from": rows_in_window,
        "sample_is_newest": len(sample) >= SAMPLE_SIZE,
        "p50_latency_ms": round(nearest_rank(sample, 0.50), 2),
        "p95_latency_ms": round(nearest_rank(sample, 0.95), 2),
        "p99_latency_ms": round(nearest_rank(sample, 0.99), 2),
        "max_latency_ms": round(sample[-1], 2) if sample else 0.0,
        "avg_latency_ms": round(average, 2),
        "failure_count": failures,
        "limitation": ("percentiles are nearest-rank over the newest rows in the window, not an exact window-wide " "figure; the sample size and whether it is full are both in the answer"),
    }


__all__ = ["DEFAULT_WINDOW_DAYS", "SAMPLE_SIZE", "profile"]
