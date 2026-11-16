"""Behavioural aggregates for the admin console — every figure read on the fly.

The admin console shows user behaviour without storing a counter anywhere: sessions,
bounces, dwell, funnels and the trend line are all computed from the `page_views` rows on
the read. Seeded rows (`seeded=true`) and live beacon rows (`seeded=false`) are counted
separately in `source_note` so the console can label every number it prints.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ModelCall, PageView, utc_today

WINDOW_DAYS = 90


def _median(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


def _linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    """(slope, intercept, r_squared) of y ~ x — least squares, no dependencies."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0), 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    if sxx == 0:
        return 0.0, mean_y, 0.0
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys, strict=True))
    r_squared = 1.0 - (ss_res / ss_tot if ss_tot else 0.0)
    return slope, intercept, max(0.0, min(1.0, r_squared))


def compute_behavior(session: Session, *, window_days: int = WINDOW_DAYS) -> dict[str, Any]:
    window_days = max(7, min(365, window_days))
    today = utc_today()
    start = today - timedelta(days=window_days - 1)
    cutoff = datetime.combine(start, time.min, tzinfo=UTC)

    rows = list(
        session.execute(
            select(PageView).where(PageView.created_at >= cutoff).order_by(PageView.created_at.asc())
        ).scalars()
    )
    seeded_views = sum(1 for row in rows if row.seeded)
    real_views = len(rows) - seeded_views

    sessions: dict[str, list[PageView]] = {}
    for row in rows:
        sessions.setdefault(row.session_ref, []).append(row)
    unique_sessions = len(sessions)

    total_views = len(rows)
    bounces = sum(1 for row in rows if row.bounced)
    bounce_rate = (bounces / total_views) if total_views else 0.0
    dwell_all = [row.dwell_ms for row in rows]
    median_dwell = _median(dwell_all)

    # Per-day series
    by_day: dict[str, list[PageView]] = {}
    for row in rows:
        key = row.created_at.date().isoformat() if hasattr(row.created_at, "date") else str(row.created_at)[:10]
        by_day.setdefault(key, []).append(row)

    daily: list[dict[str, Any]] = []
    day = start
    while day <= today:
        rows_for_day = by_day.get(day.isoformat(), [])
        day_bounces = sum(1 for row in rows_for_day if row.bounced)
        daily.append(
            {
                "date": day.isoformat(),
                "views": len(rows_for_day),
                "sessions": len({row.session_ref for row in rows_for_day}),
                "bounce_rate": (day_bounces / len(rows_for_day)) if rows_for_day else 0.0,
            }
        )
        day += timedelta(days=1)

    # Per-page roll-up (top 12 by views)
    by_page: dict[str, list[PageView]] = {}
    for row in rows:
        by_page.setdefault(row.path, []).append(row)
    pages: list[dict[str, Any]] = []
    for path, page_rows in sorted(by_page.items(), key=lambda kv: len(kv[1]), reverse=True)[:12]:
        page_bounces = sum(1 for row in page_rows if row.bounced)
        dwells = [row.dwell_ms for row in page_rows]
        pages.append(
            {
                "path": path,
                "views": len(page_rows),
                "sessions": len({row.session_ref for row in page_rows}),
                "bounce_rate": (page_bounces / len(page_rows)) if page_rows else 0.0,
                "median_dwell_ms": _median(dwells),
            }
        )

    # Funnels: share of sessions that reached B after A, in kickoff order.
    def funnel(_from: str, to: str) -> float:
        reached_from = [ref for ref, ref_rows in sessions.items() if any(row.path == _from for row in ref_rows)]
        if not reached_from:
            return 0.0
        advanced = 0
        for ref in reached_from:
            ref_rows = sessions[ref]
            paths_in_order = [row.path for row in ref_rows]
            if _from in paths_in_order and to in paths_in_order:
                if paths_in_order.index(to) > paths_in_order.index(_from):
                    advanced += 1
        return advanced / len(reached_from)

    funnels = [
        {"id": "home_to_world", "from": "/", "to": "/world", "rate": funnel("/", "/world")},
        {"id": "tutorial_to_manual", "from": "/tutorial", "to": "/manual", "rate": funnel("/tutorial", "/manual")},
        {"id": "world_to_realbook", "from": "/world", "to": "/world/real-book", "rate": funnel("/world", "/world/real-book")},
    ]

    # Trend: least squares over the daily session series
    xs = [float(i) for i, _ in enumerate(daily)]
    ys = [float(entry["sessions"]) for entry in daily]
    slope, intercept, r_squared = _linear_regression(xs, ys)
    forecast = [max(0.0, slope * (len(daily) + i) + intercept) for i in range(14)]

    # Recommendations — rule-based reads, labelled as suggestions by the console
    recs: list[dict[str, Any]] = []

    def _gv(obj: Any, key: str, default: Any = 0) -> Any:
        """One hand to read object-typed row dicts."""
        return obj.get(key, default) if isinstance(obj, dict) else default

    worst = max(
        (page for page in pages if _gv(page, "views", 0) >= 20),
        key=lambda page: float(_gv(page, "bounce_rate", 0.0)) * int(_gv(page, "views", 0)),
        default=None,
    )
    if worst is not None and float(_gv(worst, "bounce_rate", 0.0)) >= 0.55 and int(_gv(worst, "views", 0)) >= 20:
        recs.append({"kind": "high_bounce_page", "path": str(_gv(worst, "path", "")), "value": round(float(_gv(worst, "bounce_rate", 0.0)), 4)})
    dowdy = [page for page in pages if int(_gv(page, "views", 0)) >= 20 and int(_gv(page, "median_dwell_ms", 0)) < 4000]
    if dowdy:
        recs.append({"kind": "low_dwell_page", "path": str(_gv(dowdy[0], "path", "")), "value": int(_gv(dowdy[0], "median_dwell_ms", 0))})
    tutorial = next((entry for entry in funnels if _gv(entry, "id") == "tutorial_to_manual"), None)
    if tutorial is not None and float(_gv(tutorial, "rate", 0.0)) < 0.25:
        recs.append({"kind": "tutorial_drop", "value": round(float(_gv(tutorial, "rate", 0.0)), 4)})
    if abs(slope) < 0.5:
        recs.append({"kind": "forecast_flat", "value": round(slope, 4)})
    else:
        recs.append({"kind": "forecast_rising" if slope > 0 else "forecast_falling", "value": round(slope, 4)})
    top = next((page for page in pages if int(_gv(page, "views", 0)) >= 100 and float(_gv(page, "bounce_rate", 1.0)) <= 0.3), None)
    if top is not None:
        recs.append({"kind": "strong_page", "path": str(_gv(top, "path", ""))})

    # Model traffic: the window's own ledger reads back into the console
    reported = session.execute(
        select(
            func.count(ModelCall.id),
            func.coalesce(func.sum(ModelCall.input_tokens), 0),
            func.coalesce(func.sum(ModelCall.cached_input_tokens), 0),
        ).where(ModelCall.created_at >= cutoff, ModelCall.cache_reported.is_(True))
    ).one()
    all_calls = int(session.scalar(select(func.count(ModelCall.id)).where(ModelCall.created_at >= cutoff)) or 0)
    input_tokens = int(reported[1] or 0)
    cached_tokens = int(reported[2] or 0)
    cached_share = (cached_tokens / input_tokens) if input_tokens else 0.0

    return {
        "available": True,
        "window_days": window_days,
        "source_note": {
            "seeded_views": seeded_views,
            "real_views": real_views,
            "seeded_sessions": len({row.session_ref for row in rows if row.seeded}),
            "real_sessions": len({row.session_ref for row in rows if not row.seeded}),
        },
        "totals": {
            "sessions": unique_sessions,
            "views": total_views,
            "unique_paths": len(by_page),
            "bounce_rate": round(bounce_rate, 4),
            "median_dwell_ms": median_dwell,
        },
        "daily": daily,
        "pages": pages,
        "funnels": funnels,
        "forecast": {
            "method": "least_squares",
            "horizon_days": 14,
            "slope_per_day": round(slope, 4),
            "r_squared": round(r_squared, 4),
            "projected_sessions": [round(v) for v in forecast],
        },
        "recommendations": recs,
        "model": {
            "calls_in_window": all_calls,
            "input_tokens_reported": input_tokens,
            "cached_input_tokens": cached_tokens,
            "cached_share": round(cached_share, 4),
        },
    }


__all__ = ["compute_behavior"]
