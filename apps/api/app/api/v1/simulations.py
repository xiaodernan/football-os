"""Simulation endpoints (M6, spec §19, §20, §59, §61).

Two doors, and the line between them is the one §19 draws. `GET /simulate/options` is public because
the clubs and the tactical systems are the project's own fiction, already readable under `/world/*`.
Playing a match is not public: a stored match is an account's action, so `POST /simulate` needs a
session and the list and the detail read back only to their owner — the same shape §61 puts on boards
and clips, with `ownership_or_admin` so a foreign id reads as 404 rather than 403.

Every response carries the engine's fictional sentence, the note that its coefficients were authored
rather than fitted, and the seed that reproduces the row. A client that renders a scoreline from here
without those three has the payload wrong, not the model.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit, ownership_or_admin
from app.models import SimulationMatch, Team, User
from app.services.simulation.service import (
    MINUTES_CHOICES,
    SIM_LIMIT_PER_USER,
    engine_description,
    options,
    replay_is_identical,
    row,
    run_simulation,
    sim_counts,
    sim_ready,
    system_options,
)
from app.services.tactics.plan import system_by_slug

router = APIRouter(prefix="/simulate", tags=["simulation"])

NOT_FOUND = {"code": "not_found", "message": "No such simulation for this account"}


class SimulateIn(BaseModel):
    home_team: str = Field(min_length=1, max_length=160)
    away_team: str = Field(min_length=1, max_length=160)
    home_system: str | None = Field(default=None, max_length=160)
    away_system: str | None = Field(default=None, max_length=160)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    minutes: int = Field(default=90)


def _team(db: Session, ident: str) -> Team:
    """Resolve a club by id or slug, the way every world route does."""
    team = db.scalar(select(Team).where(or_(Team.id == ident, Team.slug == ident)))
    if team is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "no_such_team", "message": f"{ident!r} is not a club in the generated world", "see": "/api/v1/simulate/options"},
        )
    return team


def _guard(payload: SimulateIn, db: Session) -> tuple[Team, Team]:
    """Refuse before playing: odd minutes, the same club twice, an unknown club or system.

    Each refusal names what it looked for, because a 400 that only says "invalid" leaves a client
    guessing, and both lists are enumerable right here in the database.
    """
    if payload.minutes not in MINUTES_CHOICES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "bad_minutes", "message": f"minutes must be one of {list(MINUTES_CHOICES)}"},
        )
    home, away = _team(db, payload.home_team), _team(db, payload.away_team)
    if home.id == away.id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "same_team", "message": "a fixture needs two different clubs; the model has no self-play"},
        )
    for slug, label in ((payload.home_system, "home_system"), (payload.away_system, "away_system")):
        if slug and system_by_slug(slug) is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"code": "no_such_system", "message": f"{label} {slug!r} is not one of the 50 authored tactical systems"},
            )
    return home, away


@router.get("/options")
def read_options(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """What can be played: every club, every authored system, and what the engine claims about itself."""
    limit(request, 60, 60, scope="simulate_options")
    engine = engine_description()
    return {
        "teams": options(db),
        "systems": system_options(),
        "engine": engine,
        "ready": sim_ready(db),
        "counts": sim_counts(db),
        "data_origin": "synthetic",
        "disclaimer": engine["disclaimer"],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def play(
    payload: SimulateIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Play a fixture from the two clubs' stored squads and keep the report."""
    limit(request, 20, 60, scope="simulate_create")
    home, away = _guard(payload, db)
    owned = int(db.scalar(select(func.count()).select_from(SimulationMatch).where(SimulationMatch.owner_id == user.id)) or 0)
    if owned >= SIM_LIMIT_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "code": "simulation_limit",
                "message": f"{SIM_LIMIT_PER_USER} stored simulations per account is the current ceiling",
                "delete": "DELETE /api/v1/simulate/{id}",
            },
        )
    try:
        match = run_simulation(
            db,
            owner_id=user.id,
            home_team_id=home.id,
            away_team_id=away.id,
            home_system=payload.home_system,
            away_system=payload.away_system,
            seed=payload.seed,
            minutes=payload.minutes,
        )
    except LookupError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "no_such_input", "message": str(error)}) from error
    return row(match, full=True)


@router.get("")
def list_simulations(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """The account's own matches, newest first, each with the seed that replays it."""
    limit(request, 60, 60, scope="simulate_list")
    matches = db.scalars(select(SimulationMatch).where(SimulationMatch.owner_id == user.id).order_by(SimulationMatch.created_at.desc())).all()
    return {
        "items": [row(match) for match in matches],
        "total": len(matches),
        "limit_per_user": SIM_LIMIT_PER_USER,
        "engine": engine_description(),
        "data_origin": "simulation",
        "disclaimer": engine_description()["disclaimer"],
    }


def _one(db: Session, user: User, ident: str) -> SimulationMatch:
    match = db.scalar(select(SimulationMatch).where(or_(SimulationMatch.slug == ident, SimulationMatch.id == ident)))
    if match is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    ownership_or_admin(user, match.owner_id, "simulation")
    return match


@router.get("/{ident}")
def read_simulation(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 60, 60, scope="simulate_read")
    return row(_one(db, user, ident), full=True)


@router.get("/{ident}/replay")
def replay(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Play the stored match again from its stored inputs and report whether it came out the same.

    This is what spec §19 asks of a simulation: not that it is accurate, but that it is honest about
    being a model and reproducible in its own terms. If the engine ever changes without its version
    number moving, this is the check that stops matching.
    """
    limit(request, 20, 60, scope="simulate_replay")
    return replay_is_identical(db, _one(db, user, ident))


@router.delete("/{ident}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_simulation(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> None:
    limit(request, 20, 60, scope="simulate_delete")
    match = _one(db, user, ident)
    db.delete(match)
    db.commit()
