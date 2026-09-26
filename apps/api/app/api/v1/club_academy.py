"""Youth academy endpoints (M8, spec §40): a curriculum, one plan per child, and the consent that gates them.

The doors all live under `/club/academy/…`, and the two-segment shape is not a stylistic choice: §39 routes
`GET /club/{ident}`, so a single-segment academy path could be read as a tenant called `academy`. Every door
here is therefore at least two segments below `/club`, which means neither tier can shadow the other.

Like §39, this module implements no policy of its own. Each door hands the caller's tenant, ident and body to
`app/services/club/academy.py`, which resolves the tenant through `standing()` or `require()` and then asks the
two questions §40 is about — does this role hold the right, and does a *granted consent row* cover this child
for this purpose. Three consequences are visible from outside:

* a child's plan is not readable by a role that holds `plan.read_all` only when that role is a `parent`: the
  right is scoped by the consent row, so another family's child answers `no_such_plan` rather than a 403 that
  would confirm the row exists;
* a minor's row cannot be written at all without a consent naming that purpose, and the refusal prints the
  scopes that *are* on file, because the useful next action is a guardian ticking one box;
* the video doors cite a clip and never serve one. `plan_video_evidence` is a label and a window over an M5
  asset, and playback stays the uploader's door — §40 lists video among what must never be default-public.

`GET /club/academy/capabilities` is the one public door, and it publishes the axes, the scopes, the column list
this tier writes, and the list of what it promises never to hold. A guardian cannot be asked to agree to a
data policy that is only readable after signing in.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import User
from app.services import entitlements as ent_status
from app.services.club import academy as edu
from app.services.club import organizations as club
from app.services.club import reports as rep
from app.services.club import sessions as sess
from app.services.club.organizations import ClubRefusal

router = APIRouter(prefix="/club/academy", tags=["youth-academy"])

#: The answer each refusal code deserves, assembled from both tiers' own sets — §39's four and §40's four.
#: The two sets are held disjoint by the suite, so one code can never mean two answers, and a code in neither
#: falls through to 400 rather than being silently mapped to the nearest-looking 4xx.
_ANSWERS: dict[str, int] = {
    **dict.fromkeys(club.NOT_FOUND_CODES, status.HTTP_404_NOT_FOUND),
    **dict.fromkeys(club.UNPROCESSABLE_CODES, status.HTTP_422_UNPROCESSABLE_ENTITY),
    **dict.fromkeys(club.CONFLICT_CODES, status.HTTP_409_CONFLICT),
    **dict.fromkeys(club.FORBIDDEN_CODES, status.HTTP_403_FORBIDDEN),
    **dict.fromkeys(edu.NOT_FOUND_CODES, status.HTTP_404_NOT_FOUND),
    **dict.fromkeys(edu.UNPROCESSABLE_CODES, status.HTTP_422_UNPROCESSABLE_ENTITY),
    **dict.fromkeys(edu.CONFLICT_CODES, status.HTTP_409_CONFLICT),
    **dict.fromkeys(edu.FORBIDDEN_CODES, status.HTTP_403_FORBIDDEN),
    # A session code answers where the tier put it: an absence is a 404, a figure the caller can correct is
    # a 422, a collision on a date and slot is a 409. Anything unregistered would fall through to a 400.
    **dict.fromkeys(sess.NOT_FOUND_CODES, status.HTTP_404_NOT_FOUND),
    **dict.fromkeys(sess.UNPROCESSABLE_CODES, status.HTTP_422_UNPROCESSABLE_ENTITY),
    **dict.fromkeys(sess.CONFLICT_CODES, status.HTTP_409_CONFLICT),
    **dict.fromkeys(sess.FORBIDDEN_CODES, status.HTTP_403_FORBIDDEN),
    **dict.fromkeys(rep.NOT_FOUND_CODES, status.HTTP_404_NOT_FOUND),
    **dict.fromkeys(rep.UNPROCESSABLE_CODES, status.HTTP_422_UNPROCESSABLE_ENTITY),
    **dict.fromkeys(rep.CONFLICT_CODES, status.HTTP_409_CONFLICT),
    # §42's codes can be answered at a club door, because that is where a ceiling is checked: a
    # refusal that reached its own answer map would be a 400 claiming the request was malformed.
    **dict.fromkeys(ent_status.NOT_FOUND_CODES, status.HTTP_404_NOT_FOUND),
    **dict.fromkeys(ent_status.UNPROCESSABLE_CODES, status.HTTP_422_UNPROCESSABLE_ENTITY),
    **dict.fromkeys(ent_status.CONFLICT_CODES, status.HTTP_409_CONFLICT),
    **dict.fromkeys(ent_status.FORBIDDEN_CODES, status.HTTP_403_FORBIDDEN),
}


def _refusal(error: ClubRefusal) -> HTTPException:
    return HTTPException(_ANSWERS.get(error.code, status.HTTP_400_BAD_REQUEST), detail=error.to_dict())


#: The door guide this module publishes, and which `GET /club/capabilities` prints beside §39's own doors so a
#: page is handed one complete list of the tenant's doors rather than two halves it has to discover separately.
ROUTE_GUIDE: Final = (
    {"methods": ["GET"], "path": "/api/v1/club/academy/capabilities", "purpose": "the academy rulebook: axes, scopes, the columns this tier writes, and what it never holds"},
    {"methods": ["GET", "POST"], "path": "/api/v1/club/academy/{ident}/sessions", "purpose": "the training log of this tenant, and recording a session one team actually ran"},
    {
        "methods": ["GET", "DELETE"],
        "path": "/api/v1/club/academy/{ident}/sessions/{session_ident}",
        "purpose": "one session: its derived load beside the two columns it comes from, and erasing the row",
    },
    {
        "methods": ["GET", "POST"],
        "path": "/api/v1/club/academy/{ident}/reports",
        "purpose": "the questions this tenant has saved, and asking a new one of the rows a report may read",
    },
    {
        "methods": ["GET", "DELETE"],
        "path": "/api/v1/club/academy/{ident}/reports/{report_ident}",
        "purpose": "one report, answered now from the rows that exist now, and removing the question",
    },
    {"methods": ["GET", "POST"], "path": "/api/v1/club/academy/{ident}/curricula", "purpose": "the tenant's training curricula, and writing one"},
    {"methods": ["PATCH", "DELETE"], "path": "/api/v1/club/academy/{ident}/curricula/{curriculum}", "purpose": "change or remove a curriculum; a plan that used it keeps existing and says so"},
    {"methods": ["GET", "POST"], "path": "/api/v1/club/academy/{ident}/plans", "purpose": "the plans this account may read — all of them for staff, a guardian's own children only for a parent"},
    {
        "methods": ["GET", "PATCH", "DELETE"],
        "path": "/api/v1/club/academy/{ident}/plans/{plan}",
        "purpose": "read one plan with its reviews and recomputed progress, change its status, focus, goals, cadence or curriculum, or erase it — a dry run first, and closing is a different door",
    },
    {"methods": ["POST"], "path": "/api/v1/club/academy/{ident}/plans/{plan}/assessments", "purpose": "write a review: the five axes rated on a day, and what the coach saw"},
    {"methods": ["POST"], "path": "/api/v1/club/academy/{ident}/plans/{plan}/feedback", "purpose": "say one thing to the player, and decide whether the guardian reads it too"},
    {"methods": ["POST"], "path": "/api/v1/club/academy/{ident}/plans/{plan}/evidence", "purpose": "cite a window of a clip the caller uploaded; this does not hand out a way to watch it"},
    {"methods": ["DELETE"], "path": "/api/v1/club/academy/{ident}/plans/{plan}/evidence/{evidence}", "purpose": "remove one citation; the clip itself is the uploader's and stays"},
    {
        "methods": ["GET", "POST"],
        "path": "/api/v1/club/academy/{ident}/consents",
        "purpose": "which children have a granted scope set on file and from whose account, and a guardian's yes for one child, scope by scope",
    },
    {"methods": ["DELETE"], "path": "/api/v1/club/academy/{ident}/consents/{player}", "purpose": "take the yes back; new writes stop and the rows already written stay"},
    {
        "methods": ["GET", "DELETE"],
        "path": "/api/v1/club/academy/{ident}/players/{player}/data",
        "purpose": "everything this tenant holds about one child, table by table with the column list beside it — and erasing it, where a dry run prints the counts first",
    },
)


class PhaseIn(BaseModel):
    """One block of a curriculum week. The shape is the limit: three keys, and no place to put anything else."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(default="", max_length=edu.PHASE_LABEL_MAX + 40)
    focus: str = Field(default="", max_length=edu.FOCUS_ITEM_MAX + 40)
    minutes: int = Field(default=0)


class GoalIn(BaseModel):
    """One goal the child agreed to. `title`, `measure`, `by` — and the academy's answer to a fourth key is a refusal."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=edu.GOAL_TITLE_MAX + 40)
    measure: str = Field(default="", max_length=edu.GOAL_MEASURE_MAX + 40)
    by: str = Field(default="", max_length=32)


class CurriculumIn(BaseModel):
    """A curriculum's own fields. Bound above the published caps so the service answers first, with its figures."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(default="", max_length=edu.CURRICULUM_NAME_MAX + 64)
    age_group: str = Field(default="open", max_length=32)
    weekly_minutes: int = Field(default=0)
    phases: list[PhaseIn] = Field(default_factory=list)


class CurriculumPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=edu.CURRICULUM_NAME_MAX + 64)
    age_group: str | None = Field(default=None, max_length=32)
    weekly_minutes: int | None = Field(default=None)
    phases: list[PhaseIn] | None = Field(default=None)


class PlanIn(BaseModel):
    """Open a plan for one child. `player` is the only identity here: age and minority are read from the world's row."""

    model_config = ConfigDict(extra="forbid")

    player: str = Field(min_length=1, max_length=160)
    focus: list[str] = Field(default_factory=list)
    goals: list[GoalIn] = Field(default_factory=list)
    review_weeks: int = Field(default=6)
    curriculum: str | None = Field(default=None, max_length=96)
    team: str | None = Field(default=None, max_length=96)
    status: str = Field(default="active", max_length=16)


class PlanPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str | None = Field(default=None, max_length=16)
    focus: list[str] | None = Field(default=None)
    goals: list[GoalIn] | None = Field(default=None)
    review_weeks: int | None = Field(default=None)
    curriculum: str | None = Field(default=None, max_length=96)


class AssessmentIn(BaseModel):
    """A review. The axes are the published five and the ratings are 0 to 100; `ratings` is a dict of those, so a
    sixth axis has nowhere to be written and the service refuses it by name."""

    model_config = ConfigDict(extra="forbid")

    assessed_on: str = Field(min_length=1, max_length=32)
    ratings: dict[str, int] = Field(default_factory=dict)
    strengths: str = Field(default="", max_length=edu.ASSESSMENT_TEXT_MAX + 200)
    areas: str = Field(default="", max_length=edu.ASSESSMENT_TEXT_MAX + 200)
    next_focus: str = Field(default="", max_length=edu.NEXT_FOCUS_MAX + 40)


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(default="", max_length=edu.FEEDBACK_MAX + 200)
    shared_with_guardian: bool = Field(default=True)


class EvidenceIn(BaseModel):
    """A citation of a clip: the caller's own upload, a window, and optionally the review that prompted it."""

    model_config = ConfigDict(extra="forbid")

    clip: str = Field(min_length=1, max_length=96)
    label: str = Field(default="", max_length=edu.EVIDENCE_LABEL_MAX + 40)
    t_start: float = Field(default=0.0)
    t_end: float = Field(default=0.0)
    assessment: str | None = Field(default=None, max_length=96)


class ConsentIn(BaseModel):
    """A guardian's claim about one child, and the purposes it covers. There is no free-text field, on purpose.

    `scopes` is optional rather than defaulted to a list, because the two empty-looking cases mean different
    things: leaving the field out takes the published default set, and sending `[]` is refused rather than
    read as a yes for three purposes nobody ticked.
    """

    model_config = ConfigDict(extra="forbid")

    player: str = Field(min_length=1, max_length=160)
    scopes: list[str] | None = Field(default=None)


@router.get("/capabilities")
def read_academy_capabilities(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The published academy rulebook: what may be recorded, what must be consented to, and what is never held."""
    limit(request, 60, 60, scope="academy_capabilities")
    return {
        **edu.rules(),
        "counts": {**edu.academy_counts(db), **sess.session_counts(db, ready=edu.academy_ready(db)), **rep.report_counts(db, ready=edu.academy_ready(db))},
        "ready": edu.academy_ready(db),
        # The same flag means the same thing at both doors, so the sentence is one constant rather than two that
        # a reader has to trust agree.
        "ready_rule": club.READY_RULE,
        # The session codes join the same table, and the answer map below decides which HTTP status each
        # one earns — so a code that forgot to register there would silently be announced as a 400.
        "session_limits": dict(sess.CAPS),
        "report_kinds": list(rep.KINDS),
        "report_limits": {"max_reports_per_organization": rep.MAX_REPORTS_PER_ORGANIZATION, "window_max_days": rep.WINDOW_MAX_DAYS},
        "refusal_answers": {code: _ANSWERS.get(code, status.HTTP_400_BAD_REQUEST) for code in (*edu.REFUSALS, *edu.SHARED_REFUSALS)},
        # §41's codes are published beside §40's rather than folded into them. The academy tier's own claim is
        # that its table has exactly one row per code it can answer with, and a merged table would break that
        # arithmetic while still looking complete to a reader. Codes §40 already answers with are not claimed twice.
        "session_refusals": {code: _ANSWERS.get(code, status.HTTP_400_BAD_REQUEST) for code in sess.PUBLISHED},
        "report_refusals": {code: _ANSWERS.get(code, status.HTTP_400_BAD_REQUEST) for code in rep.REFUSALS},
        "limitations": [*edu.limitations(), sess.LIMITATION, rep.LIMITATION],
        "consent_scopes": {
            "scopes": list(edu.SCOPES),
            "default_granted": list(edu.DEFAULT_SCOPES),
            "rule": "a consent names purposes: leave `scopes` out of a grant and it covers `default_scopes` above, send an empty list and the door refuses rather than guessing — and `video` is in neither, because consenting to a plan is not consenting to footage of a child",
        },
        "data_origin": "project-authored",
        "is_demo_data": False,
        "demo_data": False,
        "routes": [dict(line) for line in ROUTE_GUIDE],
    }


@router.get("/{ident}/curricula")
def read_curricula(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The tenant's curricula, each with its phases totalled against its own weekly figure."""
    limit(request, 30, 60, scope="academy_read")
    try:
        return {**edu.list_curricula(db, user, ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/curricula")
def write_curriculum(payload: CurriculumIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Write a curriculum: what an age band trains, in blocks, and how many minutes a week it costs."""
    limit(request, 20, 60, scope="academy_write")
    try:
        return {
            **edu.create_curriculum(db, user, ident, name=payload.name, age_group=payload.age_group, weekly_minutes=payload.weekly_minutes, phases=[phase.model_dump() for phase in payload.phases]),
            "demo_data": False,
        }
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.patch("/{ident}/curricula/{curriculum}")
def edit_curriculum(payload: CurriculumPatchIn, ident: str, curriculum: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Change a curriculum. Plans that were written under it keep their own record of what they used."""
    limit(request, 20, 60, scope="academy_write")
    try:
        return {
            **edu.update_curriculum(
                db,
                user,
                ident,
                curriculum,
                name=payload.name,
                age_group=payload.age_group,
                weekly_minutes=payload.weekly_minutes,
                phases=([phase.model_dump() for phase in payload.phases] if payload.phases is not None else None),
            ),
            "demo_data": False,
        }
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/curricula/{curriculum}")
def remove_curriculum(ident: str, curriculum: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Delete a curriculum, and report how many plans it had to let go of rather than deleting with it."""
    limit(request, 20, 60, scope="academy_write")
    try:
        return {**edu.delete_curriculum(db, user, ident, curriculum), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/plans")
def read_plans(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The plans this account may read: the tenant's for staff, a guardian's own children for a parent."""
    limit(request, 30, 60, scope="academy_read")
    try:
        return {**edu.list_plans(db, user, ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/plans")
def open_plan(payload: PlanIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Open a development plan. For a child under the published age this is refused until a consent row says otherwise."""
    limit(request, 20, 60, scope="academy_write")
    try:
        return {
            **edu.open_plan(
                db,
                user,
                ident,
                player=payload.player,
                focus=payload.focus,
                goals=[goal.model_dump() for goal in payload.goals],
                review_weeks=payload.review_weeks,
                curriculum=payload.curriculum,
                team=payload.team,
                status=payload.status,
            ),
            "demo_data": False,
        }
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/plans/{plan}")
def read_plan(ident: str, plan: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """One plan, redacted by the right that opened it, with the rows that were withheld counted rather than hidden."""
    limit(request, 30, 60, scope="academy_read")
    try:
        return {**edu.get_plan(db, user, ident, plan), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.patch("/{ident}/plans/{plan}")
def edit_plan(payload: PlanPatchIn, ident: str, plan: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Change a plan. A closed one is not rewritten — the next season opens a new row."""
    limit(request, 20, 60, scope="academy_write")
    try:
        return {
            **edu.update_plan(
                db,
                user,
                ident,
                plan,
                status=payload.status,
                focus=payload.focus,
                goals=([goal.model_dump() for goal in payload.goals] if payload.goals is not None else None),
                review_weeks=payload.review_weeks,
                curriculum=payload.curriculum,
            ),
            "demo_data": False,
        }
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/plans/{plan}")
def erase_one_plan(ident: str, plan: str, request: Request, confirm: bool = Query(default=False), db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Erase one plan and its rows. Without `confirm` this is a dry run that prints the counts it would remove."""
    limit(request, 10, 60, scope="academy_write")
    try:
        return {**edu.erase_plan(db, user, ident, plan, confirm=confirm), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/plans/{plan}/assessments")
def write_assessment(payload: AssessmentIn, ident: str, plan: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Record a review: the axes rated, what was strong, what to work on, and the progress the new row makes."""
    limit(request, 30, 60, scope="academy_write")
    try:
        return {
            **edu.add_assessment(db, user, ident, plan, assessed_on=payload.assessed_on, ratings=payload.ratings, strengths=payload.strengths, areas=payload.areas, next_focus=payload.next_focus),
            "demo_data": False,
        }
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/plans/{plan}/feedback")
def write_feedback(payload: FeedbackIn, ident: str, plan: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Say a thing to the player. `shared_with_guardian` decides whether the family's copy shows it."""
    limit(request, 30, 60, scope="academy_write")
    try:
        return {**edu.add_feedback(db, user, ident, plan, message=payload.message, shared_with_guardian=payload.shared_with_guardian), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/plans/{plan}/evidence")
def cite_evidence(payload: EvidenceIn, ident: str, plan: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Cite a window of a clip you uploaded. The clip must be yours, and the window must fit inside it."""
    limit(request, 30, 60, scope="academy_write")
    try:
        return {**edu.link_evidence(db, user, ident, plan, clip=payload.clip, label=payload.label, t_start=payload.t_start, t_end=payload.t_end, assessment=payload.assessment), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/plans/{plan}/evidence/{evidence}")
def drop_evidence(ident: str, plan: str, evidence: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Remove one citation. The upload it pointed at is a different person's file and is never touched here."""
    limit(request, 30, 60, scope="academy_write")
    try:
        return {**edu.unlink_evidence(db, user, ident, plan, evidence), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/consents")
def read_consents(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Which children have a yes on file: the tenant's rows for staff, this account's own claims for a guardian."""
    limit(request, 30, 60, scope="academy_read")
    try:
        return {**edu.list_consents(db, user, ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/consents")
def grant_consent(payload: ConsentIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """A guardian's yes for one child, scope by scope. Nothing here is emailed, checked or proved."""
    limit(request, 20, 60, scope="academy_write")
    try:
        return {**edu.grant_consent(db, user, ident, player=payload.player, scopes=payload.scopes), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/consents/{player}")
def withdraw_consent(ident: str, player: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Take the yes back. New writes stop at once; what was already written stays until somebody erases it."""
    limit(request, 20, 60, scope="academy_write")
    try:
        return {**edu.withdraw_consent(db, user, ident, player), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/players/{player}/data")
def read_player_data(ident: str, player: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """What this tenant holds about one child, counted per table, with the column list and the never-held list."""
    limit(request, 30, 60, scope="academy_read")
    try:
        return {**edu.player_data_inventory(db, user, ident, player), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/players/{player}/data")
def erase_player_data(ident: str, player: str, request: Request, confirm: bool = Query(default=False), db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Erase every row this tenant holds about one child. Without `confirm` this prints the counts and removes nothing."""
    limit(request, 10, 60, scope="academy_write")
    try:
        return {**edu.erase_player_data(db, user, ident, player, confirm=confirm), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


class SessionIn(BaseModel):
    """Record one training session. The caps live in the service, whose refusal prints the figure it tripped over."""

    model_config = ConfigDict(extra="forbid")

    team: str = Field(min_length=1, max_length=160)
    scheduled_on: str = Field(min_length=8, max_length=10)
    duration_min: int
    rpe: int
    slot: int = 1
    focus: list[str] = Field(default_factory=list)
    drill_slugs: list[str] = Field(default_factory=list)
    attendees: list[str] = Field(default_factory=list)
    plan: str | None = Field(default=None, max_length=96)
    curriculum: str | None = Field(default=None, max_length=96)
    note: str = Field(default="", max_length=400)


@router.get("/{ident}/sessions")
def read_sessions(ident: str, request: Request, team: str | None = None, since: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The tenant's session log, newest first, with the load summed from the rows it shows."""
    limit(request, 30, 60, scope="academy_read")
    try:
        return {**sess.list_sessions(db, user, ident, team=team, since=since), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/sessions")
def write_session(payload: SessionIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Record what the team did: the sheet decides who may be named, and a child's guardian decides whether they are."""
    limit(request, 15, 60, scope="academy_write")
    try:
        return {
            **sess.create_session(
                db,
                user,
                ident,
                team=payload.team,
                scheduled_on=payload.scheduled_on,
                duration_min=payload.duration_min,
                rpe=payload.rpe,
                slot=payload.slot,
                focus=payload.focus,
                drill_slugs=payload.drill_slugs,
                attendees=payload.attendees,
                plan=payload.plan,
                curriculum=payload.curriculum,
                note=payload.note,
            ),
            "demo_data": False,
        }
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/sessions/{session_ident}")
def read_one_session(ident: str, session_ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """One session, with the load figure beside the two columns it is computed from."""
    limit(request, 30, 60, scope="academy_read")
    try:
        return {**sess.session_detail(db, user, ident, session_ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/sessions/{session_ident}")
def erase_one_session(ident: str, session_ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Remove one session row. The sheet, the plan and any clip it cited are untouched by it."""
    limit(request, 10, 60, scope="academy_write")
    try:
        return {**sess.delete_session(db, user, ident, session_ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


class ReportIn(BaseModel):
    """Ask a question of the tenant. The window is the only scope a report accepts, and no figure is sent in."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=3, max_length=32)
    window_from: str = Field(min_length=8, max_length=10)
    window_to: str = Field(min_length=8, max_length=10)
    team: str | None = Field(default=None, max_length=160)


@router.get("/{ident}/reports")
def read_reports(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The questions this tenant has saved. What each one answers is computed as you read it."""
    limit(request, 30, 60, scope="academy_read")
    try:
        return {**rep.list_reports(db, user, ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/reports")
def write_report(payload: ReportIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Save a reading of the tenant's rows — a kind, a window and an optional team, and no figures at all."""
    limit(request, 10, 60, scope="academy_write")
    try:
        return {
            **rep.create_report(db, user, ident, kind=payload.kind, window_from=payload.window_from, window_to=payload.window_to, team=payload.team),
            "demo_data": False,
        }
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/reports/{report_ident}")
def read_one_report(ident: str, report_ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """One report, answered now: the figures, their formulas and the row counts they came from."""
    limit(request, 30, 60, scope="academy_read")
    try:
        return {**rep.report_detail(db, user, ident, report_ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/reports/{report_ident}")
def erase_one_report(ident: str, report_ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Remove the question. Nothing the report was asking about is touched by it."""
    limit(request, 10, 60, scope="academy_write")
    try:
        return {**rep.delete_report(db, user, ident, report_ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None
