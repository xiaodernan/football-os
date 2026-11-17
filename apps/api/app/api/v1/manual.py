"""The manual's ask door — the one place a reader asks the product its own question.

Public, unauthenticated, rate-limited like every other public ask surface. The manual itself is the
only knowledge this door may draw on (the printed sections travel in the static prefix; the gateway
caches them across asks). Without a configured provider, or with the budget spent, the door answers
without the model and says exactly so — never an unflagged placeholder product claim.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import limit
from app.services.manual_ask import compute_manual_ask

router = APIRouter(prefix="/manual", tags=["manual"])


class ManualAskIn(BaseModel):
    question: str = Field(min_length=3, max_length=280)
    locale: Literal["en", "zh", "zh-TW", "fr", "ar", "he"] = "en"


@router.post("/ask")
def ask(body: ManualAskIn, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    limit(request, 24, 3600, scope="manual_ask")
    return compute_manual_ask(db, question=body.question, locale=body.locale)


__all__ = ["router"]
