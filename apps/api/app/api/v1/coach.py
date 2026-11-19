"""AI Coach endpoints (spec §9, §12, §34, §52)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import current_user, limit, new_public_id, ownership_or_admin
from app.models import CoachMessage, TrainingDrill, User, UserPlayer
from app.schemas import CoachAskIn, PlanIn
from app.services import coach_engine
from app.services.agents.coach_graph import run_coach_graph

router = APIRouter(prefix="/coach", tags=["coach"])

DISCLAIMER = "AI coach output is an estimate for training purposes. It is not medical, scouting or performance certification."


def _player(db: Session, user: User, player_id: str | None) -> UserPlayer:
    if player_id:
        player = db.get(UserPlayer, player_id)
    else:
        player = db.scalar(select(UserPlayer).where(UserPlayer.user_id == user.id).order_by(UserPlayer.created_at))
    if player is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "no_player", "message": "Create your player profile first"})
    ownership_or_admin(user, player.user_id, "player")
    return player


def _envelope(reasons: list[str], confidence: float, provider_name: str, model: str, demo: bool, structured: dict[str, Any]) -> dict[str, Any]:
    return {
        "demo_mode": demo,
        "provider": provider_name,
        "model": model,
        "confidence": confidence,
        "reasons": reasons,
        "sources": [{"type": "stored_state", "ref": "user_player", "label": "Your player profile, training history and XP ledger"}],
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": DISCLAIMER,
        **structured,
    }


@router.get("/today")
def today(
    request: Request,
    player_id: str | None = Query(default=None),
    available_minutes: int | None = Query(default=None, ge=5, le=180),
    has_pitch: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 60, 3600, scope="coach_today")
    player = _player(db, user, player_id)
    rec = coach_engine.recommend_today(db, user, player, available_minutes=available_minutes, has_pitch=has_pitch)
    content = f"Today: {rec.drill['title']} ({rec.drill['duration_min']} min, difficulty {rec.drill['difficulty']}/5). Objective — {rec.drill['objective']}"
    message = CoachMessage(
        id=new_public_id("msg"),
        user_id=user.id,
        player_id=player.id,
        role="coach",
        kind="today_recommendation",
        content=content,
        structured={"drill_slug": rec.drill["slug"], "confidence": rec.confidence},
        reasons=rec.reasons,
        confidence=rec.confidence,
    )
    db.add(message)
    db.commit()
    return _envelope(
        rec.reasons,
        rec.confidence,
        "rule-engine",
        "weighted-decision-v1",
        settings.is_demo_mode,
        {
            "message": content,
            "recommendation": rec.drill,
            "alternatives": rec.alternatives,
            "focus_attributes": rec.focus_attributes,
            "context": rec.context,
            "player": {"overall": player.overall, "archetype": player.archetype, "goal": player.goal, "streak_days": user.streak_days},
        },
    )


@router.post("/ask")
def ask(
    payload: CoachAskIn,
    request: Request,
    player_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 20, 3600, scope="coach_ask")
    player = _player(db, user, player_id)
    intent = coach_engine.answer_intent(db, user, player, payload.question)
    db.add(
        CoachMessage(
            id=new_public_id("msg"),
            user_id=user.id,
            player_id=player.id,
            role="user",
            kind=f"intent:{intent}",
            content=payload.question,
        )
    )
    graph = run_coach_graph(
        db,
        user,
        player,
        question=payload.question,
        available_minutes=payload.available_minutes,
        has_pitch=payload.has_pitch,
    )
    intent = graph["intent"]
    reasons = graph["reasons"]
    confidence = graph["confidence"]
    provider_name = graph["provider"]
    model_name = graph["model"]
    demo_mode = graph["demo_mode"]
    structured = dict(graph["structured"])
    content = structured.pop("message", "")
    structured = {**structured, "message": content, "question": payload.question}

    # The envelope names the provider that answered. A capped turn is answered by the rule engine alone,
    # which is what the CoachMessage defaults already say — the door keeps one vocabulary for "no model
    # was called" rather than inventing a second one for the capped path.
    telemetry = {
        "input_tokens": graph.get("input_tokens", 0),
        "cached_input_tokens": graph.get("cached_input_tokens", 0),
        "cache_reported": graph.get("cache_reported", False),
        "output_tokens": graph.get("output_tokens", 0),
        "latency_ms": graph.get("latency_ms", 0),
    }
    return {
        **_envelope(
            reasons,
            confidence,
            provider_name,
            model_name,
            demo_mode,
            structured,
        ),
        **telemetry,
    }


@router.get("/history")
def history(player_id: str | None = Query(default=None), db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    player = _player(db, user, player_id)
    rows = db.scalars(select(CoachMessage).where(CoachMessage.user_id == user.id).order_by(CoachMessage.created_at).limit(200)).all()
    return {
        "items": [
            {
                "id": m.id,
                "role": m.role,
                "kind": m.kind,
                "content": m.content,
                "reasons": m.reasons,
                "confidence": m.confidence,
                "demo_mode": m.demo_mode,
                "provider": m.provider,
                "model": m.model,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ],
        "memory": coach_engine.history_summary(db, user, player),
        "disclaimer": DISCLAIMER,
    }


@router.post("/plan")
def plan(
    payload: PlanIn,
    request: Request,
    player_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 10, 3600, scope="coach_plan")
    player = _player(db, user, player_id)
    days = coach_engine.build_plan(
        db,
        player,
        horizon_days=payload.horizon_days,
        available_minutes=payload.available_minutes,
        days_per_week=payload.days_per_week,
        has_pitch=payload.has_pitch,
    )
    reasons = [
        f"Emphasis set by goal '{player.goal}'",
        "Recovery day inserted every 7th day; rest days follow your chosen weekly frequency",
        "Sessions ordered by attribute gap so the weakest relevant attributes come first",
        "Test days scheduled weekly so improvement is measurable, not assumed",
    ]
    from app.models import TrainingPlan

    db.add(
        TrainingPlan(
            id=new_public_id("pln"),
            user_id=user.id,
            player_id=player.id,
            horizon_days=payload.horizon_days,
            goal=player.goal,
            days=days,
            reasons=reasons,
            demo_mode=settings.is_demo_mode,
        )
    )
    db.commit()
    return _envelope(
        reasons,
        0.78,
        "rule-engine",
        "plan-builder-v1",
        settings.is_demo_mode,
        {"horizon_days": payload.horizon_days, "days": days, "goal": player.goal},
    )


@router.get("/drills/{drill_slug}/knowledge")
def drill_knowledge(drill_slug: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    drill = db.scalar(select(TrainingDrill).where(TrainingDrill.slug == drill_slug))
    if drill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Drill not found"})
    return DrillOutPayload(drill).as_dict()


class DrillOutPayload:
    def __init__(self, drill: TrainingDrill) -> None:
        self.drill = drill

    def as_dict(self) -> dict[str, Any]:
        d = self.drill
        return {
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
            "video": d.video_ref or "Data unavailable",
            "is_demo_data": d.is_demo_data,
        }
