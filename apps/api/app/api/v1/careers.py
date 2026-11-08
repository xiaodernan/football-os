"""Career endpoints (M6, spec §20).

The wall is the same one §61 puts on boards, clips and stored matches: the *knobs* are public fiction
(clubs, tactical systems, the objective kinds), while a career and its rounds belong to the account
that opened them and read back only to their owner — a foreign slug is a 404, not a 403.

A response never carries a bare number without the sentence that made it: the record states its
formula, the table says it is built from this career's fixtures only, each objective prints the kind
it measures, and `limitations` says in plain words that the budget and the philosophy label do not
yet reach the engine.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit, ownership_or_admin
from app.models import CAREER_PHLOSOPHIES, OBJECTIVE_FORMULA, OBJECTIVE_KINDS, Career, User
from app.services.club import answers
from app.services.simulation.career import (
    CAREER_DISCLAIMER,
    WindowClosed,
    career_summary,
    career_view,
    create_career,
    next_fixture_plan,
    play_round,
    resolve_club,
)
from app.services.simulation.challenges import verdict_of
from app.services.simulation.cup import CupRefusal, cup_tie_row, cup_view, play_cup_tie
from app.services.simulation.ledger import ledger_view
from app.services.simulation.market import (
    STADIUM_MAX_SEATS,
    MarketRefusal,
    buy_season_tickets,
    buy_seats,
    buy_training_level,
    season_ticket_row,
    season_ticket_view,
    set_ticket_price,
    stadium_row,
    ticket_price_view,
    training_row,
    training_view,
)
from app.services.simulation.service import options, system_options
from app.services.tactics.plan import system_by_slug

router = APIRouter(prefix="/careers", tags=["career"])

NOT_FOUND = {"code": "not_found", "message": "No such career for this account"}
MAX_CAREERS_PER_USER = 5
BUDGET_CEILING = 10_000_000


class ObjectiveIn(BaseModel):
    kind: str = Field(min_length=2, max_length=24)
    target: int = Field(ge=-100, le=500)
    label: str | None = Field(default=None, max_length=120)


class CareerIn(BaseModel):
    club: str = Field(min_length=1, max_length=160)
    manager_name: str = Field(min_length=2, max_length=80)
    philosophy: str = Field(default="balanced", max_length=20)
    system: str | None = Field(default=None, max_length=160)
    budget: int = Field(default=1_000_000, ge=0, le=BUDGET_CEILING)
    # The board's cap on one round's wage bill. 0 is "no cap", the same convention the platform's other
    # ceilings use; a stated cap is enforced by buy and loan and previewed in every signing block.
    wage_ceiling: int = Field(default=0, ge=0, le=BUDGET_CEILING)
    objectives: list[ObjectiveIn] = Field(default_factory=list, max_length=4)
    season: str = Field(default="2026", max_length=12)


class CupIn(BaseModel):
    """Which cup to play when a career is entered in more than one. Omitted, the first live run plays."""

    cup: str | None = Field(default=None, max_length=160)


class StadiumIn(BaseModel):
    """How many seats to add to this career's ground in one purchase."""

    seats: int = Field(ge=1, le=STADIUM_MAX_SEATS)


class TicketPriceIn(BaseModel):
    """The manager's gate price as a percentage of the competition's own (100 leaves it unchanged)."""

    price_pct: int = Field(ge=0, le=1_000)


class SeasonTicketsIn(BaseModel):
    """How many seats to sell for this season before its first round."""

    seats: int = Field(ge=0, le=100_000)


class TrainingIn(BaseModel):
    """How many levels to buy for the training ground (bounded by the current level)."""

    levels: int = Field(ge=0, le=10)


def _career(db: Session, user: User, ident: str) -> Career:
    row = db.scalar(select(Career).where(Career.slug == ident)) or db.scalar(select(Career).where(Career.id == ident))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    ownership_or_admin(user, row.owner_id, "career")
    return row


def _guard(payload: CareerIn, db: Session) -> tuple[Any, list[dict[str, Any]]]:
    club = resolve_club_or_404(db, payload.club)
    if payload.philosophy not in CAREER_PHLOSOPHIES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "bad_philosophy", "message": f"philosophy must be one of {list(CAREER_PHLOSOPHIES)}"},
        )
    if payload.system and system_by_slug(payload.system) is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "no_such_system", "message": f"system {payload.system!r} is not one of the 50 authored tactical systems"},
        )
    objectives: list[dict[str, Any]] = []
    for objective in payload.objectives:
        if objective.kind not in OBJECTIVE_KINDS:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "bad_objective", "message": f"objective kind {objective.kind!r} is not one of {list(OBJECTIVE_KINDS)}"},
            )
        objectives.append({"kind": objective.kind, "target": objective.target, "label": objective.label or objective.kind})
    if not objectives:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "no_objectives", "message": "a career needs at least one objective to be judged by", "see": list(OBJECTIVE_KINDS)},
        )
    return club, objectives


def resolve_club_or_404(db: Session, ident: str) -> Any:
    try:
        return resolve_club(db, ident)
    except ValueError:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "no_such_club", "message": f"{ident!r} is not a club in the generated world", "see": "/api/v1/careers/options"},
        ) from None


@router.get("/options")
def read_options(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """What a career can be built from: the clubs, the systems, and the objective kinds with their formulas."""
    limit(request, 60, 60, scope="career_options")
    return {
        "clubs": options(db),
        "systems": system_options(),
        "philosophies": list(CAREER_PHLOSOPHIES),
        "objective_kinds": {kind: OBJECTIVE_FORMULA[kind] for kind in OBJECTIVE_KINDS},
        "budget_ceiling": BUDGET_CEILING,
        "budget_units": "career credits",
        "wage_ceiling_units": "career credits per round",
        "max_careers_per_user": MAX_CAREERS_PER_USER,
        "data_origin": "simulation",
        "is_demo_data": True,
        "disclaimer": CAREER_DISCLAIMER,
    }


@router.post("")
def open_career(payload: CareerIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 10, 60, scope="career_create")
    club, objectives = _guard(payload, db)
    owned = int(db.scalar(select(func.count(Career.id)).where(Career.owner_id == user.id)) or 0)
    if owned >= MAX_CAREERS_PER_USER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={"code": "career_limit", "message": f"this account already has {owned} of {MAX_CAREERS_PER_USER} careers; retire one before opening another"},
        )
    career = create_career(
        db,
        owner_id=user.id,
        club=club,
        manager_name=payload.manager_name,
        philosophy=payload.philosophy,
        system_slug=payload.system or "",
        budget=payload.budget,
        objectives=objectives,
        wage_ceiling=payload.wage_ceiling,
        season=payload.season,
    )
    return {"created": True, **career_view(db, career)}


@router.get("")
def list_careers(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 30, 60, scope="career_list")
    rows = list(db.scalars(select(Career).where(Career.owner_id == user.id).order_by(Career.created_at.desc())).all())
    items = []
    for career in rows:
        summary = career_summary(db, career)
        items.append(summary["career"] | {"record": summary["record"], "objectives_met": sum(1 for item in summary["objectives"] if item["met"]), "objectives_total": len(summary["objectives"])})
    return {
        "items": items,
        "total": len(items),
        "limit_per_user": MAX_CAREERS_PER_USER,
        "data_origin": "simulation",
        "is_demo_data": True,
        "demo_data": True,
        "disclaimer": CAREER_DISCLAIMER,
    }


@router.get("/{ident}")
def read_career(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 60, 60, scope="career_detail")
    career = _career(db, user, ident)
    return career_view(db, career)


@router.post("/{ident}/play")
def play_next(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Play the career's next round with the engine, then re-derive everything the page shows.

    A career opened from a live challenge stops here once its window is used. That is the scenario
    working, not a failure, so it answers `window_closed` with the rounds that closed it rather than a
    generic refusal — and the run's own view is beside it, so the page can show the final verdict
    instead of an error with nothing to read.
    """
    limit(request, 20, 60, scope="career_play")
    career = _career(db, user, ident)
    plan = next_fixture_plan(db, career)
    if not plan["available"]:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "no_fixture", "message": str(plan["reason"])})
    try:
        fixture, match = play_round(db, career)
    except WindowClosed as error:
        raise HTTPException(
            answers.ANSWERS.get(error.code, status.HTTP_409_CONFLICT),
            detail={**error.to_dict(), "verdict": _challenge_verdict(db, career)},
        ) from None
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "cannot_play", "message": str(error)}) from None
    return {
        "played": True,
        "fixture_id": fixture.id,
        "match": {"slug": match.slug, "path": f"/simulate/{match.slug}", "digest": match.digest, "seed": match.seed, "model_version": match.model_version},
        **career_view(db, career),
        "challenge_verdict": _challenge_verdict(db, career),
    }


def _challenge_verdict(db: Session, career: Career) -> dict[str, Any] | None:
    """The live verdict, but only for a career that is actually playing a scenario.

    Read from the run's own fixture rows: the play response already carries the whole career view, and
    building a second one to return this dictionary made every play read the career tables twice.
    """
    return verdict_of(db, career)


@router.post("/{ident}/cup")
def play_cup(ident: str, request: Request, payload: CupIn | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Play the career's next cup tie with the engine, then re-derive everything the page shows.

    A tie is not a league round: it does not advance `rounds_played`, score points or close a season. It is
    the world's own knockout bracket (item 32), and the career's result replaces the slot the world's
    simulation filled. A run that is over, a cup the career is not entered in and a challenge career each
    answer 409 with the sentence that says why rather than inventing a fixture.
    """
    limit(request, 20, 60, scope="career_cup")
    career = _career(db, user, ident)
    try:
        tie, match = play_cup_tie(db, career, cup=payload.cup if payload is not None else None)
    except CupRefusal as error:
        raise HTTPException(answers.ANSWERS.get(error.code, status.HTTP_409_CONFLICT), detail={**error.to_dict(), "cup": cup_view(db, career)}) from None
    except ValueError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={"code": "cannot_play_cup", "message": str(error)}) from None
    return {
        "played": True,
        "tie": cup_tie_row(tie),
        "match": {"slug": match.slug, "path": f"/simulate/{match.slug}", "digest": match.digest, "seed": match.seed, "model_version": match.model_version},
        **career_view(db, career),
    }


@router.post("/{ident}/stadium")
def build_stand(ident: str, payload: StadiumIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Buy seats for this career's ground (M13 Phase 9 item 37).

    One purchase at a time, priced and capped by the market's own rules, and written as a ledger row
    whose `budget_after` the finance page can check. The whole career view comes back, because a stand
    changes the balance, the timeline and the gate the next home round will read.
    """
    limit(request, 20, 60, scope="career_stadium")
    career = _career(db, user, ident)
    try:
        work, _stadium = buy_seats(db, career, seats=payload.seats)
    except MarketRefusal as error:
        raise HTTPException(answers.ANSWERS.get(error.code, status.HTTP_409_CONFLICT), detail=error.to_dict()) from None
    return {"built": True, "work": stadium_row(work), **career_view(db, career)}


@router.get("/{ident}/tickets")
def tickets(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The gate price this career has set and the demand and revenue it indexes (M13 Phase 10 item 44)."""
    limit(request, 60, 60, scope="career_tickets")
    career = _career(db, user, ident)
    return ticket_price_view(db, career)


@router.put("/{ident}/tickets")
def price_tickets(ident: str, payload: TicketPriceIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Set the gate price and answer with the whole career view the finance page reads.

    The service owns the bounds and the step so the refusal names `bad_ticket_price` with the figures
    that decided it, rather than a body-validation message the page cannot translate.
    """
    limit(request, 20, 60, scope="career_tickets")
    career = _career(db, user, ident)
    try:
        view = set_ticket_price(db, career, price_pct=payload.price_pct)
    except MarketRefusal as error:
        raise HTTPException(answers.ANSWERS.get(error.code, status.HTTP_409_CONFLICT), detail=error.to_dict()) from None
    return {"priced": True, "tickets": view, **career_view(db, career)}


@router.get("/{ident}/season-tickets")
def season_tickets(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """This season's season-ticket offer, its price and every sale already made (item 46)."""
    limit(request, 60, 60, scope="career_season_tickets")
    career = _career(db, user, ident)
    return season_ticket_view(db, career)


@router.post("/{ident}/season-tickets")
def sell_season_tickets(ident: str, payload: SeasonTicketsIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Sell one season's allocation before its first round and answer with the sale and career view."""
    limit(request, 20, 60, scope="career_season_tickets")
    career = _career(db, user, ident)
    try:
        sale, _view = buy_season_tickets(db, career, seats=payload.seats)
    except MarketRefusal as error:
        raise HTTPException(answers.ANSWERS.get(error.code, status.HTTP_409_CONFLICT), detail=error.to_dict()) from None
    return {"sold": True, "sale": season_ticket_row(sale), **career_view(db, career)}


@router.get("/{ident}/training")
def training(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The training ground's level, its bonus and every upgrade already bought (item 47)."""
    limit(request, 60, 60, scope="career_training")
    career = _career(db, user, ident)
    return training_view(db, career)


@router.post("/{ident}/training")
def build_training(ident: str, payload: TrainingIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Buy levels for the training ground and answer with the rows, the new level and the career view."""
    limit(request, 20, 60, scope="career_training")
    career = _career(db, user, ident)
    try:
        rows, _view = buy_training_level(db, career, levels=payload.levels)
    except MarketRefusal as error:
        raise HTTPException(answers.ANSWERS.get(error.code, status.HTTP_409_CONFLICT), detail=error.to_dict()) from None
    return {"built": True, "levels": [training_row(row) for row in rows], **career_view(db, career)}


@router.post("/{ident}/retire")
def retire(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 10, 60, scope="career_retire")
    career = _career(db, user, ident)
    career.status = "active" if career.status == "retired" else "retired"
    db.commit()
    db.refresh(career)
    return {"status": career.status, **career_view(db, career)}


@router.delete("/{ident}")
def delete_career(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Remove the career and its rounds. The match reports it played stay in `/simulate`, because the
    account chose to play them and may still want to read them; the career's own view says so."""
    limit(request, 10, 60, scope="career_delete")
    career = _career(db, user, ident)
    slug = career.slug
    db.delete(career)
    db.commit()
    return {"deleted": True, "slug": slug, "matches_kept": True, "disclaimer": CAREER_DISCLAIMER}


@router.get("/{ident}/ledger")
def read_ledger(
    ident: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """This career's season ledger, summed from sim_events of its fixtures.

    The ledger is a pure read: every figure is summed from sim_events rows at request
    time, and the consistency check compares the same season's goals from the event
    rows against the career's own fixture list.
    """
    limit(request, 60, 60, scope="career_ledger")
    career = _career(db, user, ident)
    return ledger_view(db, career)
