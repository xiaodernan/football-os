"""Leaderboard endpoints: gamification surface (spec §37).

`GET /leaderboard` is a read designed to motivate, not shame. Any reader may open it and read the
opted-in board — accounts that chose to be visible are public by their own choice, which is what
"opt in" means — and a signed-in reader additionally gets their own row and the opt-in switch.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, optional_user
from app.models import User
from app.services import leaderboard as leaderboard_service

router = APIRouter(tags=["leaderboard"])


@router.get("/leaderboard")
def get_leaderboard(db: Session = Depends(get_db), user: User | None = Depends(optional_user)) -> dict[str, object]:
    """The top-ten by 30-day XP among opted-in accounts, plus the caller's own row when signed in.

    The door is read-only and public: the board lists only accounts that opted in, and a reader with no
    credential gets the same board. `optional_user` still declares the bearer scheme, so `PUBLIC_READS`
    in `app.main` erases the security requirement this operation never enforces.
    """
    leaders = leaderboard_service.leaders(db, top=10)
    me = leaderboard_service.my_stats(db, user) if user else None
    visible = leaderboard_service.count_visible(db)
    return {
        "leaders": leaders,
        "me": me,
        "leaders_visible": visible,
        "window_days": 30,
        "opt_in_required": True,
    }


@router.post("/leaderboard")
def set_leaderboard_visibility(
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, object]:
    """Opt in or out of the leaderboard's public rows; the caller's own row is always visible to them."""
    enabled = bool(payload.get("enabled", False))
    visible = leaderboard_service.set_visibility(db, user, enabled=enabled)
    return {"leaderboard_visible": visible}
