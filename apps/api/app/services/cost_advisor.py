"""Cost optimisation advisor (spec §46, §59, §76, M12).

Reads the ledger — `model_calls` — and answers where the money went and what a cheaper call would
have been. Every figure is recomputed from the rows on the request, and every recommendation names
the arithmetic that produced it: this is a cost *advisor*, not a cost *enforcer*. It changes nothing
about how a provider is chosen (§45's router owns that); it prints what the choice cost, so a human
can decide whether the choice was right.

Five questions, each answered over a stated window:

* **by feature** — which feature spent the money, with its own share and its failure rate beside it.
  A feature that fails half its calls is paying for nothing, and a failure rate is the cheapest thing
  on this page to fix.
* **by model** — cost per thousand tokens across the models actually called, with the share of spend
  each holds. A cheaper model doing the same feature is a routing decision, and it is made with the
  figures printed here rather than a guess.
* **reasoning tokens** — the share of output tokens the reasoning model spent *thinking*. OpenAI's
  reasoning models charge the same per token for reasoning as for answer, so this share is where the
  money went when it went somewhere unexpected.
* **demo share** — the share of calls that ran in demo mode. A demo call costs nothing, so this is
  the honest share of the ledger that is free, printed beside the paid share rather than instead of it.
* **failure waste** — what the failed calls cost. A failed call is a paid call with no answer.

The window is stated in the answer (`days`), and an empty ledger answers with the zeros and a
sentence saying so rather than an error: a platform that has never made a call has no cost to report.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import Float, Integer, case, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ModelCall

#: The window the advisor reads by default. A longer window smooths a single expensive day; a shorter
#: one is too noisy to advise on. Thirty days is long enough to see a routing decision's effect.
DEFAULT_WINDOW_DAYS: int = 30


def _window_start(days: int) -> datetime:
    return (datetime.now(UTC) - timedelta(days=max(1, days))).replace(microsecond=0)


def _share(part: float, whole: float) -> float:
    """A share that answers 0.0 rather than raising on an empty ledger."""
    return (part / whole) if whole > 0 else 0.0


def _totals(db: Session, since: datetime) -> dict[str, Any]:
    """The window's own arithmetic: what was spent, how many calls, how many failed, how many were demo."""
    row = db.execute(
        select(
            func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0).cast(Float),
            func.count(ModelCall.id).cast(Integer),
            func.coalesce(func.sum(case((ModelCall.success.is_(False), 1), else_=0)), 0).cast(Integer),
            func.coalesce(func.sum(case((ModelCall.demo_mode.is_(True), 1), else_=0)), 0).cast(Integer),
            func.coalesce(func.sum(ModelCall.input_tokens), 0).cast(Integer),
            func.coalesce(func.sum(ModelCall.output_tokens), 0).cast(Integer),
            func.coalesce(func.sum(ModelCall.reasoning_tokens), 0).cast(Integer),
        ).where(ModelCall.created_at >= since)
    ).one()
    return {
        "spend_usd": round(float(row[0]), 4),
        "calls": int(row[1]),
        "failed_calls": int(row[2]),
        "demo_calls": int(row[3]),
        "input_tokens": int(row[4]),
        "output_tokens": int(row[5]),
        "reasoning_tokens": int(row[6]),
    }


def _by_feature(db: Session, since: datetime) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            ModelCall.feature,
            func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0).cast(Float),
            func.count(ModelCall.id).cast(Integer),
            func.coalesce(func.sum(case((ModelCall.success.is_(False), 1), else_=0)), 0).cast(Integer),
        )
        .where(ModelCall.created_at >= since)
        .group_by(ModelCall.feature)
        .order_by(func.sum(ModelCall.actual_cost_usd).desc())
    ).all()
    return [
        {
            "feature": str(feature),
            "spend_usd": round(float(spend), 4),
            "calls": int(calls),
            "failed_calls": int(failed),
            "failure_rate": round(_share(float(failed), float(calls)), 4),
        }
        for feature, spend, calls, failed in rows
    ]


def _by_model(db: Session, since: datetime) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            ModelCall.provider,
            ModelCall.model,
            func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0).cast(Float),
            func.coalesce(func.sum(ModelCall.input_tokens + ModelCall.output_tokens), 0).cast(Integer),
            func.count(ModelCall.id).cast(Integer),
        )
        .where(ModelCall.created_at >= since)
        .group_by(ModelCall.provider, ModelCall.model)
        .order_by(func.sum(ModelCall.actual_cost_usd).desc())
    ).all()
    out = []
    for provider, model, spend, tokens, calls in rows:
        thousand = float(tokens) / 1000.0
        out.append(
            {
                "provider": str(provider),
                "model": str(model),
                "spend_usd": round(float(spend), 4),
                "tokens": int(tokens),
                "calls": int(calls),
                #: Cost per thousand tokens, the figure a routing decision is made on. A model with no
                #: tokens has no rate to print, and 0.0 would read as "the cheapest" — None says the
                #: ledger contains nothing to divide.
                "cost_per_1k_tokens_usd": round(float(spend) / thousand, 4) if thousand > 0 else None,
            }
        )
    return out


#: How the monthly figure is derived, published beside it.
MONTHLY_FORMULA: Final = (
    "month-to-date is the actual_cost_usd of model_calls since the first instant of the current UTC month; "
    "the projection is that spend ÷ the days elapsed × the month's length, so it is a pace, not a forecast "
    "of a different traffic pattern"
)


def _month_start(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def monthly_state(db: Session, *, now: datetime | None = None) -> dict[str, Any]:
    """Month-to-date spend against the published ceiling (`AI_MONTHLY_CEILING_USD`), and its pace.

    A ceiling of 0 means none is configured, and the answer says so rather than inventing one: the
    projection is still published, because a spend rate is useful even with no ceiling beside it.
    """
    moment = now or datetime.now(UTC)
    start = _month_start(moment)
    row = db.execute(
        select(
            func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0).cast(Float),
            func.count(ModelCall.id).cast(Integer),
        ).where(ModelCall.created_at >= start)
    ).one()
    spend = round(float(row[0]), 4)
    calls = int(row[1])
    ceiling = float(settings.ai_monthly_ceiling_usd)
    configured = ceiling > 0
    days_in_month = calendar.monthrange(moment.year, moment.month)[1]
    projected = round(spend / max(1, moment.day) * days_in_month, 4) if spend > 0 else 0.0
    return {
        "month": f"{moment.year:04d}-{moment.month:02d}",
        "spend_usd": spend,
        "calls": calls,
        "ceiling_usd": round(ceiling, 2) if configured else None,
        "configured": configured,
        "remaining_usd": round(max(0.0, ceiling - spend), 4) if configured else None,
        "used_pct": round(spend / ceiling, 4) if configured else None,
        "projected_month_end_usd": projected,
        "exceeded": bool(configured and spend > ceiling),
        "projected_over": bool(configured and projected > ceiling),
        "formula": MONTHLY_FORMULA,
        "note": (
            f"month-to-date spend against AI_MONTHLY_CEILING_USD=${ceiling:.2f}"
            if configured
            else "no monthly ceiling is configured (set AI_MONTHLY_CEILING_USD); the projection is still published"
        ),
    }


def recommend(db: Session, *, days: int = DEFAULT_WINDOW_DAYS) -> dict[str, Any]:
    """The advisor's whole answer for one window, every figure recomputed from the ledger."""
    since = _window_start(days)
    totals = _totals(db, since)
    features = _by_feature(db, since)
    models = _by_model(db, since)
    spend = float(totals["spend_usd"])
    calls = int(totals["calls"])

    output_tokens = int(totals["output_tokens"])
    reasoning = int(totals["reasoning_tokens"])
    failed_waste_row = db.execute(select(func.coalesce(func.sum(ModelCall.actual_cost_usd), 0.0).cast(Float)).where(ModelCall.created_at >= since, ModelCall.success.is_(False))).scalar()
    failed_waste = round(float(failed_waste_row or 0.0), 4)

    recommendations: list[dict[str, Any]] = []

    # 1. Failures cost money and answer nothing. The cheapest saving on the page.
    if calls and int(totals["failed_calls"]) / calls > 0.05:
        recommendations.append(
            {
                "code": "failure_waste",
                "summary": (f"{int(totals['failed_calls'])} of {calls} calls failed " f"({_share(float(totals['failed_calls']), float(calls)):.0%}), costing ${failed_waste}"),
                "spend_usd": failed_waste,
                "why": "a failed call is a paid call with no answer; its rate is on the by_feature list above",
            }
        )

    # 2. Reasoning tokens are billed as output; a large share is where the money went.
    if output_tokens and reasoning / output_tokens > 0.5:
        recommendations.append(
            {
                "code": "reasoning_share",
                "summary": (f"{reasoning:,} of {output_tokens:,} output tokens were reasoning " f"({reasoning / output_tokens:.0%}) — billed at the model's output rate"),
                "spend_usd": round(spend * (reasoning / output_tokens), 4),
                "why": "reasoning effort is not visible in the answer; a lower effort on the same feature is a parameter, not a rewrite",
            }
        )

    # 3. The daily budget, if a spend rate would cross it.
    if spend > 0:
        per_day = spend / max(1, days)
        budget = float(settings.ai_daily_budget_usd)
        if per_day > budget:
            recommendations.append(
                {
                    "code": "budget_pace",
                    "summary": f"${per_day:.2f}/day against a ${budget:.2f} daily budget",
                    "spend_usd": round(per_day - budget, 4),
                    "why": f"the window spent ${spend} over {days} days; the budget is settings.ai_daily_budget_usd",
                }
            )

    # 4. A cheaper model is already doing the same kind of work in this ledger.
    priced = [m for m in models if m["cost_per_1k_tokens_usd"] is not None and m["calls"] >= 5]
    if len(priced) >= 2:
        cheapest = min(priced, key=lambda m: float(m["cost_per_1k_tokens_usd"] or 0.0))
        dearest = max(priced, key=lambda m: float(m["cost_per_1k_tokens_usd"] or 0.0))
        ratio = float(dearest["cost_per_1k_tokens_usd"] or 0.0) / max(float(cheapest["cost_per_1k_tokens_usd"] or 1e-9), 1e-9)
        if ratio >= 2.0:
            recommendations.append(
                {
                    "code": "cheaper_model_available",
                    "summary": (f"{dearest['model']} pays ${dearest['cost_per_1k_tokens_usd']}/1k tokens where " f"{cheapest['model']} pays ${cheapest['cost_per_1k_tokens_usd']}"),
                    "spend_usd": round(float(dearest["spend_usd"]) * (1.0 - 1.0 / ratio), 4),
                    "why": "routing is §45's decision; these are the two rates the ledger holds for models both already called",
                }
            )

    monthly = monthly_state(db)
    if monthly["configured"] and (monthly["exceeded"] or monthly["projected_over"]):
        recommendations.append(
            {
                "code": "monthly_ceiling",
                "summary": (
                    f"${monthly['spend_usd']:.2f} spent of a ${monthly['ceiling_usd']:.2f} monthly ceiling"
                    if monthly["exceeded"]
                    else f"${monthly['spend_usd']:.2f} spent, projected ${monthly['projected_month_end_usd']:.2f} by month end against a ${monthly['ceiling_usd']:.2f} ceiling"
                ),
                "spend_usd": monthly["spend_usd"],
                "why": "the monthly ceiling is a published budget, not a rate limit; this names the month-to-date figure and its pace",
            }
        )

    return {
        "window_days": max(1, days),
        "monthly": monthly,
        "totals": {
            **totals,
            "demo_share": round(_share(float(totals["demo_calls"]), float(calls)), 4),
            "reasoning_share": round(_share(float(reasoning), float(output_tokens)), 4),
            "budget_usd_per_day": round(float(settings.ai_daily_budget_usd), 4),
        },
        "by_feature": features,
        "by_model": models,
        "recommendations": recommendations,
        "limitation": (
            "these figures are recomputed from the ledger, not from a provider invoice; a demo-mode call "
            "costs nothing and is counted as such, and nothing here changes which provider a door calls (§45)"
        ),
    }


__all__ = ["DEFAULT_WINDOW_DAYS", "MONTHLY_FORMULA", "monthly_state", "recommend"]
