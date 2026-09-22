"""Progress + history + privacy surfaces (spec §8, §11, §38, §61, §88 empty/loading states)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, ownership_or_admin
from app.models import (
    Achievement,
    AttributeChange,
    TrainingDrill,
    TrainingSession,
    User,
    UserAchievement,
    UserPlayer,
    XpEvent,
)
from app.services.attributes import ATTRIBUTES
from app.services.progression import level_from_xp, xp_for_next_level

router = APIRouter(prefix="/progress", tags=["progress"])


def _player_or_404(db: Session, user: User, player_id: str | None) -> UserPlayer:
    player = db.get(UserPlayer, player_id) if player_id else db.scalar(select(UserPlayer).where(UserPlayer.user_id == user.id).order_by(UserPlayer.created_at))
    if player is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "no_player", "message": "Create your player profile first"})
    ownership_or_admin(user, player.user_id, "player")
    return player


@router.get("/overview")
def overview(player_id: str | None = Query(default=None), db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    player = _player_or_404(db, user, player_id)
    clean = {k: v for k, v in player.attributes.items() if not k.startswith("_sp_")}
    completed = int(db.scalar(select(func.count(TrainingSession.id)).where(TrainingSession.player_id == player.id, TrainingSession.status == "completed")) or 0)
    this_week = int(
        db.scalar(
            select(func.count(TrainingSession.id)).where(
                TrainingSession.player_id == player.id,
                TrainingSession.status == "completed",
                TrainingSession.completed_at >= (date.today() - timedelta(days=7)).isoformat(),
            )
        )
        or 0
    )
    next_level_xp = xp_for_next_level(player.level_number)
    current_level_floor = xp_for_next_level(player.level_number - 1) if player.level_number > 1 else 0
    last_completed = db.scalar(select(func.max(TrainingSession.completed_at)).where(TrainingSession.player_id == player.id))
    progress_in_level = 0.0
    if next_level_xp > current_level_floor:
        progress_in_level = max(0.0, min(1.0, (player.xp - current_level_floor) / (next_level_xp - current_level_floor)))
    return {
        "player": {
            "id": player.id,
            "name": player.name,
            "position": player.position,
            "age": player.age,
            "goal": player.goal,
            "overall": player.overall,
            "potential": player.potential,
            "form": player.form,
            "archetype": player.archetype,
            "archetype_match": player.archetype_match,
            "preferred_foot": player.preferred_foot,
        },
        "attributes": clean,
        "attribute_groups": {group: {a: clean.get(a, 40) for a in names} for group, names in ATTRIBUTES.items()},
        "xp": {"total": player.xp, "level": player.level_number, "next_level_at": next_level_xp, "progress_in_level": round(progress_in_level, 3)},
        "training": {
            "sessions_completed": completed,
            "sessions_this_week": this_week,
            "streak_days": user.streak_days,
            "last_session_at": last_completed.isoformat() if last_completed else None,
        },
        "achievements": [
            {"slug": a.slug, "title": a.title, "description": a.description, "awarded_at": ua.awarded_at.isoformat()}
            for a, ua in db.execute(
                select(Achievement, UserAchievement)
                .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
                .where(UserAchievement.user_id == user.id)
                .order_by(UserAchievement.awarded_at)
            ).all()
        ],
        "empty_state": completed == 0,
        "demo_data": player.is_demo_data,
    }


@router.get("/timeline")
def timeline(player_id: str | None = Query(default=None), days: int = Query(default=30, ge=7, le=180), db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    player = _player_or_404(db, user, player_id)
    since = date.today() - timedelta(days=days)
    sessions = db.scalars(select(TrainingSession).where(TrainingSession.player_id == player.id, TrainingSession.planned_date >= since.isoformat()).order_by(TrainingSession.planned_date)).all()
    changes = db.scalars(select(AttributeChange).where(AttributeChange.player_id == player.id, AttributeChange.created_at >= str(since)).order_by(AttributeChange.created_at)).all()
    by_attribute: dict[str, list[dict[str, Any]]] = {}
    for change in changes:
        by_attribute.setdefault(change.attribute, []).append({"at": change.created_at.isoformat(), "after": change.after, "delta": change.delta, "reason": change.reason})
    session_rows = []
    for s in sessions:
        drill = db.get(TrainingDrill, s.drill_id)
        session_rows.append(
            {
                "date": s.planned_date,
                "status": s.status,
                "xp": s.xp_awarded,
                "execution": s.execution_rating,
                "drill": drill.title if drill else "Data unavailable",
                "category": drill.category if drill else "unknown",
            }
        )
    return {
        "sessions": session_rows,
        "attribute_series": by_attribute,
        "xp_events": [
            {"at": e.created_at.isoformat(), "amount": e.amount, "reason": e.reason, "formula": e.formula}
            for e in db.scalars(select(XpEvent).where(XpEvent.player_id == player.id).order_by(XpEvent.created_at)).all()
        ],
        "level_estimate": level_from_xp(player.xp),
        "demo_data": player.is_demo_data,
    }


@router.get("/export")
def export(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Data export right (spec §61)."""
    players = db.scalars(select(UserPlayer).where(UserPlayer.user_id == user.id)).all()
    return {
        "user": {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role, "created_at": user.created_at.isoformat()},
        "players": [
            {
                "id": p.id,
                "name": p.name,
                "position": p.position,
                "age": p.age,
                "goal": p.goal,
                "attributes": p.attributes,
                "overall": p.overall,
                "archetype": p.archetype,
                "xp": p.xp,
                "level_number": p.level_number,
            }
            for p in players
        ],
        "sessions": [
            {"id": s.id, "status": s.status, "planned_date": s.planned_date, "xp_awarded": s.xp_awarded, "drill_id": s.drill_id, "execution_rating": s.execution_rating}
            for s in db.scalars(select(TrainingSession).where(TrainingSession.user_id == user.id)).all()
        ],
        "xp_events": [{"amount": e.amount, "reason": e.reason, "formula": e.formula, "at": e.created_at.isoformat()} for e in db.scalars(select(XpEvent).where(XpEvent.user_id == user.id)).all()],
        "format_version": 1,
    }


@router.delete("/player-data", status_code=status.HTTP_200_OK)
def delete_player_data(db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Delete training history + player identity, keeping the account (spec §61)."""
    players = db.scalars(select(UserPlayer).where(UserPlayer.user_id == user.id)).all()
    for session in db.scalars(select(TrainingSession).where(TrainingSession.user_id == user.id)).all():
        db.delete(session)
    for event in db.scalars(select(XpEvent).where(XpEvent.user_id == user.id)).all():
        db.delete(event)
    for player in players:
        for change in db.scalars(select(AttributeChange).where(AttributeChange.player_id == player.id)).all():
            db.delete(change)
        db.delete(player)
    user.streak_days = 0
    user.streak_anchor_date = None
    db.commit()
    return {"deleted_players": len(players), "message": "Player identity and training history deleted. Account retained; use /auth/account to delete it entirely."}
