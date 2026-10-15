"""Metrics and observability endpoints (spec §58-§60).

Exposes platform health metrics including request latency, error rates, database performance,
AI provider usage, cost optimisation advice, and cache statistics. All endpoints are auth-gated to
prevent information leakage while allowing administrators to monitor system health.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import get_cache_stats
from app.core.db import get_db
from app.core.redis_cache import get_redis_cache
from app.core.request_metrics import snapshot as request_metrics_snapshot
from app.core.runtime import uptime_seconds
from app.core.security import current_user
from app.models import ModelCall, User, VideoAsset
from app.services.cost_advisor import DEFAULT_WINDOW_DAYS
from app.services.cost_advisor import recommend as cost_recommend
from app.services.latency_profile import profile as latency_profile

router = APIRouter(prefix="/metrics", tags=["metrics"])


class SystemMetricsResponse(BaseModel):
    uptime_seconds: float
    request_count: int
    error_count: int
    avg_latency_ms: float
    p95_latency_ms: float | None
    active_users_today: int
    total_users: int


class DatabaseMetricsResponse(BaseModel):
    total_model_calls: int
    model_calls_today: int
    total_video_assets: int
    avg_model_call_latency_ms: float
    success_rate: float


class ProviderMetricsResponse(BaseModel):
    total_calls: int
    calls_by_provider: dict[str, int]
    total_cost_usd: float
    cost_today_usd: float
    avg_latency_ms: float
    demo_mode_percentage: float


@router.get("/system", response_model=SystemMetricsResponse)
def system_metrics(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> SystemMetricsResponse:
    """Report system-level metrics including uptime, request counts, and latency."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Count users
    total_users = int(db.scalar(select(func.count(User.id))) or 0)
    # How many accounts were active today, which is what the row's name says. This used to count
    # DISTINCT ModelCall.user_id, which answers a different question - how many accounts bought an AI
    # call - so a user who logged in and spent the day on training, tactics or boards was active today and
    # counted as nobody. `last_login_at` is the column that records what the row promises, and it is
    # written on both ways in (login, and registration, which issues a token).
    active_today = int(db.scalar(select(func.count(User.id)).where(User.last_login_at >= today_start)) or 0)

    # The four rows that describe the traffic, which counted the AI ledger until now: `request_count` was
    # `COUNT(ModelCall.id)`, `error_count` the failed subset of the same table, and both latencies came out
    # of it too. That is a different question with no name of its own — a door answering 404 all day moved
    # none of these figures, and `/metrics/providers` already answers "how much AI did we buy" over the
    # ledger. What callers waited, and how much of it failed, is what a system row is for.
    served = request_metrics_snapshot()

    return SystemMetricsResponse(
        uptime_seconds=round(uptime_seconds(), 2),
        request_count=served["request_count"],
        error_count=served["error_count"],
        avg_latency_ms=served["avg_latency_ms"],
        p95_latency_ms=served["p95_latency_ms"],
        active_users_today=active_today,
        total_users=total_users,
    )


@router.get("/database", response_model=DatabaseMetricsResponse)
def database_metrics(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> DatabaseMetricsResponse:
    """Report database-level metrics including table sizes and query performance."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_calls = int(db.scalar(select(func.count(ModelCall.id))) or 0)
    calls_today = int(db.scalar(select(func.count(ModelCall.id)).where(ModelCall.created_at >= today_start)) or 0)
    total_videos = int(db.scalar(select(func.count(VideoAsset.id))) or 0)
    avg_latency = float(db.scalar(select(func.avg(ModelCall.latency_ms))) or 0.0)
    successful = int(db.scalar(select(func.count(ModelCall.id)).where(ModelCall.success.is_(True))) or 0)
    success_rate = successful / total_calls if total_calls > 0 else 0.0

    return DatabaseMetricsResponse(
        total_model_calls=total_calls,
        model_calls_today=calls_today,
        total_video_assets=total_videos,
        avg_model_call_latency_ms=round(avg_latency, 2),
        success_rate=round(success_rate, 4),
    )


@router.get("/providers", response_model=ProviderMetricsResponse)
def provider_metrics(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> ProviderMetricsResponse:
    """Report AI provider usage metrics including costs and latency."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Total calls
    total_calls = int(db.scalar(select(func.count(ModelCall.id))) or 0)

    # Calls by provider
    provider_counts = db.execute(select(ModelCall.provider, func.count(ModelCall.id)).group_by(ModelCall.provider)).all()
    calls_by_provider = {str(provider): int(count) for provider, count in provider_counts}

    # Costs
    total_cost = float(db.scalar(select(func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0))) or 0.0)
    cost_today = float(db.scalar(select(func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0)).where(ModelCall.created_at >= today_start)) or 0.0)

    # Latency
    avg_latency = float(db.scalar(select(func.avg(ModelCall.latency_ms))) or 0.0)

    # Demo mode percentage
    demo_calls = int(db.scalar(select(func.count(ModelCall.id)).where(ModelCall.demo_mode.is_(True))) or 0)
    demo_pct = (demo_calls / total_calls * 100) if total_calls > 0 else 0.0

    return ProviderMetricsResponse(
        total_calls=total_calls,
        calls_by_provider=calls_by_provider,
        total_cost_usd=round(total_cost, 4),
        cost_today_usd=round(cost_today, 4),
        avg_latency_ms=round(avg_latency, 2),
        demo_mode_percentage=round(demo_pct, 2),
    )


@router.get("/cost-optimisation")
def cost_optimisation(
    days: int = Query(DEFAULT_WINDOW_DAYS, ge=1, le=365),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Where the AI budget went and what a cheaper call would have been (spec §46, §76).

    Reads the model-call ledger over a stated window and answers four breakdowns (by feature, by
    model, reasoning share, demo share) with every figure recomputed on the request. The
    recommendations name the arithmetic that produced them, and the answer says plainly that it is an
    advisor, not an enforcer: nothing here changes which provider a door calls (§45 owns that).
    """
    return cost_recommend(db, days=days)


@router.get("/latency")
def latency_profile_endpoint(
    days: int = Query(DEFAULT_WINDOW_DAYS, ge=1, le=365),
    feature: str | None = Query(None, max_length=60),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Latency percentiles over the model-call ledger, per feature or overall (spec §58).

    The percentiles are nearest-rank over the newest rows the profile read, which is the same figure
    on SQLite and PostgreSQL — SQL has `percentile_cont` on one engine and nothing on the other. The
    answer prints the sample size and whether the sample is full, so a percentile over 20 rows is never
    mistaken for one over 2,000.
    """
    return latency_profile(db, days=days, feature=feature)


@router.get("/cache")
def cache_stats(
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Cache statistics for every tier the process runs: the two in-memory caches and Redis.

    Redis is reported whether or not it is serving. `get_redis_cache()` is a lazy singleton
    that attempts the connection once and then remembers the answer, so this door costs a
    failed connect at most once per process on a host with no usable instance — and what it
    returns there is the fact an operator needs: the tier exists, and it is not serving.
    """
    stats: dict[str, Any] = get_cache_stats()
    stats["redis"] = get_redis_cache().get_stats()
    return stats
