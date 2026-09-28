"""Portfolio endpoints (M10, spec §38): the Football CV, read section by section from rows other tiers own.

One public door and one private one. `GET /portfolio/rules` prints only the tier's own vocabulary — §38's ten
sections in §38's order, the expression behind every derived figure, the two sections this build cannot fill and
the measurement that says so, and §38's three permitted outputs with their state — which is §39's, §35's and §36's
precedent: a rulebook is not a person's rows, a CV is.

`GET /portfolio/cv` is the CV itself. There is no write door anywhere in this file, because a CV has nothing of its
own to store: no `portfolio*` table exists, and `test_portfolio.py` asserts that over `Base.metadata` rather than
taking this sentence's word for it. Nothing is cached either — every figure is counted from the rows its published
formula names at the moment of the read, which is why completing a session and re-reading this door shows the new
number.

This tier registers no refusal code. The only question a door asks is whether the caller has a session, which
`current_user` answers with a 401 before any service code runs; an account with no player row is not a refusal but a
CV whose player-backed sections say so, which is §35's rule — absence is an answer, never a confirmation that
somebody else's rows exist. `refusal_answers` is still printed from the project's one table
(`services/club/answers.py`) so that a code added by a later slice cannot be answered one way here and another at
`/club`.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import User
from app.services.club import answers
from app.services.portfolio import cv as portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

#: Every door this module declares, in the order a reader meets them. Held against the live route table by
#: `test_portfolio.py` in both directions, because the rules door prints this list to the browser as the tier's own
#: description of itself.
ROUTE_GUIDE: Final[tuple[dict[str, str], ...]] = (
    {"method": "GET", "path": "/portfolio/rules", "door": "the tier's vocabulary: §38's ten sections, the formulas, the two the build cannot fill, the three outputs it permits"},
    {"method": "GET", "path": "/portfolio/cv", "door": "your Football CV: ten sections, each a read of the rows its source names"},
)


def _vocabulary() -> list[dict[str, Any]]:
    """§38's ten sections as data: the key, the spec's word for it, the rows behind it, and whether this build fills it."""
    return [
        {
            "section": key,
            "title": portfolio.SECTION_TITLES[key],
            "source": portfolio.SOURCES.get(key, ""),
            "fillable": key not in portfolio.UNFILLED_REASONS,
        }
        for key in portfolio.SECTIONS
    ]


@router.get("/rules")
def read_rules() -> dict[str, Any]:
    """The rulebook door: no account, no player, no figure about anybody — only what a CV is made of."""
    return {
        "routes": [dict(item) for item in ROUTE_GUIDE],
        "refusal_answers": answers.published(portfolio.REFUSALS),
        "sections": _vocabulary(),
        "unfilled": {key: portfolio.UNFILLED_REASONS[key] for key in portfolio.SECTIONS if key in portfolio.UNFILLED_REASONS},
        "would_read_from": dict(portfolio.WOULD_READ_FROM),
        "formulas": dict(portfolio.FORMULAS),
        "public_outputs": dict(portfolio.PUBLIC_OUTPUTS),
        "limitation": portfolio.LIMITATION,
    }


@router.get("/cv")
def read_cv(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The account's CV, ten sections in §38's order. Nothing here is stored and nothing is cached."""
    limit(request, 60, 60, scope="portfolio_read")
    return portfolio.build_cv(db, user.id)
