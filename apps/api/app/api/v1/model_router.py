"""Model router endpoint (spec §45-§46).

A single door for managing and querying all AI providers across the platform. This endpoint
exposes which provider serves each surface (LLM, embedding, reranker, vision, storage), allows
runtime provider switching when credentials exist, and reports cost/usage metrics from the ledger.

The router does not invent capabilities — it exposes what is already configured via settings
and the provider factory functions. Without API keys, surfaces run in DEMO MODE with self-labelled
responses (ADR-005).

Every row describes the platform rather than the caller: the provider serving each surface, today's AI
spend against the shared budget, and a switch that would change the configuration for every account. So
every door asks for the platform's `admin` standing. The status row's `budget_spent_today` is read from
the same ledger `/costs` totals; until this landing it was a hardcoded zero behind a comment.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, role_refusal, standing_check
from app.models import User
from app.providers import provider_status
from app.services.club import answers
from app.services.model_ledger import spend_today_usd

MODEL_ROUTER_STANDING: Final = standing_check(("admin",))


def require_operator(user: User = Depends(current_user)) -> User:
    """The standing every model-router door asks for, carried by the router.

    The costs door publishes the whole platform's spend and the status door publishes the provider
    configuration and the shared budget; the switch door is documented as an admin-only change although
    it refuses everyone today. A session proves none of that, so the standing is mounted on the router:
    a fourth door inherits it along with the bearer check the dependency already carries.
    """
    if user.role not in MODEL_ROUTER_STANDING:
        raise role_refusal(
            held=user.role,
            required=MODEL_ROUTER_STANDING,
            message="Only an admin account may inspect or switch the model router",
        )
    return user


router = APIRouter(prefix="/model-router", tags=["model-router"], dependencies=[Depends(require_operator)])


class ProviderStatusResponse(BaseModel):
    demo_mode: bool
    llm: str
    embedding: str
    reranker: str
    vision: str
    storage: str
    football_data: str
    news: str
    budget_spent_today: float
    budget_limit: float


class ProviderSwitchRequest(BaseModel):
    provider_type: str  # "llm", "embedding", etc.
    provider_name: str  # "openai", "mock", "hash-local", etc.
    api_key: str | None = None
    model: str | None = None


class ProviderSwitchResponse(BaseModel):
    success: bool
    message: str
    new_provider: str


@router.get("/status", response_model=ProviderStatusResponse)
def router_status(db: Session = Depends(get_db)) -> ProviderStatusResponse:
    """Report which provider serves each surface and today's spending.

    Admin standing only: the provider mix and the shared budget are platform configuration, and the
    spend row is every account's calls read from the ledger.
    """
    status = provider_status()
    from app.core.config import settings

    return ProviderStatusResponse(
        demo_mode=status["demo_mode"],
        llm=status["llm"],
        embedding=status["embedding"],
        reranker=status["reranker"],
        vision=status["vision"],
        storage=status["storage"],
        football_data=status["football_data"],
        news=status["news"],
        budget_spent_today=round(spend_today_usd(db), 4),
        budget_limit=settings.ai_daily_budget_usd,
    )


@router.post("/switch", response_model=ProviderSwitchResponse)
def router_switch(
    body: ProviderSwitchRequest,
) -> ProviderSwitchResponse:
    """Switch a provider type at runtime (requires valid credentials).

    This is a configuration change that affects all users, so the door asks for the admin standing
    before it answers. For now every admin call is refused: provider selection is driven by
    environment variables.
    """
    # Provider switching is intentionally not implemented here.
    # Providers are selected by environment variables (settings.*) at startup.
    # Runtime switching would require hot-reloading config and invalidating caches,
    # which violates PRINCIPLE 1 (no premature infrastructure).
    #: The status is read from `answers.ANSWERS` rather than spelled: this door refuses the verb
    #: categorically — provider selection is read from the environment at startup, so no standing can
    #: earn it, which is why it is not 403 (the permission matrix's single meaning) but the table's
    #: capability answer. The door registers the code and asks for its row.
    raise HTTPException(
        answers.ANSWERS["provider_switch_unavailable"],
        detail={
            "code": "provider_switch_unavailable",
            "message": "Provider switching requires environment variable changes and server restart.",
            "provider_type": body.provider_type,
            "current_provider": provider_status().get(body.provider_type, "unknown"),
        },
    )


@router.get("/costs")
def router_costs(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Report today's AI spending from the model call ledger.

    Admin standing only: the total is the whole platform's spend, not the caller's.
    """
    spent = spend_today_usd(db)
    from app.core.config import settings

    return {
        "spent_today_usd": round(spent, 4),
        "budget_limit_usd": settings.ai_daily_budget_usd,
        "remaining_usd": round(max(0, settings.ai_daily_budget_usd - spent), 4),
        "budget_exhausted": spent >= settings.ai_daily_budget_usd,
    }
