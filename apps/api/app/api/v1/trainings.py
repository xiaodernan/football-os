"""Training Academy endpoints: catalogue, plan a session, complete it (spec §10–§12)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit, new_public_id, ownership_or_admin
from app.models import TrainingDrill, TrainingSession, User, UserPlayer, utc_today
from app.schemas import CompleteIn, DrillOut, PlanSessionIn
from app.services import coach_engine
from app.services.progression import complete_session

router = APIRouter(prefix="/trainings", tags=["trainings"])


@router.get("/drills", response_model=list[DrillOut])
def list_drills(
    category: str | None = Query(default=None, max_length=40),
    position: str | None = Query(default=None, max_length=8),
    limit_rows: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[DrillOut]:
    stmt = select(TrainingDrill).order_by(TrainingDrill.category, TrainingDrill.title).limit(limit_rows)
    if category:
        stmt = stmt.where(TrainingDrill.category == category)
    rows = db.scalars(stmt).all()
    if position:
        rows = [r for r in rows if position in (r.positions or [])]
    return [DrillOut.model_validate(r) for r in rows]


@router.get("/drills/{drill_id}", response_model=DrillOut)
def get_drill(drill_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)) -> DrillOut:
    drill = db.get(TrainingDrill, drill_id)
    if drill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Drill not found"})
    return DrillOut.model_validate(drill)


def _player_for(db: Session, user: User, player_id: str | None) -> UserPlayer:
    if player_id:
        player = db.get(UserPlayer, player_id)
        if player is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Player not found"})
        ownership_or_admin(user, player.user_id, "player")
        return player
    player = db.scalar(select(UserPlayer).where(UserPlayer.user_id == user.id).order_by(UserPlayer.created_at))
    if player is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "no_player", "message": "Create your player profile first"})
    return player


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def plan_session(
    payload: PlanSessionIn,
    request: Request,
    player_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, object]:
    limit(request, 40, 3600, scope="plan_session")
    player = _player_for(db, user, player_id)
    drill = db.get(TrainingDrill, payload.drill_id)
    if drill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Drill not found"})
    reasons = [
        f"Selected by you from the {drill.category} category",
        f"Targets {', '.join(drill.target_attributes)}",
        f"{drill.duration_min} min fits your {payload.available_minutes} min window",
    ]
    if player.position not in drill.positions:
        reasons.append(f"Note: this drill is usually assigned to {', '.join(drill.positions[:4])}, not {player.position}")
    session = TrainingSession(
        id=new_public_id("ses"),
        user_id=user.id,
        player_id=player.id,
        drill_id=drill.id,
        planned_date=utc_today().isoformat(),
        recommendation_reasons=reasons,
    )
    db.add(session)
    db.commit()
    return {"session_id": session.id, "status": session.status, "drill": DrillOut.model_validate(drill).model_dump(), "reasons": reasons}


@router.post("/sessions/{session_id}/complete")
def complete(
    session_id: str,
    payload: CompleteIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, object]:
    limit(request, 30, 3600, scope="complete_session")
    session = db.get(TrainingSession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "Session not found"})
    ownership_or_admin(user, session.user_id, "session")
    if session.status == "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "already_completed", "message": "This session is already logged"})
    player = db.get(UserPlayer, session.player_id)
    drill = db.get(TrainingDrill, session.drill_id)
    if player is None or drill is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "missing_records", "message": "Session references are incomplete"})
    result = complete_session(
        db,
        user,
        player,
        session,
        drill,
        execution=payload.execution,
        focus=payload.focus,
        difficulty_experience=payload.difficulty_experience,
        self_notes=payload.self_notes,
    )
    feedback = coach_engine.coach_message_after_completion(db, user, player, drill, payload.execution)
    reasons = list(result.xp_formula and [result.xp_formula] or [])
    from app.models import CoachMessage

    db.add(
        CoachMessage(
            id=new_public_id("msg"),
            user_id=user.id,
            player_id=player.id,
            role="coach",
            kind="post_session",
            content=feedback["content"],
            structured={"reasons": feedback["reasons"], "attribute_changes": result.attribute_changes, "skill_progress": result.skill_progress},
            reasons=feedback["reasons"],
            confidence=feedback["confidence"],
        )
    )
    db.commit()
    return {
        "session_id": session.id,
        "status": session.status,
        "xp_awarded": result.xp_awarded,
        "xp_formula": result.xp_formula,
        "attribute_changes": result.attribute_changes,
        "skill_progress": result.skill_progress,
        "player_level": result.level_number,
        "level_changed": result.level_changed,
        "streak_days": result.streak_days,
        "new_achievements": result.new_achievements,
        "form": result.form,
        "player": {
            "id": player.id,
            "overall": player.overall,
            "potential": player.potential,
            "archetype": player.archetype,
            "archetype_match": player.archetype_match,
            "xp": player.xp,
        },
        "coach_feedback": feedback,
        "reasons": reasons,
        "demo_mode": True,
    }


@router.get("/sessions")
def list_sessions(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, object]:
    stmt = select(TrainingSession).where(TrainingSession.user_id == user.id).order_by(TrainingSession.created_at.desc())
    if status_filter:
        stmt = stmt.where(TrainingSession.status == status_filter)
    total = int(db.scalar(select(func.count(TrainingSession.id)).where(TrainingSession.user_id == user.id)) or 0)
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    items = []
    for row in rows:
        drill = db.get(TrainingDrill, row.drill_id)
        items.append(
            {
                "id": row.id,
                "status": row.status,
                "planned_date": row.planned_date,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "xp_awarded": row.xp_awarded,
                "execution_rating": row.execution_rating,
                "focus_quality": row.focus_quality,
                "self_notes": row.self_notes,
                "recommendation_reasons": row.recommendation_reasons,
                # Which program planned this session, when one did. A session the learner planned
                # themselves carries none, and the column says so rather than leaving the reader to
                # guess from the reason text.
                "program_id": row.program_id,
                "drill": {
                    "id": row.drill_id,
                    "slug": drill.slug if drill else None,
                    "title": drill.title if drill else "Data unavailable",
                    "category": drill.category if drill else "Data unavailable",
                    "duration_min": drill.duration_min if drill else 0,
                    "difficulty": drill.difficulty if drill else 0,
                    "test_prompt": drill.test_prompt if drill else "",
                    "test_target": drill.test_target if drill else "",
                },
            }
        )
    return {"items": items, "page": page, "page_size": page_size, "total": total, "demo_data": True}
