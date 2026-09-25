"""Scout endpoints (M7, spec §23–§27).

Twelve doors, and the wall is the one §61 puts on everything else in this project:

* `GET /scout/rules` is public. The vocabulary, the money reading, the sortings and the two band
  vocabularies this project disagrees with itself about are authored fiction about generated rows, and a
  reader should be able to learn what the parser understands *before* typing a sentence.
* `POST /scout/parse` is public too, because it is pure: it turns a sentence into requirements, refusals and
  connectors without touching a row. A page can show a manager what their words would filter, then search.
* `POST /scout/search` needs an account. It is the one route here that reads the whole stored player table,
  and it can be pointed at a career — whose squad decides the need, and §61 keeps a career behind its
  owner's wall, so a foreign career slug answers 404 rather than confirming it exists.
* `POST /scout/report` needs an account for the same reason: §24's thirteen fields are read off the stored
  pool, and a career can be asked about beside the player. It is the only route here that refuses on
  *who* is missing rather than on what was asked — an unknown player is 404, an unknown role is 422 with
  the roles that do exist, and a report never comes back as an empty object to suggest the player was
  found and simply had nothing to say.
* `POST /scout/compare` needs an account, and answers §27's ten dimensions for a pair of stored players. It
  is the route in this file with the strongest thing not to do — 避免单一 Overall 分数决定一切 — so it
  returns no composite figure at all: ten dimensions, each a list of measures with its own leader, and a
  dimension whose measures disagree is called `split` instead of being resolved into a winner. Asking for a
  player against themself is a 422 that says a pair has to be two players, because the alternative is a
  payload of forty even lines that looks like a verdict.
* `GET|POST /scout/shortlists`, `GET|PATCH|DELETE /scout/shortlists/{ident}` and
  `POST|DELETE /scout/shortlists/{ident}/items[/{player}]` are §23's 建立 shortlist, and they need an account for
  the ordinary reason: a list is one account's own words. What is deliberate about them is what they do not store
  — no figure about a player is saved anywhere, so no list can go on claiming a rating the world has moved away
  from. A read takes every number from the stored rows again and re-applies the stored sentence, so a list ages
  in the open rather than going quiet.

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
from app.services.scouting.compare import (
    DIMENSION_LEADERS,
    DIMENSIONS,
    LEADERS,
    NO_WINNER_NOTE,
    STAT_COLUMNS,
    build_comparison,
    comparison_counts,
    comparison_problems,
    comparison_ready,
)
from app.services.scouting.compare import (
    limitations as comparison_limitations,
)
from app.services.scouting.report import (
    COMPANION_FIELDS,
    REPORT_FIELDS,
    VERDICTS,
    ReportRefusal,
    build_report,
    report_counts,
    report_problems,
    report_ready,
)
from app.services.scouting.report import (
    limitations as report_limitations,
)
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
from app.services.scouting.shortlist import (
    NOT_FOUND_CODES as SHORTLIST_NOT_FOUND,
)
from app.services.scouting.shortlist import (
    UNPROCESSABLE_CODES as SHORTLIST_UNPROCESSABLE,
)
from app.services.scouting.shortlist import (
    ShortlistRefusal,
    add_player,
    create_shortlist,
    delete_list,
    drop_player,
    list_shortlists,
    shortlist_counts,
    shortlist_ready,
    shortlist_view,
    update_list,
)
from app.services.scouting.shortlist import (
    limitations as shortlist_limitations,
)
from app.services.scouting.shortlist import (
    rules as shortlist_rules,
)
from app.services.simulation.market import MarketRefusal

router = APIRouter(prefix="/scout", tags=["scouting"])

NOT_FOUND = {"code": "not_found", "message": "No such career for this account"}
NOT_FOUND_CODES: Final = {"no_club"}
#: The §24 report and the §27 comparison both read the stored pool, and both refuse a name that is not in it
#: with 404 — the row genuinely is not there. A refusal that is about this project's vocabulary instead (an
#: unknown role, a pair that is one player) answers 422, because that one is the caller's word, not the world's.
POOL_NOT_FOUND_CODES: Final = {"no_such_player"}
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


class ReportIn(BaseModel):
    """One player, optionally judged for a role and against one career, optionally measured beside another."""

    player: str = Field(min_length=1, max_length=80)
    role: str | None = Field(default=None, max_length=16)
    career: str | None = Field(default=None, max_length=80)
    compare_to: str | None = Field(default=None, max_length=80)
    round_index: int | None = Field(default=None, ge=0, le=380)


class CompareIn(BaseModel):
    """§27's pair. Both sides are required: a comparison of one player is the refusal, not an empty answer."""

    left: str = Field(min_length=1, max_length=80)
    right: str = Field(min_length=1, max_length=80)


class ShortlistIn(BaseModel):
    """§23's list: a name, the sentence it was built from, and the two links a read needs.

    No figure belongs here. A list carries words and links; the players' numbers come back on every read from
    the stored rows, which is what lets a list go stale about its own question instead of lying about a player.

    The length caps are deliberately not pydantic constraints. A transport-level 422 names a field and a rule;
    the service's refusal names the length it was handed and the limit it tripped over, which is the answer a
    reader can check their own request against. So the cap lives in one place, and it is the service's.
    """

    name: str = ""
    query: str = ""
    role: str | None = Field(default=None, max_length=16)
    career: str | None = Field(default=None, max_length=80)


class ShortlistPatchIn(BaseModel):
    """The same four fields, all optional: a list can be renamed, re-questioned, or re-pointed at a career."""

    name: str | None = None
    query: str | None = None
    role: str | None = Field(default=None, max_length=16)
    career: str | None = Field(default=None, max_length=80)


class ShortlistItemIn(BaseModel):
    """Which player, and the manager's own words about him — the note is the only other thing stored, and the
    service is the one that says how long a note may be."""

    player: str = Field(min_length=1, max_length=80)
    note: str = ""


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
    the vocabulary agreeing with itself, the search answering every requirement kind the parser emits, a
    report building over the stored pool that answers every field §24 lists with a figure that recomputes
    from the attributes printed beside it, and a comparison whose every dimension is the leader its own
    measures give it.
    """
    limit(request, 60, 60, scope="scout_rules")
    rules = scout_rules()
    problems = [*vocabulary_problems(), *search_problems(db), *report_problems(db), *comparison_problems(db)]
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
        "report": {
            "fields": list(REPORT_FIELDS),
            "companion_fields": list(COMPANION_FIELDS),
            "verdicts": list(VERDICTS),
            "ready": report_ready(db),
            "counts": report_counts(db),
            "limitations": report_limitations(),
            "refusals": {
                "no_such_player": "404 — the row is not in the pool this report reads, and no empty report is returned to suggest otherwise",
                "unknown_role": "422 — the word is not in the role catalogue, and the roles that are come back beside it",
            },
            "note": "§24's thirteen lines, each answered by a figure recomputed from the stored row on the request: no group is averaged over an attribute the row does not carry, no potential is called talent, and no line is written by a model",
        },
        "comparison": {
            "dimensions": list(DIMENSIONS),
            "dimension_leaders": list(DIMENSION_LEADERS),
            "measure_leaders": list(LEADERS),
            "stat_columns": list(STAT_COLUMNS),
            "ready": comparison_ready(db),
            "counts": comparison_counts(db),
            "limitations": comparison_limitations(),
            "no_single_score": NO_WINNER_NOTE,
            "refusals": {
                "no_such_player": "404 — one side of the pair is not in the pool this comparison reads",
                "same_player": "422 — both idents resolved to one stored row, and a comparison needs two players",
            },
            "note": "§27's ten dimensions, each answered measure by measure out of the two stored rows: a dimension whose measures disagree is called `split`, an event rate with no lines behind it is `unknown`, and the two overall columns are printed without being made the answer",
        },
        "shortlists": {
            **shortlist_rules(),
            "ready": shortlist_ready(db),
            "counts": shortlist_counts(db),
            "limitations": shortlist_limitations(),
            "refusals": {
                "no_such_shortlist": "404 — no list of yours answers to that id, and another account's id is answered the same way",
                "no_such_player": "404 — the player is not in the pool, so nothing can be listed under that name",
                "no_such_career": "404 — no career of yours bears that slug, so no squad need can be judged against it",
                "already_listed": "409 — he is already on that list, and a second row would make the list's own count lie",
                "shortlist_full": "409 — the list holds as many players as one list may",
                "too_many_shortlists": "409 — the account holds as many lists as one account may",
                "not_listed": "409 — he is not on that list, so there is nothing there to take off it",
                "name_taken": "409 — the account already has a list under that name, and two lists of one name cannot be asked which is which",
            },
            "note": "§23's 建立 shortlist, stored as membership only: the read prints the search's own candidate projection for each member, re-parses the stored sentence against every row on it, and calls a stale list what it is",
        },
        "example_parse": parse_requirements("找一个 22 岁以下、左脚、能踢 Inverted Fullback、预算 €20m 的球员").to_dict(),
        "routes": {
            "parse": "POST /api/v1/scout/parse — a sentence in, requirements and refusals out, no rows read",
            "search": "POST /api/v1/scout/search — needs an account; the only route here that reads the stored player table",
            "report": "POST /api/v1/scout/report — needs an account; §24's structured report for one stored player",
            "comparison": "POST /api/v1/scout/compare — needs an account; §27's ten dimensions for a pair of stored players, with no composite score to decide between them",
            "shortlists": "GET|POST /api/v1/scout/shortlists — needs an account; §23's lists, which store a name, a sentence and membership, and nothing else about a player",
            "shortlist": "GET|PATCH|DELETE /api/v1/scout/shortlists/{ident} — one list read live: every figure re-taken from the stored rows, the stored sentence re-applied to every member",
            "shortlist_items": "POST|DELETE /api/v1/scout/shortlists/{ident}/items[/{player}] — put a stored player on a list, or take him off it",
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


@router.post("/report")
def read_report(payload: ReportIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """§24's structured report for one stored player: thirteen fields, each one arithmetic over that row.

    A career is optional, and its absence stays visible in the payload rather than being papered over:
    `team_fit` is null and the risk list simply carries one factor fewer. A comparison behaves the same way —
    §24 lists `Comparison`, and answering that field with nobody beside it would be a line that looks
    measured and is not. The player is looked up before the role, so a wrong slug and a wrong role produce
    the one refusal that is about the world rather than the one that is about this project's vocabulary.
    """
    limit(request, 20, 60, scope="scout_report")
    career: Career | None = None
    if payload.career:
        career = _career(db, user, str(payload.career))
    try:
        report = build_report(db, payload.player, role=payload.role, career=career, compare_to=payload.compare_to, round_index=payload.round_index)
    except ReportRefusal as error:
        detail = error.to_dict()
        http = status.HTTP_404_NOT_FOUND if str(detail["code"]) in POOL_NOT_FOUND_CODES else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(http, detail=detail) from None
    except MarketRefusal as error:
        detail = error.to_dict()
        http = status.HTTP_404_NOT_FOUND if str(detail["code"]) in NOT_FOUND_CODES else status.HTTP_409_CONFLICT
        raise HTTPException(http, detail=detail) from None
    return {
        **report,
        "asked_for": {
            "player": payload.player,
            "role": payload.role,
            "career": payload.career,
            "compare_to": payload.compare_to,
            "round_index": payload.round_index,
        },
        "demo_data": True,
    }


@router.post("/compare")
def compare(payload: CompareIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """§27's ten dimensions for a pair of stored players, with no figure in the answer that ranks them as a whole.

    The route is deliberately narrower than the report: no career, no role, no round. Each of those is a way
    of judging one player against a context, and §27 asks for a comparison of two players instead — the
    moment a context is allowed in, the payload starts carrying a figure that is about a club rather than
    about the pair, which is the report's job. Both sides are looked up before anything is computed, and the
    left is answered first when neither exists, so a typo says which half of the request it was.
    """
    limit(request, 20, 60, scope="scout_compare")
    try:
        comparison = build_comparison(db, payload.left, payload.right)
    except ReportRefusal as error:
        detail = error.to_dict()
        http = status.HTTP_404_NOT_FOUND if str(detail["code"]) in POOL_NOT_FOUND_CODES else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(http, detail=detail) from None
    return {**comparison, "asked_for": {"left": payload.left, "right": payload.right}, "demo_data": True}


__all__ = ["router"]


# --- §23's shortlist (建立 shortlist) ---------------------------------------------------------------


def _shortlist_refusal(error: ShortlistRefusal) -> HTTPException:
    """Which answer a list refusal deserves: a thing that is not there, a sentence that cannot be stored, or a
    state the request would have to break. The code and its figures travel together, as §22's refusals do."""
    detail = error.to_dict()
    if error.code in SHORTLIST_NOT_FOUND:
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=detail)
    if error.code in SHORTLIST_UNPROCESSABLE:
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    return HTTPException(status.HTTP_409_CONFLICT, detail=detail)


@router.get("/shortlists")
def read_shortlists(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """This account's lists and how many players each holds — counts of membership, because nothing else is stored."""
    limit(request, 30, 60, scope="scout_shortlists")
    return {**list_shortlists(db, user), "demo_data": True}


@router.post("/shortlists")
def open_shortlist(payload: ShortlistIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Name a list, and keep the sentence it came out of beside it. No player is looked up here."""
    limit(request, 20, 60, scope="scout_shortlist_write")
    try:
        created = create_shortlist(db, user, name=payload.name, query=payload.query, role=payload.role or "", career=payload.career)
    except ShortlistRefusal as error:
        raise _shortlist_refusal(error) from None
    return {**created, "demo_data": True}


@router.get("/shortlists/{ident}")
def read_shortlist(ident: str, request: Request, round_index: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """§23's shortlist read live: every figure re-taken from the stored rows, and the stored sentence re-applied
    to each member so a list that no longer answers its own question says so. `round_index` moves the career's
    need to a round the manager names, exactly as §24's report takes it."""
    limit(request, 20, 60, scope="scout_shortlist_read")
    try:
        view = shortlist_view(db, user, ident, round_index=round_index)
    except ShortlistRefusal as error:
        raise _shortlist_refusal(error) from None
    return view


@router.patch("/shortlists/{ident}")
def rename_shortlist(payload: ShortlistPatchIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Change a list's words. The players on it are not touched, because they were never stored in the words."""
    limit(request, 20, 60, scope="scout_shortlist_write")
    try:
        return {**update_list(db, user, ident, name=payload.name, query=payload.query, role=payload.role, career=payload.career), "demo_data": True}
    except ShortlistRefusal as error:
        raise _shortlist_refusal(error) from None


@router.delete("/shortlists/{ident}")
def remove_shortlist(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Delete a list. Its membership rows go by the schema's cascade, and no player row is written back to."""
    limit(request, 20, 60, scope="scout_shortlist_write")
    try:
        return {**delete_list(db, user, ident), "demo_data": True}
    except ShortlistRefusal as error:
        raise _shortlist_refusal(error) from None


@router.post("/shortlists/{ident}/items")
def put_on_list(payload: ShortlistItemIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Put a stored player on a list. The slug is looked up first, so a wrong name never becomes a row."""
    limit(request, 30, 60, scope="scout_shortlist_write")
    try:
        return {**add_player(db, user, ident, player=payload.player, note=payload.note), "demo_data": True}
    except ShortlistRefusal as error:
        raise _shortlist_refusal(error) from None


@router.delete("/shortlists/{ident}/items/{player}")
def take_off_list(ident: str, player: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Take a player off a list. The rows that stay keep the positions they had, which is the only order kept."""
    limit(request, 30, 60, scope="scout_shortlist_write")
    try:
        return {**drop_player(db, user, ident, player=player), "demo_data": True}
    except ShortlistRefusal as error:
        raise _shortlist_refusal(error) from None
