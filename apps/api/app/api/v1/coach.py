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
from app.providers import get_llm_provider
from app.schemas import CoachAskIn, PlanIn
from app.services import coach_engine
from app.services.model_ledger import budget_exhausted, record_model_call

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
    structured: dict[str, Any] = {"intent": intent}
    reasons: list[str] = []
    confidence = 0.7
    provider = get_llm_provider()

    if intent in {"today", "plan_7", "plan_30", "plan_90"}:
        horizon = {"plan_7": 7, "plan_30": 30, "plan_90": 90}.get(intent, 1)
        if intent == "today":
            rec = coach_engine.recommend_today(db, user, player, available_minutes=payload.available_minutes, has_pitch=payload.has_pitch)
            structured["recommendation"] = rec.drill
            structured["alternatives"] = rec.alternatives
            structured["message"] = f"Today: {rec.drill['title']}. {rec.drill['objective']}"
            reasons = rec.reasons
            confidence = rec.confidence
        else:
            days = coach_engine.build_plan(db, player, horizon_days=horizon, available_minutes=payload.available_minutes or 25, days_per_week=4, has_pitch=payload.has_pitch)
            structured["plan"] = {"horizon_days": horizon, "days": days}
            structured["message"] = f"{horizon}-day plan built around {player.goal.replace('_', ' ')} with recovery days scheduled."
            reasons = [
                f"Emphasis rotated across {', '.join(coach_engine.plan_emphasis(player)[:4])}",
                "Recovery days inserted so weekly load stays safe",
                "Sessions ordered by attribute gap, weakest first",
            ]
            confidence = 0.78
    elif intent == "weak_foot":
        rec = coach_engine.recommend_today(db, user, player, available_minutes=payload.available_minutes or 15)
        structured["message"] = "Weak-foot work is the fastest route: two short sessions a week beat one long one."
        structured["recommendation"] = rec.drill
        reasons = [
            f"Weak-foot rating stored as {player.weak_foot_rating}",
            "Ball-mastery and wall-pass drills transfer to the weak foot in 4-6 weeks of consistent reps",
        ]
        confidence = 0.74
    elif intent == "ball_loss":
        attrs = player.attributes
        structured["message"] = f"Ball loss usually traces to first touch under pressure, not dribbling. Your first touch is {attrs.get('first_touch', 40)} and composure {attrs.get('composure', 40)}."
        reasons = [
            f"first_touch {attrs.get('first_touch', 40)} vs ball_control {attrs.get('ball_control', 40)} — the lower value is the limiter",
            f"Recent sessions covered: {', '.join(sorted(coach_engine.history_summary(db, user, player)['recent_categories'])) or 'none yet'}",
            "Check whether you are receiving square-on; half-turn receiving removes half the pressure",
        ]
        confidence = 0.7
    elif intent == "role_question":
        knowledge = coach_engine.archetype_knowledge(player.archetype)
        structured["message"] = (
            f"As a {player.position} your current profile reads {player.archetype} ({player.archetype_match * 100:.0f}% fit). "
            f"Priorities: {', '.join(knowledge.get('strengths', ['positional discipline']))}."
        )
        reasons = [
            f"Archetype derived from weighted core attributes: {', '.join(knowledge.get('core', {}).keys())}",
            f"Preferred zones: {', '.join(knowledge.get('zones', ['central_corridor']))}",
            f"Known trade-offs: {', '.join(knowledge.get('weaknesses', ['general development']))}",
            f"Recommended drill categories: {', '.join(knowledge.get('drill_categories', []))}",
        ]
        confidence = 0.8
    elif intent == "pressing":
        attrs = player.attributes
        structured["message"] = f"Pressing is triggered, not attempted. Your pressing {attrs.get('pressing', 40)} and stamina {attrs.get('stamina', 40)} set the ceiling."
        reasons = [
            f"pressing {attrs.get('pressing', 40)} / stamina {attrs.get('stamina', 40)} / transition {attrs.get('transition', 40)}",
            "Train counter-press triggers: lose ball -> 5 seconds of controlled pressure",
            "If the first pressor is beaten, the second must cover the pass, not the dribbler",
        ]
        confidence = 0.72
    elif intent == "match_review":
        structured["message"] = "No match data is stored for your profile yet. Match analysis lands with the video pipeline (M5); until then I will say 'Data unavailable' rather than guess."
        reasons = ["No MatchPerformance rows exist for this player", "Spec §15: unavailable metrics must display 'Data unavailable'"]
        confidence = 0.5
    elif intent == "explain":
        summary = coach_engine.history_summary(db, user, player)
        structured["message"] = f"Your progress is explainable: {summary['sessions_total']} completed sessions, {summary['xp_total']} XP, level {summary['level']}."
        reasons = [r["reason"] for r in summary["attribute_trend"][:5]] or ["No attribute changes recorded yet — complete a session first"]
        confidence = 0.8
    else:
        rec = coach_engine.recommend_today(db, user, player, available_minutes=payload.available_minutes, has_pitch=payload.has_pitch)
        structured["recommendation"] = rec.drill
        structured["message"] = f"Here is the most useful next session: {rec.drill['title']}. {rec.drill['objective']}"
        reasons = rec.reasons
        confidence = rec.confidence

    # §76's cap, gated at the call rather than at the request. The answer above is arithmetic over
    # `user_players` and the training ledger, and the model only phrases it, so a reached cap refuses the
    # phrasing step and ships the arithmetic — the same trade §60's answer table records as
    # `ai_budget_exhausted` ("Retrieval still works"), applied to a door that has no separate retrieval.
    # In demo mode the provider is the mock and costs nothing, so the ledger's actual spend stays at zero
    # and this never fires there: a cap measured in real dollars cannot bind a free run.
    spend_capped = budget_exhausted(db)
    if spend_capped:
        result = None
    else:
        result = provider.complete(
            system="You phrase football coaching guidance in short sentences. Never invent data.",
            prompt=str({"intent": intent, "facts": structured.get("message", "")}),
        )
    content = structured.get("message", "")
    if result is not None and not result.demo_mode and result.text.strip():
        content = f"{content}\n\n{result.text.strip()}"
    if spend_capped:
        reasons = [*reasons, "Today's AI spend cap is reached, so the phrasing step was skipped; every figure above is still computed from your stored profile and history"]
    db.add(
        CoachMessage(
            id=new_public_id("msg"),
            user_id=user.id,
            player_id=player.id,
            role="coach",
            kind=f"answer:{intent}",
            content=content,
            structured={"reasons": reasons, "provider_text": result.text if result is not None and not result.demo_mode else None},
            provider=result.provider if result is not None else "mock",
            model=result.model if result is not None else "rule-engine-demo",
            demo_mode=result.demo_mode if result is not None else settings.is_demo_mode,
            confidence=confidence,
            reasons=reasons,
        )
    )
    if result is not None:
        record_model_call(db, result=result, feature="coach.ask", user_id=user.id)
    db.commit()
    # The envelope names the provider that answered. A capped turn is answered by the rule engine alone,
    # which is what the CoachMessage defaults already say — the door keeps one vocabulary for "no model
    # was called" rather than inventing a second one for the capped path.
    return _envelope(
        reasons,
        confidence,
        result.provider if result is not None else "mock",
        result.model if result is not None else "rule-engine-demo",
        result.demo_mode if result is not None else settings.is_demo_mode,
        {**structured, "message": content, "question": payload.question},
    )


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
