"""Achievement awards (spec §37): gamification must push learning/training, nothing else."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Achievement, AttributeChange, TrainingSession, User, UserAchievement, UserPlayer
from app.services.progression import ACHIEVEMENTS


def award(db: Session, user: User, player: UserPlayer) -> list[str]:
    completed = int(db.scalar(select(func.count(TrainingSession.id)).where(TrainingSession.user_id == user.id, TrainingSession.status == "completed")) or 0)
    attr_changes = int(db.scalar(select(func.count(AttributeChange.id)).where(AttributeChange.player_id == player.id)) or 0)
    earned = {
        "first-session": completed >= 1,
        "week-streak": user.streak_days >= 7,
        "ten-sessions": completed >= 10,
        "first-breakthrough": attr_changes >= 1,
        "level-5": player.level_number >= 5,
    }
    existing = set(db.scalars(select(Achievement.slug).join(UserAchievement, UserAchievement.achievement_id == Achievement.id).where(UserAchievement.user_id == user.id)).all())
    newly: list[str] = []
    for spec in ACHIEVEMENTS:
        slug = spec["slug"]
        if not earned.get(slug) or slug in existing:
            continue
        row = db.scalar(select(Achievement).where(Achievement.slug == slug))
        if row is None:
            row = Achievement(id=f"ach_{slug}", **spec)
            db.add(row)
            db.flush()
        db.add(UserAchievement(id=f"ua_{slug}_{user.id}", user_id=user.id, achievement_id=row.id))
        newly.append(slug)
    return newly
