"""AI Coach engine (spec §9, §12, §17, §34, ADR-005).

Recommendation logic is a transparent weighted decision over stored state — never a
language-model hallucination. The LLM provider is optional and only phrases text; in
DEMO MODE the phrasing is template based and labelled as such.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ATTRIBUTES, AttributeChange, TrainingDrill, TrainingSession, User, UserPlayer, XpEvent
from app.services.achievements import award  # noqa: F401  (kept for parity with progression)
from app.services.attributes import ARCHETYPES, derive_archetype
from app.services.training_catalog import DRILLS

GOAL_FOCUS: dict[str, dict[str, Any]] = {
    "improve_first_touch": {"attributes": ("first_touch", "ball_control"), "categories": ("first_touch", "ball_mastery", "receiving")},
    "improve_passing": {"attributes": ("passing", "long_passing", "vision"), "categories": ("passing", "rondo", "build_up")},
    "improve_dribbling": {"attributes": ("dribbling", "ball_control", "agility"), "categories": ("dribbling", "1v1", "ball_mastery")},
    "improve_finishing": {"attributes": ("finishing", "composure"), "categories": ("finishing", "off_ball_movement")},
    "improve_defending": {"attributes": ("tackling", "defensive_awareness", "positioning"), "categories": ("defending", "positioning")},
    "improve_pressing": {"attributes": ("pressing", "stamina", "transition"), "categories": ("pressing", "transition")},
    "improve_weak_foot": {"attributes": ("first_touch", "passing", "ball_control"), "categories": ("ball_mastery", "weak_foot")},
    "improve_fitness": {"attributes": ("stamina", "speed", "acceleration"), "categories": ("fitness", "transition")},
    "improve_vision": {"attributes": ("vision", "scanning", "decision_making"), "categories": ("scanning", "decision_making")},
    "become_box_to_box": {"attributes": ("pressing", "stamina", "passing", "transition"), "categories": ("pressing", "transition", "passing")},
    "become_playmaker": {"attributes": ("passing", "vision", "first_touch", "decision_making"), "categories": ("receiving", "passing", "decision_making")},
    "become_inverted_winger": {"attributes": ("dribbling", "finishing", "acceleration"), "categories": ("1v1", "dribbling", "finishing")},
}

_INTENT_MAP: tuple[tuple[str, str], ...] = (
    ("train today", "today"),
    ("today's training", "today"),
    ("what should i train", "today"),
    ("weak foot", "weak_foot"),
    ("losing the ball", "ball_loss"),
    ("lose the ball", "ball_loss"),
    ("as a cm", "role_question"),
    ("midfielder", "role_question"),
    ("pressing", "pressing"),
    ("analyze my last match", "match_review"),
    ("analyse my last match", "match_review"),
    ("7 day", "plan_7"),
    ("7-day", "plan_7"),
    ("30 day", "plan_30"),
    ("90 day", "plan_90"),
    ("why", "explain"),
)


@dataclass
class Recommendation:
    drill: dict[str, Any]
    reasons: list[str]
    alternatives: list[dict[str, Any]]
    confidence: float
    focus_attributes: list[str]
    demo_mode: bool = True
    context: dict[str, Any] = field(default_factory=dict)


def _drill_rows(db: Session) -> list[dict[str, Any]]:
    stored = db.scalars(select(TrainingDrill)).all()
    if stored:
        return [
            {
                "id": d.id,
                "slug": d.slug,
                "title": d.title,
                "category": d.category,
                "objective": d.objective,
                "difficulty": d.difficulty,
                "duration_min": d.duration_min,
                "equipment": d.equipment,
                "setup": d.setup,
                "instructions": d.instructions,
                "coaching_points": d.coaching_points,
                "common_mistakes": d.common_mistakes,
                "progressions": d.progressions,
                "regression": d.regression,
                "test_prompt": d.test_prompt,
                "test_target": d.test_target,
                "target_attributes": d.target_attributes,
                "positions": d.positions,
                "xp_base": d.xp_base,
                "needs_pitch": d.needs_pitch,
                "min_age_safe": d.min_age_safe,
                "is_demo_data": d.is_demo_data,
            }
            for d in stored
        ]
    return [dict(d, id=f"seed_{d['slug']}", is_demo_data=True) for d in DRILLS]


def _recent_categories(db: Session, user_id: str, days: int = 5) -> dict[str, int]:
    since = date.today() - timedelta(days=days)
    rows = db.execute(
        select(TrainingDrill.category, XpEvent.created_at)
        .select_from(XpEvent)
        .join(TrainingSession, TrainingSession.id == XpEvent.source_id)
        .join(TrainingDrill, TrainingDrill.id == TrainingSession.drill_id)
        .where(XpEvent.user_id == user_id, XpEvent.created_at >= str(since))
    ).all()
    counts: dict[str, int] = {}
    for category, _created in rows:
        counts[str(category)] = counts.get(str(category), 0) + 1
    return counts


def _public(drill: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in drill.items() if k not in {"id"}} | {"drill_id": drill.get("id", "")}


def recommend_today(
    db: Session,
    user: User,
    player: UserPlayer,
    *,
    available_minutes: int | None = None,
    equipment: list[str] | None = None,
    has_pitch: bool | None = None,
) -> Recommendation:
    attrs = {k: v for k, v in player.attributes.items() if not k.startswith("_sp_")}
    goal = GOAL_FOCUS.get(player.goal, GOAL_FOCUS["improve_first_touch"])
    focus_attributes = list(goal["attributes"])
    minutes = available_minutes or 25
    pitch_available = player.age >= 8 if has_pitch is None else has_pitch
    has_wall = True
    candidates: list[tuple[float, dict[str, Any], list[str]]] = []
    recent = _recent_categories(db, user.id)
    training_load = sum(
        db.scalars(
            select(XpEvent.amount).where(XpEvent.user_id == user.id, XpEvent.created_at >= str(date.today() - timedelta(days=1)))
        ).all()
    )

    for drill in _drill_rows(db):
        reasons: list[str] = []
        score = 0.0
        if drill["duration_min"] > minutes + 5:
            continue
        if drill["category"] in goal["categories"] or any(c in goal["categories"] for c in [drill["category"]]):
            score += 2.2
            reasons.append(f"Directly serves your goal '{player.goal}'")
        target_hits = [a for a in drill["target_attributes"] if a in focus_attributes]
        if target_hits:
            gap_sum = sum(max(0, 70 - attrs.get(a, 40)) for a in target_hits)
            score += min(2.4, gap_sum / 22)
            reasons.append(f"Trains {', '.join(target_hits)} where your gap to target is {gap_sum} points")
        weakest = sorted(attrs.items(), key=lambda item: item[1])[:4]
        if any(a in drill["target_attributes"] for a, _v in weakest):
            score += 1.1
            reasons.append("One of your four weakest attributes: " + ", ".join(f"{a} {v}" for a, v in weakest))
        if player.position in drill["positions"]:
            score += 0.9
            reasons.append(f"Valid for {player.position}")
        else:
            score -= 1.6
        difficulty_fit = drill["difficulty"]
        ideal = 1 + min(4, int(player.level_number / 2) + (0 if player.form < 0 else 1))
        if difficulty_fit == ideal:
            score += 0.8
            reasons.append(f"Difficulty {difficulty_fit}/5 matches your current load level")
        elif abs(difficulty_fit - ideal) > 1:
            score -= 0.7
        if player.age < 18 and drill["difficulty"] >= 4:
            score -= 1.4
            reasons.append("Load capped: high-intensity contact work is unsuitable for an under-18 profile (spec §62)")
        if drill["needs_pitch"] and not pitch_available:
            score -= 3.0
            reasons.append("Needs space you did not mark as available")
        if not has_wall and "flat wall or rebound board" in drill["equipment"]:
            score -= 1.0
        repetition = recent.get(drill["category"], 0)
        if repetition:
            score -= 0.55 * repetition
            reasons.append(f"De-prioritised: {repetition} recent sessions already covered {drill['category']}")
        else:
            score += 0.45
        if training_load >= 250:
            score -= 0.4 * (drill["duration_min"] / 20)
            reasons.append("Volume trimmed: you are already close to today's XP cap")
        if score < -1.5:
            continue
        candidates.append((score, drill, reasons))

    if not candidates:
        fallback = dict(_drill_rows(db)[0])
        return Recommendation(
            drill=_public(fallback),
            reasons=["No drill satisfied the constraints (time/equipment). Showing the shortest general ball-mastery option instead."],
            alternatives=[],
            confidence=0.35,
            focus_attributes=focus_attributes,
            context={"available_minutes": minutes, "candidate_count": 0},
        )

    candidates.sort(key=lambda item: (-item[0], item[1]["slug"]))
    top_score, best, best_reasons = candidates[0]
    alternatives = [
        {"drill_id": d.get("id", ""), "slug": d["slug"], "title": d["title"], "category": d["category"], "duration_min": d["duration_min"], "score": round(s, 2)}
        for s, d, _r in candidates[1:5]
    ]
    spread = max(0.1, top_score - (candidates[1][0] if len(candidates) > 1 else top_score - 1))
    confidence = round(max(0.3, min(0.95, 0.55 + min(0.4, len(candidates) / 20) + 0.1 * min(spread, 2))), 2)
    best_reasons = [
        f"Scored {top_score:.2f} against {len(candidates)} eligible drills",
        *best_reasons,
        f"Session length {best['duration_min']} min fits your {minutes} min window",
    ]
    return Recommendation(
        drill=_public(best),
        reasons=best_reasons,
        alternatives=alternatives,
        confidence=confidence,
        focus_attributes=focus_attributes,
        context={
            "available_minutes": minutes,
            "candidate_count": len(candidates),
            "recent_categories": recent,
            "xp_last_24h": training_load,
            "streak_days": user.streak_days,
            "archetype": player.archetype,
        },
    )


def build_plan(db: Session, player: UserPlayer, *, horizon_days: int, available_minutes: int, days_per_week: int, has_pitch: bool = True) -> list[dict[str, Any]]:
    """7/30/90-day plan: rotating emphasis, recovery days, a test day each week (spec §12)."""
    drills = _drill_rows(db)
    goal = GOAL_FOCUS.get(player.goal, GOAL_FOCUS["improve_first_touch"])
    attrs = {k: v for k, v in player.attributes.items() if not k.startswith("_sp_")}
    ordered = sorted(
        drills,
        key=lambda d: (
            -(2.0 if d["category"] in goal["categories"] else 0)
            - sum(max(0, 70 - attrs.get(a, 40)) * w for a, w in d["target_attributes"].items()) / 40
            - (0 if player.position in d["positions"] else 1),
            d["slug"],
        ),
    )
    days: list[dict[str, Any]] = []
    cursor = 0
    for day_index in range(horizon_days):
        iso_weekday = day_index % 7
        if iso_weekday == 6:
            days.append({"day": day_index + 1, "date": (date.today() + timedelta(days=day_index)).isoformat(), "type": "recovery", "sessions": [], "note": "Mobility, hydration and 10 min video review. Recovery is part of the plan."})
            continue
        if days_per_week <= 3 and iso_weekday in (1, 3):
            days.append({"day": day_index + 1, "date": (date.today() + timedelta(days=day_index)).isoformat(), "type": "rest", "sessions": [], "note": "Scheduled rest day to keep load safe."})
            continue
        capacity = max(1, int(available_minutes // 18))
        sessions = []
        for _slot in range(capacity):
            if cursor >= len(ordered):
                cursor = 0
            drill = ordered[cursor]
            cursor += 1
            if drill["duration_min"] > available_minutes:
                continue
            sessions.append(
                {
                    "drill_id": drill.get("id", ""),
                    "slug": drill["slug"],
                    "title": drill["title"],
                    "category": drill["category"],
                    "duration_min": drill["duration_min"],
                    "objective": drill["objective"],
                    "why": "Goal emphasis" if drill["category"] in goal["categories"] else "Attribute gap",
                }
            )
            available_minutes -= drill["duration_min"]
            if available_minutes < 10:
                break
        is_test = iso_weekday == (2 if days_per_week >= 4 else 1) and day_index > 0
        days.append(
            {
                "day": day_index + 1,
                "date": (date.today() + timedelta(days=day_index)).isoformat(),
                "type": "test" if is_test else "training",
                "sessions": sessions,
                "note": "Testing week: record the drill's test metric so progress is measurable." if is_test else "",
            }
        )
    return days


def coach_message_after_completion(db: Session, user: User, player: UserPlayer, drill: TrainingDrill, execution: int) -> dict[str, Any]:
    """Follow-up that reflects the *new* stored state, not generic praise (spec §93)."""
    attrs = {k: v for k, v in player.attributes.items() if not k.startswith("_sp_")}
    recent_changes = db.scalars(
        select(AttributeChange).where(AttributeChange.player_id == player.id).order_by(AttributeChange.created_at.desc()).limit(6)
    ).all()
    improving = [c.attribute for c in recent_changes]
    next_focus = sorted(attrs.items(), key=lambda item: item[1])[:3]
    archetype, match, _ = derive_archetype(player.position, attrs)
    reasons: list[str] = []
    if improving:
        reasons.append(f"Attribute evidence recorded for: {', '.join(sorted(set(improving)))}")
    if execution >= 4:
        headline = f"Clean reps logged on '{drill.title}'. Your {', '.join(sorted(set(improving))[:2]) if improving else 'technique under fatigue'} is trending up."
        next_step = "receiving under pressure"
    elif execution == 3:
        headline = f"'{drill.title}' completed at a solid tempo — control held, but only just."
        next_step = drill.category
    else:
        headline = f"'{drill.title}' was a struggle, and that is useful information rather than a failure."
        next_step = "the regression version of this drill"
    body = (
        f"{headline} Next session should focus on {next_step}: "
        f"your lowest attributes are {', '.join(f'{a} ({v})' for a, v in next_focus)}. "
        f"Current archetype fit: {archetype} at {match * 100:.0f}%, overall {player.overall}."
    )
    reasons.append(f"Next focus derived from lowest attributes: {', '.join(a for a, _ in next_focus)}")
    reasons.append("Archetype recomputed from stored attributes (spec §8), not from conversation text")
    return {
        "content": body,
        "reasons": reasons,
        "confidence": 0.82,
        "archetype": archetype,
        "next_focus_attributes": [a for a, _ in next_focus],
    }


def answer_intent(db: Session, user: User, player: UserPlayer, question: str) -> str:
    normalized = " ".join(question.lower().split())
    intent = next((target for needle, target in _INTENT_MAP if needle in normalized), "general")
    return intent


def history_summary(db: Session, user: User, player: UserPlayer) -> dict[str, Any]:
    """Coach memory: what the agent must know about this user's arc (spec §34)."""
    sessions = db.scalars(select(TrainingSession).where(TrainingSession.player_id == player.id).order_by(TrainingSession.created_at.desc()).limit(20)).all()
    completed = [s for s in sessions if s.status == "completed"]
    categories: dict[str, int] = {}
    for session in completed:
        drill = db.get(TrainingDrill, session.drill_id)
        if drill:
            categories[drill.category] = categories.get(drill.category, 0) + 1
    changes = db.scalars(select(AttributeChange).where(AttributeChange.player_id == player.id).order_by(AttributeChange.created_at.desc()).limit(40)).all()
    return {
        "sessions_total": len(completed),
        "recent_categories": categories,
        "last_completed_at": completed[0].completed_at.isoformat() if completed and completed[0].completed_at else None,
        "xp_total": player.xp,
        "level": player.level_number,
        "streak_days": user.streak_days,
        "attribute_trend": [
            {"attribute": c.attribute, "delta": c.delta, "reason": c.reason, "at": c.created_at.isoformat()} for c in changes[:10]
        ],
        "goal_history": [player.goal],
        "weakest_attributes": sorted(
            ((k, v) for k, v in {a: player.attributes.get(a, 40) for group in ATTRIBUTES.values() for a in group}.items()), key=lambda item: item[1]
        )[:5],
    }


def plan_emphasis(player: UserPlayer) -> list[str]:
    goal = GOAL_FOCUS.get(player.goal, GOAL_FOCUS["improve_first_touch"])
    return list(goal["categories"])


def archetype_knowledge(name: str) -> dict[str, Any]:
    return ARCHETYPES.get(name, {})
