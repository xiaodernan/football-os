"""Explainable progression (spec §8, §11, §37).

Training -> XP -> skill points -> attribute gain -> archetype re-fit.
Every mutation stores a reason and the evidence rows that caused it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ALL_ATTRIBUTES, AttributeChange, TrainingDrill, TrainingSession, User, UserPlayer, XpEvent, utcnow

# Guardrails keep progression honest: no single session can inflate a player.
MAX_DAILY_XP = 400
MAX_ATTRIBUTE_GAIN_PER_ATTR_7D = 2
MAX_ATTRIBUTE_GAIN_PER_SESSION = 1
SKILL_POINTS_PER_ATTRIBUTE_POINT = 100
ACHIEVEMENTS: list[dict[str, str]] = [
    {"slug": "first-session", "title": "First Bricks Laid", "description": "Complete your first training session.", "criterion": "sessions>=1"},
    {"slug": "week-streak", "title": "Seven Days Running", "description": "Train 7 days in a row.", "criterion": "streak>=7"},
    {"slug": "ten-sessions", "title": "Consistency Tax Paid", "description": "Complete 10 training sessions.", "criterion": "sessions>=10"},
    {"slug": "first-breakthrough", "title": "Attribute Breakthrough", "description": "Raise any attribute through training.", "criterion": "attr_changes>=1"},
    {"slug": "level-5", "title": "Coming Through", "description": "Reach player level 5.", "criterion": "level>=5"},
]


def xp_for_completion(*, drill: TrainingDrill, execution: int, focus: int, difficulty_experience: int, streak_days: int) -> tuple[int, str]:
    """Deterministic, documented XP formula."""
    quality = (execution * 0.55 + focus * 0.30 + difficulty_experience * 0.15) / 5
    difficulty_factor = 0.85 + 0.075 * drill.difficulty
    streak_factor = 1 + min(streak_days, 7) * 0.02
    xp = round(drill.xp_base * (0.45 + 0.75 * quality) * difficulty_factor * streak_factor)
    formula = (
        f"{drill.xp_base} base x quality {0.45 + 0.75 * quality:.2f} "
        f"(execution {execution}/5, focus {focus}/5, difficulty {difficulty_experience}/5) "
        f"x difficulty {difficulty_factor:.2f} x streak {streak_factor:.2f} = {xp} XP"
    )
    return xp, formula


def level_from_xp(xp: int) -> int:
    """Inverse of xp_for_next_level: total XP needed to *reach* level L is 20(L-1)^2 + 80(L-1)."""
    if xp < 100:
        return 1
    return int((-80 + math.sqrt(6400 + 80 * xp)) / 40) + 1


def xp_for_next_level(level_number: int) -> int:
    """Total XP required to reach level_number + 1."""
    n = level_number
    return int(20 * n * n + 80 * n)


def update_streak(user: User) -> tuple[int, bool]:
    """Returns (streak, changed). Streak anchors to ISO date strings."""
    today = date.today().isoformat()
    if user.streak_anchor_date == today:
        return user.streak_days, False
    from datetime import timedelta

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if user.streak_anchor_date == yesterday and user.streak_days > 0:
        user.streak_days += 1
    else:
        user.streak_days = 1
    user.streak_anchor_date = today
    return user.streak_days, True


@dataclass
class CompletionResult:
    session: TrainingSession
    xp_awarded: int
    xp_formula: str
    player: UserPlayer
    attribute_changes: list[dict[str, Any]]
    skill_progress: list[dict[str, Any]]
    level_number: int
    level_changed: bool
    streak_days: int
    new_achievements: list[str]
    form: float


def _recent_gain(db: Session, player_id: str, attribute: str, days: int = 7) -> int:
    from datetime import timedelta

    since = utcnow() - timedelta(days=days)
    rows = db.scalars(select(AttributeChange.delta).where(AttributeChange.player_id == player_id, AttributeChange.attribute == attribute, AttributeChange.created_at >= since)).all()
    return int(sum(rows))


def apply_skill_points(db: Session, player: UserPlayer, drill: TrainingDrill, quality: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert drill emphasis into attribute gains with caps and stored reasons.

    Returns (changes, progress). `progress` explains every targeted attribute, including the
    common first-session case where the banked skill points are still below the 100-point
    threshold — a user must be able to tell "still banking" from "nothing happened".
    """
    changes: list[dict[str, Any]] = []
    progress: list[dict[str, Any]] = []
    points = int(drill.xp_base * quality * 1.6)
    total_weight = sum(drill.target_attributes.values()) or 1
    for attribute, weight in sorted(drill.target_attributes.items()):
        if attribute not in ALL_ATTRIBUTES:
            continue
        needed = SKILL_POINTS_PER_ATTRIBUTE_POINT
        earned = int(points * weight / total_weight)
        banked = int(player.attributes.get(f"_sp_{attribute}", 0)) + earned
        current = player.attributes.get(attribute, 40)
        ceiling = ""
        if banked >= needed:
            if current >= min(99, player.potential + 8):
                ceiling = "potential ceiling"
            elif _recent_gain(db, player.id, attribute) >= MAX_ATTRIBUTE_GAIN_PER_ATTR_7D:
                ceiling = "weekly cap"
            elif current >= 99:
                ceiling = "attribute maximum"
            if ceiling:
                banked = needed - 1
            else:
                before, after = current, current + 1
                player.attributes = {**player.attributes, attribute: after}
                banked -= needed
                reason = f"{weight}/{total_weight} weight from '{drill.title}' ({points} skill points at quality {quality:.2f})"
                change = AttributeChange(
                    id=f"ac_{abs(hash((player.id, attribute, before))) % 10**12}",
                    player_id=player.id,
                    attribute=attribute,
                    delta=1,
                    before=before,
                    after=after,
                    reason=reason,
                    evidence_ids=[drill.id],
                )
                db.add(change)
                changes.append({"attribute": attribute, "delta": 1, "before": before, "after": after, "reason": reason})
        player.attributes = {**player.attributes, f"_sp_{attribute}": banked}
        progress.append(
            {
                "attribute": attribute,
                "earned": earned,
                "banked": banked,
                "needed": needed,
                "value": player.attributes.get(attribute, 40),
                "ceiling": ceiling,
            }
        )
    return changes, progress


def refresh_derived_state(player: UserPlayer) -> None:
    from app.services.attributes import compute_overall, derive_archetype

    clean = {k: v for k, v in player.attributes.items() if not k.startswith("_sp_")}
    player.overall = compute_overall(player.position, clean)
    archetype, match, _ = derive_archetype(player.position, clean)
    player.archetype = archetype
    player.archetype_match = match


def complete_session(
    db: Session,
    user: User,
    player: UserPlayer,
    session: TrainingSession,
    drill: TrainingDrill,
    *,
    execution: int,
    focus: int,
    difficulty_experience: int,
    self_notes: str | None = None,
) -> CompletionResult:
    streak, _ = update_streak(user)
    xp, formula = xp_for_completion(drill=drill, execution=execution, focus=focus, difficulty_experience=difficulty_experience, streak_days=streak)
    todays_xp = sum(db.scalars(select(XpEvent.amount).where(XpEvent.user_id == user.id, XpEvent.created_at >= _today_start())).all())
    capped = max(0, min(xp, MAX_DAILY_XP - todays_xp))
    quality = (execution * 0.55 + focus * 0.30 + difficulty_experience * 0.15) / 5
    changes, skill_progress = apply_skill_points(db, player, drill, quality)
    player.xp += capped
    new_level = level_from_xp(player.xp)
    level_changed = new_level > player.level_number
    player.level_number = new_level
    player.form = round(0.7 * player.form + 3.0 * (quality - 0.6), 3)
    refresh_derived_state(player)

    session.status = "completed"
    session.completed_at = utcnow()
    session.execution_rating = execution
    session.focus_quality = focus
    session.difficulty_experience = difficulty_experience
    session.self_notes = self_notes
    session.xp_awarded = capped

    db.add(
        XpEvent(
            id=f"xp_{abs(hash((session.id, capped))) % 10**12}",
            user_id=user.id,
            player_id=player.id,
            amount=capped,
            reason=f"Completed '{drill.title}' (execution {execution}/5, focus {focus}/5)",
            formula=formula if capped == xp else f"{formula}, capped by {MAX_DAILY_XP} XP daily limit (awarded {capped})",
            source_type="training_session",
            source_id=session.id,
        )
    )
    from app.services.achievements import award

    db.flush()  # sessions use autoflush=False; awards must see the completed row
    new_achievements = award(db, user, player)
    db.commit()
    return CompletionResult(
        session=session,
        xp_awarded=capped,
        xp_formula=formula,
        player=player,
        attribute_changes=changes,
        skill_progress=skill_progress,
        level_number=player.level_number,
        level_changed=level_changed,
        streak_days=streak,
        new_achievements=new_achievements,
        form=player.form,
    )


def _today_start() -> datetime:
    return datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
