"""Gamification leaderboard (spec §37: XP, Levels, Badges, Achievements, Streaks, Challenges, Leaderboards).

Two truths and one rule. The truths: XP is the score, and the board counts XP only for accounts
that opted in — a new account is invisible here until it says so itself. The rule: ranks are by
XP, ties are broken by the account's own creation order, and nothing here ever names a row
that did not opt in.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import utc_midnight
from app.models import User, XpEvent, utc_today


def _since() -> object:
    return utc_midnight(utc_today() - timedelta(days=29))


def leaders(session: Session, *, top: int = 10) -> list[dict[str, Any]]:
    since = _since()
    xp = (
        select(XpEvent.user_id, func.sum(XpEvent.amount).label("xp"))
        .where(XpEvent.created_at >= since)
        .group_by(XpEvent.user_id)
        .subquery()
    )
    rows = session.execute(
        select(User.display_name, User.streak_days, User.id, func.coalesce(xp.c.xp, 0))
        .outerjoin(xp, xp.c.user_id == User.id)
        .where(User.leaderboard_visible.is_(True), User.is_active.is_(True))
        .order_by(func.coalesce(xp.c.xp, 0).desc(), User.created_at.asc())
        .limit(top)
    ).all()
    return [
        {"rank": index + 1, "name": name, "streak": int(streak or 0), "xp": int(xp or 0)}
        for index, (name, streak, _, xp) in enumerate(rows)
    ]


def my_stats(session: Session, user: User) -> dict[str, Any]:
    since = _since()
    xp = session.scalar(select(func.sum(XpEvent.amount)).where(XpEvent.user_id == user.id, XpEvent.created_at >= since)) or 0
    # One aggregate scan, one outer join — the same shape `leaders` uses. The previous form wrapped a
    # correlated subquery in the WHERE of an all-accounts scan, which the planner ran once per visible
    # account; this computes the per-account total once for the whole board.
    totals = (
        select(XpEvent.user_id, func.sum(XpEvent.amount).label("total"))
        .where(XpEvent.created_at >= since)
        .group_by(XpEvent.user_id)
    ).subquery()
    ahead = session.scalar(
        select(func.count())
        .select_from(User)
        .outerjoin(totals, totals.c.user_id == User.id)
        .where(User.leaderboard_visible.is_(True), User.is_active.is_(True), User.id != user.id)
        .where(func.coalesce(totals.c.total, 0) > xp)
    )
    rank = (ahead or 0) + 1
    return {
        "rank": rank,
        "xp": int(xp),
        "streak": int(user.streak_days or 0),
        "visible": bool(user.leaderboard_visible),
    }


def set_visibility(session: Session, user: User, *, enabled: bool) -> bool:
    user.leaderboard_visible = bool(enabled)
    session.commit()
    return user.leaderboard_visible


def count_visible(session: Session) -> int:
    return int(session.scalar(select(func.count()).where(User.leaderboard_visible.is_(True), User.is_active.is_(True))) or 0)
