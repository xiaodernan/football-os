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
            cached_input_tokens=result.cached_input_tokens,
            cache_reported=result.cache_reported,
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


def cache_hit_rate(db: Session) -> dict[str, float | int]:
    """The measurable prefix-cache story across every recorded call.

    `hit_rate` is cached ÷ input, but only over the calls whose gateway actually **reported** a
    cache figure. That qualifier is the whole point: this project's gateway prints
    `prompt_tokens_details` on some calls and nothing at all on others (measured 2026-11-13: four of
    six warm repeats reported 4 352 cached of 4 472 tokens, two reported no details object). Counting
    silence as a miss put a working 97 % cache on the dashboard as roughly 50 %.

    `coverage` is the honesty that goes with it — the share of recorded input tokens the ratio is
    actually computed over. A rate of 0.97 at coverage 0.55 means "of the half of the bill we can
    see, 97 % hit"; a rate of 0.0 at coverage 0.0 means the gateway never told us anything, which is
    not the same as a cache that never hit. Rows written before `cache_reported` existed count as
    unreported, which is what they are.
    """
    from sqlalchemy import func, select

    total_in = int(db.scalar(select(func.coalesce(func.sum(ModelCall.input_tokens), 0))) or 0)
    cached = int(db.scalar(select(func.coalesce(func.sum(ModelCall.cached_input_tokens), 0))) or 0)
    calls = int(db.scalar(select(func.count(ModelCall.id))) or 0)
    cost = float(db.scalar(select(func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0))) or 0.0)
    reported_in = int(
        db.scalar(select(func.coalesce(func.sum(ModelCall.input_tokens), 0)).where(ModelCall.cache_reported.is_(True))) or 0
    )
    reported_calls = int(db.scalar(select(func.count(ModelCall.id)).where(ModelCall.cache_reported.is_(True))) or 0)
    #: A row that reported a figure may still have reported zero — that is a real miss and stays in
    #: both the numerator (as zero) and the denominator (as its input).
    reported_cached = int(
        db.scalar(
            select(func.coalesce(func.sum(ModelCall.cached_input_tokens), 0)).where(ModelCall.cache_reported.is_(True))
        )
        or 0
    )
    return {
        "cached_input_tokens": cached,
        "input_tokens": total_in,
        "calls": calls,
        "hit_rate": round(reported_cached / reported_in, 4) if reported_in else 0.0,
        "coverage": round(reported_in / total_in, 4) if total_in else 0.0,
        "reported_calls": reported_calls,
        "reported_input_tokens": reported_in,
        "cost_usd": round(cost, 6),
    }


def budget_exhausted(db: Session) -> bool:
    return spend_today_usd(db) >= settings.ai_daily_budget_usd
