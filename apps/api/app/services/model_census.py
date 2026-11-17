"""The admin console's AI ledger census — aggregates only, never an identity.

The console already prints the high-level model summary (calls and cache share) on its behaviour
panel, and the metrics tier carries spend and recommendations behind the platform's own admin
standing. This door is the third and plainest window into the same `model_calls` ledger: what the
doors actually called, how often the gateway reported the prefix served from its own cache, how
many rows were demo-mode stand-ins, how many failed, what the daily line looks like, and which
features carry which share — all recomputed on every read from the rows, no counters stored.

No row is projected with its `user_id`. Costs are shown in aggregate for the window, rounded to
four decimals; per-feature costs are reported per feature, never per user. Identities never leave
the table, not even in error samples.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models import ModelCall, utc_today

WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 120
FEATURE_TABLE_LIMIT = 24
ERROR_SAMPLE_LIMIT = 6
ERROR_SAMPLE_CHARS = 96


def _median(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


def compute_model_census(session: Session, *, window_days: int = WINDOW_DAYS) -> dict[str, Any]:
    window_days = max(1, min(MAX_WINDOW_DAYS, int(window_days)))
    today = utc_today()
    start = today - timedelta(days=window_days - 1)
    cutoff = datetime.combine(start, time.min, tzinfo=UTC)

    rows = list(session.query(ModelCall).where(ModelCall.created_at >= cutoff).all())

    total = len(rows)
    reported = [r for r in rows if r.cache_reported]
    in_reported = sum(int(r.input_tokens or 0) for r in reported)
    cached_reported = sum(int(r.cached_input_tokens or 0) for r in reported)
    cached_share = (cached_reported / in_reported) if in_reported else 0.0
    failures = sum(1 for r in rows if not r.success)
    demo = sum(1 for r in rows if r.demo_mode)
    est_cost = sum(float(r.estimated_cost_usd or 0.0) for r in rows)
    act_cost = sum(float(r.actual_cost_usd or 0.0) for r in rows)
    median_latency = _median([int(r.latency_ms or 0) for r in rows])
    output_tokens = sum(int(r.output_tokens or 0) for r in rows)

    by_feature: dict[str, dict[str, Any]] = {}
    for r in rows:
        bucket = by_feature.setdefault(
            r.feature,
            {
                "calls": 0,
                "failures": 0,
                "demo_mode": 0,
                "reported": 0,
                "input_reported": 0,
                "cached_reported": 0,
                "output_tokens": 0,
                "latency_ms": [],
                "cost_usd": 0.0,
                "last_called": None,
            },
        )
        bucket["calls"] += 1
        bucket["failures"] += 0 if r.success else 1
        bucket["demo_mode"] += 1 if r.demo_mode else 0
        if r.cache_reported:
            bucket["reported"] += 1
            bucket["input_reported"] += int(r.input_tokens or 0)
            bucket["cached_reported"] += int(r.cached_input_tokens or 0)
        bucket["output_tokens"] += int(r.output_tokens or 0)
        bucket["latency_ms"].append(int(r.latency_ms or 0))
        bucket["cost_usd"] += float(r.actual_cost_usd or 0.0)
        stamp = r.created_at.date().isoformat() if hasattr(r.created_at, "date") else str(r.created_at)[:10]
        if bucket["last_called"] is None or stamp > bucket["last_called"]:
            bucket["last_called"] = stamp

    features = []
    for feature, bucket in by_feature.items():
        share = (bucket["cached_reported"] / bucket["input_reported"]) if bucket["input_reported"] else 0.0
        features.append(
            {
                "feature": feature,
                "calls": bucket["calls"],
                "failures": bucket["failures"],
                "demo_mode_calls": bucket["demo_mode"],
                "cached_share_reported": round(share, 4),
                "reported_rows": bucket["reported"],
                "output_tokens": bucket["output_tokens"],
                "median_latency_ms": _median(bucket["latency_ms"]),
                "cost_usd": round(bucket["cost_usd"], 4),
                "last_called": bucket["last_called"],
            }
        )
    features.sort(key=lambda item: item["calls"], reverse=True)
    features = features[:FEATURE_TABLE_LIMIT]

    by_day: dict[str, dict[str, Any]] = {}
    for offset in range(window_days):
        day_iso = (today - timedelta(days=window_days - 1 - offset)).isoformat()
        by_day[day_iso] = {"date": day_iso, "calls": 0, "failures": 0, "input_tokens": 0, "cached_tokens": 0, "reported_rows": 0, "cost_usd": 0.0}
    for r in rows:
        key = r.created_at.date().isoformat() if hasattr(r.created_at, "date") else str(r.created_at)[:10]
        slot = by_day.get(key)
        if slot is None:
            continue
        slot["calls"] += 1
        slot["failures"] += 0 if r.success else 1
        slot["input_tokens"] += int(r.input_tokens or 0)
        slot["cached_tokens"] += int(r.cached_input_tokens or 0)
        slot["reported_rows"] += 1 if r.cache_reported else 0
        slot["cost_usd"] = round(slot["cost_usd"] + float(r.actual_cost_usd or 0.0), 4)

    error_groups: dict[str, int] = {}
    for r in rows:
        if r.success:
            continue
        sample = (r.error or "unknown").strip().splitlines()[0][:ERROR_SAMPLE_CHARS]
        error_groups[f"{r.feature}: {sample}"] = error_groups.get(f"{r.feature}: {sample}", 0) + 1
    errors = sorted(((k, v) for k, v in error_groups.items()), key=lambda kv: kv[1], reverse=True)[:ERROR_SAMPLE_LIMIT]

    return {
        "available": True,
        "window_days": window_days,
        "totals": {
            "calls": total,
            "failures": failures,
            "failure_rate": round((failures / total) if total else 0.0, 4),
            "demo_mode_calls": demo,
            "demo_mode_share": round((demo / total) if total else 0.0, 4),
            "input_tokens": sum(int(r.input_tokens or 0) for r in rows),
            "output_tokens": output_tokens,
            "cached_input_tokens": sum(int(r.cached_input_tokens or 0) for r in rows),
            "in_cache_reported": in_reported,
            "cached_reported": cached_reported,
            "cached_share_reported": round(cached_share, 4),
            "reported_rows": len(reported),
            "estimated_cost_usd": round(est_cost, 4),
            "actual_cost_usd": round(act_cost, 4),
            "median_latency_ms": median_latency,
        },
        "by_feature": features,
        "daily": list(by_day.values()),
        "errors": [{"sample": k, "count": v} for k, v in errors],
        "note": "aggregates-only; identities are never projected; a row passes cache through the gateway's own report or not at all",
    }


__all__ = ["WINDOW_DAYS", "compute_model_census"]
