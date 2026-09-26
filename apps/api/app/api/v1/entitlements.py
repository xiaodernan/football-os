"""§42's doors: what a plan is entitled to, and what has been used. Nothing here takes money."""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import User
from app.services import entitlements as ent
from app.services.club import answers
from app.services.club.organizations import ClubRefusal

# main.py mounts every router under /api/v1, so the prefix here is only the last segment: a full path
# here would double it and the door would answer 404 while looking correctly written.
router = APIRouter(prefix="/entitlements", tags=["entitlements"])

#: §42's codes are answered from the tier's one table, not a copy written here. An exceeded ceiling is a 409:
#: the request is well-formed and repeatable once the period turns, so it is not a 422, and it is not a 403 —
#: §39 reserved that for a missing standing. A door that assembled its own map is how `no_such_entitlement_plan` came to
#: answer 404 at one club door and 400 at another, and the same code would have grown a third answer here.
_ANSWERS: Final[dict[str, int]] = answers.ANSWERS


def _refusal(error: ClubRefusal) -> HTTPException:
    return answers.refusal(error)


ROUTE_GUIDE = (
    {"methods": ["GET"], "path": "/api/v1/entitlements/capabilities", "purpose": "the plans, the metered features, and which ceilings a write is actually refused on today"},
    {"methods": ["GET"], "path": "/api/v1/entitlements/me", "purpose": "this account's plan, its ceilings, and what it has used in the current period"},
)


@router.get("/capabilities")
def read_capabilities(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The rulebook, answerable before anybody signs in — §41's buyer asks what a plan means first."""
    limit(request, 60, 60, scope="entitlements_capabilities")
    rows = ent.ensure_matrix(db)
    return {
        **ent.rules(),
        "matrix_rows": rows,
        "matrix": ent.matrix_from_table(db),
        "ready": True,
        "data_origin": "project-authored",
        "is_demo_data": False,
        "demo_data": False,
        "routes": [dict(line) for line in ROUTE_GUIDE],
        "limitations": [
            ent.NO_PAYMENT,
            f"only {', '.join(ent.ENFORCED)} is refused on today by a door that checks it; the other ceilings are published as data and enforced as each tier is wired to them",
            "a plan is granted by this platform's own record, not by a purchase: nothing here reads a payment provider, and no price exists to be charged",
        ],
    }


@router.get("/me")
def read_mine(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """What this account's plan is entitled to, and what it has spent in the current period."""
    limit(request, 60, 60, scope="entitlements_read")
    try:
        # Nothing grants a plan yet — that is the part §42 says to leave for later — so every account
        # is read against `free`, the plan the matrix holds for an ungranted subject.
        plan = ent.DEFAULT_PLAN
        view = ent.entitlements_view(db, str(user.id), plan=plan, subject_kind="user")
        return {**view, "display_name": user.display_name, "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None
