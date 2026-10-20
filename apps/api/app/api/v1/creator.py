"""Creator endpoints (M10, spec §36): what an account publishes as a guide, and the addresses it cites.

One public door and ten private ones. `GET /creator/rules` prints only the tier's own vocabulary — the sections,
the ceilings, the formulas, the refusal codes and the limitation sentence — which is §39's and §35's precedent: a
rulebook is not a person's data, a shelf of guides is.

There is no 403 anywhere here, and that is a decision rather than an omission (§51): a creator door asks only
whether the caller has a session, which `current_user` answers with a 401 before any service code runs. What a
caller may not reach is answered as **absence** — `no_such_guide`, `no_such_creator` — in the same shape a row
that was never written earns, so no door confirms that somebody else's unpublished shelf exists.

Two things every answer keeps:

* **the guide is an address.** A citation travels as (document, ordinal) plus the hash that was there when it was
  written, and `passages` carries the heading read from the chunk *now* with `moved` beside it. Nothing in this
  module can return a passage's text, because no column stores one — which is what makes the tier honest after a
  corpus re-sync rather than quietly quoting something else;
* **every figure is counted now.** `citations`, `tokens`, `moved`, `guides` and `subscribers` come from the rows
  their published formulas name, recomputed per request, so a re-read after a write is the only way the page can
  show them and a cached number cannot exist here.

A refusal is answered from the project's one table (`services/club/answers.py`), which registers this tier in
`TIERS`; that is why this router holds no answer dict of its own — two tables is the defect §51 was written for.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import User
from app.services.club import answers
from app.services.creator import programs as cpr
from app.services.creator import publishing as cre

router = APIRouter(prefix="/creator", tags=["creator"])

#: The one table, read rather than copied: `test_creator.py` asserts this *is* the object the club doors answer
#: from, because a door that re-forked it would answer a shared code one way here and another way at `/club`.
_ANSWERS: Final[dict[str, int]] = answers.ANSWERS

#: Every door this module declares, in the order a reader meets them. `test_creator.py` holds this list against the
#: live route table in both directions, since `GET /creator/rules` prints it to the browser as the tier's own
#: description of itself.
ROUTE_GUIDE: tuple[dict[str, str], ...] = (
    {"method": "GET", "path": "/creator/rules", "door": "the tier's vocabulary: sections, ceilings, formulas, refusals"},
    {"method": "POST", "path": "/creator/profile", "door": "publish the creator state, or amend its headline and biography"},
    {"method": "GET", "path": "/creator/profile", "door": "your own shelf: the state, its counts, both sides of a follow"},
    {"method": "GET", "path": "/creator/profiles/{account}", "door": "another account as a creator, as far as they publish"},
    {"method": "POST", "path": "/creator/guides", "door": "frame a guide: a section, a title, a visibility"},
    {"method": "GET", "path": "/creator/guides", "door": "the public shelf, one creator's shelf, or one section's"},
    {"method": "GET", "path": "/creator/guides/{guide}", "door": "one guide with the passages it cites, read now"},
    {"method": "DELETE", "path": "/creator/guides/{guide}", "door": "erase your own guide, and the citations on it"},
    {"method": "POST", "path": "/creator/guides/{guide}/citations", "door": "cite one passage by address, remembering its hash"},
    {"method": "GET", "path": "/creator/guides/{guide}/citations", "door": "the citations, each with whether its passage moved"},
    {"method": "DELETE", "path": "/creator/guides/{guide}/citations/{citation}", "door": "un-cite one passage; the guide keeps the rest"},
    {"method": "POST", "path": "/creator/programs", "door": "publish a training program: a title, a visibility and its steps"},
    {"method": "GET", "path": "/creator/programs", "door": "the public shelf of programs"},
    {"method": "GET", "path": "/creator/programs/{program}", "door": "one program with its steps and the figures counted now"},
    {"method": "DELETE", "path": "/creator/programs/{program}", "door": "erase your own program and the sessions it planned"},
    {"method": "POST", "path": "/creator/programs/{program}/start", "door": "plan a program's steps as your own training sessions"},
)


def _refusal(error: cre.CreatorRefusal) -> HTTPException:
    """The answer a creator refusal deserves, read out of the project's one table (§51)."""
    return HTTPException(_ANSWERS.get(error.code, status.HTTP_400_BAD_REQUEST), detail=error.to_dict())


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # No `min_length`: a blank or over-long field is the *tier's* refusal, with the two figures a page needs to
    # show why beside the sentence. A pydantic bound would answer the same mistake with a schema list naming none.
    slug: str = Field(default="", max_length=64)
    headline: str = Field(default="", max_length=cre.PROFILE_HEADLINE_MAX + 40)
    bio: str = Field(default="", max_length=cre.PROFILE_BIO_MAX + 100)


class GuideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section: str = Field(default="plan", max_length=16)
    title: str = Field(default="", max_length=cre.GUIDE_TITLE_MAX + 40)
    summary: str = Field(default="", max_length=cre.GUIDE_SUMMARY_MAX + 100)
    visibility: str = Field(default="public", max_length=12)


class ProgramStepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drill: str = Field(default="", max_length=80)
    minutes: int = Field(default=0)
    note: str = Field(default="", max_length=cpr.STEP_NOTE_MAX + 100)


class ProgramIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=cpr.PROGRAM_TITLE_MAX + 40)
    summary: str = Field(default="", max_length=cpr.PROGRAM_SUMMARY_MAX + 100)
    visibility: str = Field(default="public", max_length=12)
    steps: list[ProgramStepIn] = Field(default_factory=list)


class CitationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: str = Field(default="", max_length=80)
    ordinal: int = Field(default=0)
    note: str = Field(default="", max_length=cre.CITATION_NOTE_MAX + 100)


@router.get("/rules")
def read_rules(db: Session = Depends(get_db)) -> dict[str, Any]:
    """The rulebook door: no guide, no creator, no figure about anybody — only what may be published.

    `refusal_answers` is derived here from the same table `_refusal` reads, so the printed status and the raised
    one cannot be written apart, and the limits are the shipped ones rather than a copy.
    """
    return {
        "routes": [dict(item) for item in ROUTE_GUIDE],
        "refusal_answers": answers.published(cre.REFUSALS),
        "entitlement_features": ["creator_publish", "creator_guide"],
        **cre.rules(db, ready=True),
        **cpr.rules(db, ready=True),
    }


@router.post("/profile")
def publish_profile(payload: ProfileIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The creator state is written by the first publication; nothing switches it on with a flag.

    `exclude_unset` is what makes an amendment mean *the fields this caller sent*: without it every field the form
    left out would arrive as the schema's own empty default, and a caller amending a headline would silently blank
    the biography beside it. The fields that were not sent are not passed, and `ensure_profile` reads that absence.
    """
    limit(request, 10, 60, scope="creator_write")
    try:
        return cre.ensure_profile(db, user.id, **payload.model_dump(exclude_unset=True))
    except cre.CreatorRefusal as error:
        raise _refusal(error) from None


@router.get("/profile")
def read_own_profile(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 60, 60, scope="creator_read")
    try:
        return cre.profile(db, user.id)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from None


@router.get("/profiles/{account}")
def read_profile(account: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Another account as a creator. Somebody who has published nothing is answered as absence, not as a blank."""
    limit(request, 60, 60, scope="creator_read")
    try:
        return cre.profile(db, account)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from None


@router.post("/guides")
def publish(payload: GuideIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Frame a guide. The section and the title are the author's; the substance stays in the corpus."""
    limit(request, 10, 60, scope="creator_write")
    try:
        return cre.publish_guide(db, user.id, section=payload.section, title=payload.title, summary=payload.summary, visibility=payload.visibility)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from None


@router.get("/guides")
def read_shelf(request: Request, creator: str | None = None, section: str | None = None, page_size: int = 20, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The public shelf, one creator's shelf, or one section's — as far as this reader may reach."""
    limit(request, 60, 60, scope="creator_read")
    try:
        return cre.list_guides(db, user.id, creator=creator, section=section, limit=page_size)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from None


@router.get("/guides/{guide}")
def read_guide(guide: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """One guide at its own address, with each cited passage read fresh and `moved` beside the ones that changed."""
    limit(request, 60, 60, scope="creator_read")
    try:
        return cre.read_guide(db, guide, user.id)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from None


@router.delete("/guides/{guide}")
def erase_guide(guide: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Erase your own guide. Its citations go with it, and the answer says how many did."""
    limit(request, 10, 60, scope="creator_write")
    try:
        return cre.erase_guide(db, guide, user.id)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from None


@router.post("/guides/{guide}/citations")
def add_citation(guide: str, payload: CitationIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Cite one passage by address. The corpus row is read for its hash; none of its text is stored."""
    limit(request, 20, 60, scope="creator_write")
    try:
        return cre.cite(db, guide, user.id, document=payload.document, ordinal=payload.ordinal, note=payload.note)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from None


@router.get("/guides/{guide}/citations")
def read_citations(guide: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 60, 60, scope="creator_read")
    try:
        return cre.citations_view(db, guide, user.id)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from None


@router.delete("/guides/{guide}/citations/{citation}")
def remove_citation(guide: str, citation: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    limit(request, 20, 60, scope="creator_write")
    try:
        return cre.uncite(db, guide, citation, user.id)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from None


@router.post("/programs", status_code=status.HTTP_201_CREATED)
def publish_program(
    payload: ProgramIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Publish a training program: a title, a visibility and the steps a learner would walk.

    A step names a drill from the training catalogue and the minutes it asks for, and a step
    naming a drill the catalogue does not hold is refused here rather than at the learner's first
    session: a plan that cannot be walked is not a plan.
    """
    limit(request, 20, 3600, scope="publish_program")
    try:
        return cpr.publish_program(
            db,
            user.id,
            title=payload.title,
            summary=payload.summary,
            visibility=payload.visibility,
            steps=[step.model_dump() for step in payload.steps],
        )
    except cre.CreatorRefusal as error:
        raise _refusal(error) from error


@router.get("/programs")
def read_programs(
    creator: str | None = None,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """The public shelf of programs."""
    return cpr.list_programs(db, creator=creator, page_size=page_size)


@router.get("/programs/{program}")
def read_program(
    program: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """One program with its steps and the figures counted now."""
    try:
        return cpr.read_program(db, program)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from error


@router.delete("/programs/{program}")
def erase_program(
    program: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Erase your own program and the sessions it planned."""
    limit(request, 20, 3600, scope="erase_program")
    try:
        return cpr.erase_program(db, user.id, program)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from error


@router.post("/programs/{program}/start", status_code=status.HTTP_201_CREATED)
def start_program(
    program: str,
    request: Request,
    player_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Plan a program's steps as the caller's own training sessions - the runnable half.

    The sessions are the training tier's rows, so completing one of them is the same act as
    completing any other session, and the progression is the program's order.
    """
    limit(request, 20, 3600, scope="start_program")
    try:
        return cpr.start_program(db, user.id, program, player_id=player_id)
    except cre.CreatorRefusal as error:
        raise _refusal(error) from error
