"""Metrics and observability endpoint (spec §58-§60).

Exposes platform health metrics including request latency, error rates, database performance,
AI provider usage, and resource utilization. All endpoints are auth-gated to prevent information
leakage while allowing administrators to monitor system health.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user
from app.models import ModelCall, User, VideoAsset

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
    active_today = int(
        db.scalar(
            select(func.count(func.distinct(ModelCall.user_id))).where(ModelCall.created_at >= today_start)
        ) or 0
    )

    # Model call stats as proxy for request volume
    total_calls = int(db.scalar(select(func.count(ModelCall.id))) or 0)
    failed_calls = int(
        db.scalar(select(func.count(ModelCall.id)).where(ModelCall.success.is_(False))) or 0
    )
    avg_latency = float(
        db.scalar(select(func.avg(ModelCall.latency_ms))) or 0.0
    )

    return SystemMetricsResponse(
        uptime_seconds=0.0,  # Would need process start time tracking
        request_count=total_calls,
        error_count=failed_calls,
        avg_latency_ms=round(avg_latency, 2),
        p95_latency_ms=None,  # Would need percentile calculation
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
    calls_today = int(
        db.scalar(select(func.count(ModelCall.id)).where(ModelCall.created_at >= today_start)) or 0
    )
    total_videos = int(db.scalar(select(func.count(VideoAsset.id))) or 0)
    avg_latency = float(
        db.scalar(select(func.avg(ModelCall.latency_ms))) or 0.0
    )
    successful = int(
        db.scalar(select(func.count(ModelCall.id)).where(ModelCall.success.is_(True))) or 0
    )
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
    provider_counts = db.execute(
        select(ModelCall.provider, func.count(ModelCall.id))
        .group_by(ModelCall.provider)
    ).all()
    calls_by_provider = {str(provider): int(count) for provider, count in provider_counts}

    # Costs
    total_cost = float(
        db.scalar(select(func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0))) or 0.0
    )
    cost_today = float(
        db.scalar(
            select(func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0)).where(
                ModelCall.created_at >= today_start
            )
        ) or 0.0
    )

    # Latency
    avg_latency = float(
        db.scalar(select(func.avg(ModelCall.latency_ms))) or 0.0
    )

    # Demo mode percentage
    demo_calls = int(
        db.scalar(select(func.count(ModelCall.id)).where(ModelCall.demo_mode.is_(True))) or 0
    )
    demo_pct = (demo_calls / total_calls * 100) if total_calls > 0 else 0.0

    return ProviderMetricsResponse(
        total_calls=total_calls,
        calls_by_provider=calls_by_provider,
        total_cost_usd=round(total_cost, 4),
        cost_today_usd=round(cost_today, 4),
        avg_latency_ms=round(avg_latency, 2),
        demo_mode_percentage=round(demo_pct, 2),
    )
