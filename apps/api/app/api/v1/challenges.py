"""Manager live challenge endpoints (M6, spec §21).

The catalogue is public because it is authored fiction about nothing in particular — the six scenarios,
their windows, their goals and what their constraints do. A *run* is not: it is a career, and §61 puts
it behind the same wall as every other career, clip and board, so a foreign slug is a 404 rather than
a 403.

Two design points worth stating, because they are what make the feature more than a label:

* **Playing is not a challenge route.** A run's rounds are played through `POST /careers/{ident}/play`,
  which enforces the window in `career.play_round`. There is one play path and one place a limit can be
  applied, so a challenge cannot be extended by reaching for a different endpoint.
* **The verdict is never stored.** `verdict_for` recomputes the goals, the rounds remaining and the
  reward from the run's own fixture rows on every read, so the numbers on this response and the numbers
  in the run's fixture list cannot disagree.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit, ownership_or_admin
from app.models import OBJECTIVE_FORMULA, Career, User
from app.services.simulation.career import next_fixture_plan
from app.services.simulation.challenges import (
    CHALLENGE_DISCLAIMER,
    CHALLENGES,
    REWARD_UNITS,
    VERDICT_STATUSES,
    challenge_by_slug,
    challenge_problems,
    competition_options,
    fingerprint,
    limitations,
    resolve_challenge_club,
    run_view,
    start_run,
)
from app.services.simulation.service import options as club_options
from app.services.simulation.service import system_options
from app.services.tactics.plan import system_by_slug

router = APIRouter(prefix="/challenges", tags=["challenges"])

NOT_FOUND = {"code": "not_found", "message": "No such challenge run for this account"}
MAX_RUNS_PER_USER = 5


class StartIn(BaseModel):
    """What a caller may choose. The window, the budget, the objectives and the philosophy are not here."""

    manager_name: str = Field(min_length=2, max_length=80)
    club: str | None = Field(default=None, max_length=160)
    competition: str | None = Field(default=None, max_length=160)
    system: str | None = Field(default=None, max_length=160)
    season: str = Field(default="2026", max_length=12)


def _run(db: Session, user: User, ident: str) -> Career:
    row = db.scalar(select(Career).where(Career.slug == ident, Career.challenge_slug != ""))
    if row is None:
        row = db.scalar(select(Career).where(Career.id == ident, Career.challenge_slug != ""))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    ownership_or_admin(user, row.owner_id, "challenge run")
    return row


@router.get("")
def read_catalogue(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The six scenarios, what each one asks of you, and how a verdict is decided.

    `objective_formulas` is shipped beside the scenarios rather than left to the reader, so a target of
    "thirty points" comes with the sentence that will be compared against it.
    """
    limit(request, 60, 60, scope="challenge_catalogue")
    return {
        "challenges": [challenge.to_dict() for challenge in CHALLENGES],
        "total": len(CHALLENGES),
        "fingerprint": fingerprint(),
        "integrity": {"problems": challenge_problems(), "clean": not challenge_problems()},
        "objective_formulas": {kind: OBJECTIVE_FORMULA[kind] for kind in sorted(OBJECTIVE_FORMULA)},
        "verdict_statuses": list(VERDICT_STATUSES),
        "how_a_verdict_is_decided": (
            "A run is in_progress while rounds remain, met when its window has closed and every objective is reached, "
            "and missed when the window closed with at least one objective short. The reward is earned only by met."
        ),
        "window_enforced_by": "career.play_round, the only path that can play a round; a closed window answers 409 window_closed",
        "play_through": "POST /api/v1/careers/{ident}/play — a run's rounds are played through the career route",
        "clubs": club_options(db),
        # A `weakest` scenario needs the caller to name a competition, so the choice it can name — and
        # how many clubs each one holds — is published beside it rather than left to /world.
        "competitions": competition_options(db),
        "systems": system_options(),
        "reward_units": REWARD_UNITS,
        "max_runs_per_user": MAX_RUNS_PER_USER,
        "limitations": limitations(),
        "data_origin": "simulation",
        "is_demo_data": True,
        "demo_data": True,
        "disclaimer": CHALLENGE_DISCLAIMER,
    }


@router.post("/{slug}/start", status_code=status.HTTP_201_CREATED)
def start(slug: str, payload: StartIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Open a run of a scenario: the weakest club in a competition, or a club you name."""
    limit(request, 10, 60, scope="challenge_start")
    challenge = challenge_by_slug(slug)
    if challenge is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "no_such_challenge", "message": f"{slug!r} is not one of the {len(CHALLENGES)} authored challenges", "see": "/api/v1/challenges"},
        )
    if payload.system and system_by_slug(payload.system) is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "no_such_system", "message": f"system {payload.system!r} is not one of the 50 authored tactical systems"},
        )
    owned = int(db.scalar(select(func.count(Career.id)).where(Career.owner_id == user.id, Career.challenge_slug != "")) or 0)
    if owned >= MAX_RUNS_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "run_limit", "message": f"this account already has {owned} of {MAX_RUNS_PER_USER} challenge runs; delete one before starting another"},
        )
    try:
        club, choice = resolve_challenge_club(db, challenge, club=payload.club, competition=payload.competition)
    except ValueError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "cannot_choose_club", "message": str(error), "selector": challenge.club_selector}) from None
    career = start_run(
        db,
        challenge,
        owner_id=user.id,
        club=club,
        manager_name=payload.manager_name,
        system_slug=payload.system or "",
        season=payload.season,
    )
    return {
        "started": True,
        "club_choice": choice,
        "next_fixture": next_fixture_plan(db, career),
        **run_view(db, career),
    }


@router.get("/runs")
def list_runs(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """This account's runs, each with the verdict recomputed from its own rows."""
    limit(request, 30, 60, scope="challenge_runs")
    rows = list(db.scalars(select(Career).where(Career.owner_id == user.id, Career.challenge_slug != "").order_by(Career.created_at.desc())).all())
    items = []
    for career in rows:
        view = run_view(db, career, include_fixtures=False)
        items.append(
            {
                "id": career.id,
                "slug": career.slug,
                "challenge_slug": career.challenge_slug,
                "challenge_name": (view.get("challenge") or {}).get("name") or career.challenge_slug,
                "club_name": career.club_name,
                "season": career.season,
                "rounds_played": career.rounds_played,
                "verdict": view["verdict"],
            }
        )
    return {
        "items": items,
        "total": len(items),
        "limit_per_user": MAX_RUNS_PER_USER,
        "verdict_statuses": list(VERDICT_STATUSES),
        "limitations": limitations(),
        "data_origin": "simulation",
        "is_demo_data": True,
        "demo_data": True,
        "disclaimer": CHALLENGE_DISCLAIMER,
    }


@router.get("/runs/{ident}")
def read_run(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """One run in full: the scenario, the club it gave you, the verdict, and the fixtures behind it."""
    limit(request, 60, 60, scope="challenge_run_detail")
    career = _run(db, user, ident)
    return {"next_fixture": next_fixture_plan(db, career), **run_view(db, career)}


__all__ = ["router"]
