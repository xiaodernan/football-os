"""Scout endpoints (M7, spec §23).

Three doors, and the wall is the one §61 puts on everything else in this project:

* `GET /scout/rules` is public. The vocabulary, the money reading, the sortings and the two band
  vocabularies this project disagrees with itself about are authored fiction about generated rows, and a
  reader should be able to learn what the parser understands *before* typing a sentence.
* `POST /scout/parse` is public too, because it is pure: it turns a sentence into requirements, refusals and
  connectors without touching a row. A page can show a manager what their words would filter, then search.
* `POST /scout/search` needs an account. It is the one route here that reads the whole stored player table,
  and it can be pointed at a career — whose squad decides the need, and §61 keeps a career behind its
  owner's wall, so a foreign career slug answers 404 rather than confirming it exists.

A search never hides what it could not understand. The `refused` list from the parser rides along on the
response beside the candidates the filters produced, so a page cannot present "12 left-footed strikers" when
the foot was one of the phrases this vocabulary refused. §23's own example asks for an inverted full-back:
the answer names the players it found and says the role is not in this catalogue, in the same response.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit, ownership_or_admin
from app.models import Career, User
from app.services.scouting.requirements import (
    CONNECTORS,
    ROLE_POSITIONS,
    STAFFED_POSITIONS,
    UNSTAFFED_POSITIONS,
    Parsed,
    RequirementError,
    parse_requirements,
    scout_rules,
    stated_requirements,
    vocabulary_problems,
)
from app.services.scouting.search import DEFAULT_LIMIT, MAX_LIMIT, SORT_KEYS, SearchRefusal, limitations, scout_counts, scout_ready, search, search_problems, world_account
from app.services.simulation.market import MarketRefusal

router = APIRouter(prefix="/scout", tags=["scouting"])

NOT_FOUND = {"code": "not_found", "message": "No such career for this account"}
NOT_FOUND_CODES: Final = {"no_club"}
MAX_QUERY_CHARS: Final = 400


class ParseIn(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)


class SearchIn(BaseModel):
    """A sentence, stated fields, or both. Where both speak, both cuts apply and the response says so."""

    query: str = Field(default="", max_length=MAX_QUERY_CHARS)
    max_age: int | None = Field(default=None, ge=10, le=60)
    min_age: int | None = Field(default=None, ge=10, le=60)
    foot: str | None = Field(default=None, max_length=8)
    positions: list[str] | None = Field(default=None, max_length=8)
    bands: list[str] | None = Field(default=None, max_length=4)
    role: str | None = Field(default=None, max_length=16)
    attributes: dict[str, int] | None = Field(default=None, max_length=8)
    max_fee: int | None = Field(default=None, ge=0, le=1_000_000_000)
    sort: str | None = Field(default=None, max_length=24)
    career: str | None = Field(default=None, max_length=80)
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)


def _career(db: Session, user: User, ident: str) -> Career:
    row = db.scalar(select(Career).where(Career.slug == ident)) or db.scalar(select(Career).where(Career.id == ident))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    ownership_or_admin(user, row.owner_id, "career")
    return row


def _stated(payload: SearchIn) -> dict[str, Any]:
    """Only the fields the caller actually named, so a default `None` never becomes a filter."""
    return {
        key: value
        for key, value in payload.model_dump().items()
        if key in {"max_age", "min_age", "foot", "positions", "bands", "role", "attributes", "max_fee", "sort"} and value not in (None, {}, [])
    }


def _plan(payload: SearchIn) -> Parsed:
    """One object carrying the sentence, the filters it produced, the stated fields, and what was refused.

    A refusal cannot be separated from the search here: `search.py` takes the whole `Parsed`, so a candidate
    list always travels with the phrases that did not become filters.
    """
    stated = stated_requirements(_stated(payload))
    if not payload.query.strip():
        return Parsed(text="", requirements=stated)
    parsed = parse_requirements(payload.query)
    if parsed.unaccounted:  # pragma: no cover - the parser refuses every leftover instead of dropping it
        raise RequirementError("unaccounted_text", f"{parsed.unaccounted} was neither parsed nor refused, which should not happen", see="/api/v1/scout/rules")
    parsed.requirements.extend(stated)
    return parsed


def _duplicates(plan: Parsed) -> list[dict[str, Any]]:
    """Fields two parts of one request both spoke about, reported rather than resolved silently."""
    seen: dict[str, list[str]] = {}
    for item in plan.requirements:
        if item.kind == "sort":
            continue
        seen.setdefault(item.kind, []).append(item.phrase)
    return [
        {
            "kind": kind,
            "phrases": phrases,
            "rule": "both cuts apply: a candidate must answer each of them, so a stated field and a sentence that disagree narrow the pool rather than overrule one another",
        }
        for kind, phrases in sorted(seen.items())
        if len(phrases) > 1
    ]


@router.get("/rules")
def read_rules(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The vocabulary and the arithmetic: what a sentence may say, and what each saying does to the pool.

    The integrity block is published rather than kept in a test because it is the part a reader has to trust:
    the vocabulary agreeing with itself, and the search answering every requirement kind the parser emits.
    """
    limit(request, 60, 60, scope="scout_rules")
    rules = scout_rules()
    problems = [*vocabulary_problems(), *search_problems(db)]
    return {
        **rules,
        "integrity": {"problems": problems, "clean": not problems, "ready": scout_ready(db), "counts": scout_counts(db)},
        "search": {
            "default_limit": DEFAULT_LIMIT,
            "max_limit": MAX_LIMIT,
            "sorts": list(SORT_KEYS),
            "limits": limitations(),
            "world": world_account(db),
            "positions_stored": list(STAFFED_POSITIONS),
            "positions_the_engine_names_and_the_world_does_not_staff": list(UNSTAFFED_POSITIONS),
            "roles_occupiable_by_a_stored_position": {key: list(ROLE_POSITIONS[key]) for key in ROLE_POSITIONS if ROLE_POSITIONS[key]},
        },
        "connector_count": len(CONNECTORS),
        "example_parse": parse_requirements("找一个 22 岁以下、左脚、能踢 Inverted Fullback、预算 €20m 的球员").to_dict(),
        "routes": {
            "parse": "POST /api/v1/scout/parse — a sentence in, requirements and refusals out, no rows read",
            "search": "POST /api/v1/scout/search — needs an account; the only route here that reads the stored player table",
        },
    }


@router.post("/parse")
def parse(payload: ParseIn, request: Request) -> dict[str, Any]:
    """Read a scout's sentence without searching: what would be filtered, what was refused, what was ignored."""
    limit(request, 60, 60, scope="scout_parse")
    try:
        parsed = parse_requirements(payload.query)
    except RequirementError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error.to_dict()) from None
    return {
        "query": payload.query,
        **parsed.to_dict(),
        "search_route": "POST /api/v1/scout/search",
        "search_would_apply": len(parsed.filters),
        "search_would_rank_by": parsed.sort,
        "note": (
            "the sentence produced no filter, so a search over it would rank the whole stored pool rather than cut it"
            if not parsed.filters
            else "nothing was searched here: this route only reads the sentence"
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


@router.post("/search")
def run_search(payload: SearchIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Search the stored world with a sentence, stated fields, or both, optionally judged against a career."""
    limit(request, 20, 60, scope="scout_search")
    career: Career | None = None
    if payload.career:
        career = _career(db, user, str(payload.career))
    try:
        plan = _plan(payload)
        result = search(db, plan, career=career, limit=int(payload.limit))
    except RequirementError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error.to_dict()) from None
    except SearchRefusal as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error.to_dict()) from None
    except MarketRefusal as error:
        detail = error.to_dict()
        http = status.HTTP_404_NOT_FOUND if str(detail["code"]) in NOT_FOUND_CODES else status.HTTP_409_CONFLICT
        raise HTTPException(http, detail=detail) from None
    return {
        **result,
        "duplicate_fields": _duplicates(plan),
        "asked_for": {
            "query": payload.query or None,
            "stated": _stated(payload) or None,
            "career": payload.career,
            "limit": int(payload.limit),
        },
        "demo_data": True,
    }


__all__ = ["router"]
