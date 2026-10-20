"""Token/cost ledger (spec §46, §59, §76)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import new_public_id
from app.core.timeutil import utc_midnight
from app.models import ModelCall, utc_today
from app.providers import LlmResult


def record_model_call(db: Session, *, result: LlmResult, feature: str, user_id: str | None = None) -> None:
    db.add(
        ModelCall(
            id=new_public_id("mc"),
            provider=result.provider,
            model=result.model,
            feature=feature,
            user_id=user_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            reasoning_tokens=result.reasoning_tokens,
            latency_ms=result.latency_ms,
            estimated_cost_usd=result.estimated_cost_usd,
            actual_cost_usd=result.actual_cost_usd,
            success=result.error is None,
            error=result.error,
            demo_mode=result.demo_mode,
        )
    )


def spend_today_usd(db: Session) -> float:
    from sqlalchemy import func, select

    start = utc_midnight(utc_today())
    return float(db.scalar(select(func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0)).where(ModelCall.created_at >= start)) or 0.0)


def budget_exhausted(db: Session) -> bool:
    return spend_today_usd(db) >= settings.ai_daily_budget_usd
