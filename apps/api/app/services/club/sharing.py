"""§40's development plan behind a link its guardian or coach can hand over, and take back (M13 Phase 5 item 18).

A plan is the one academy row a family is likely to want to *send* — to a relative, to a grassroots coach, to the
next club — and §40's rule about a child's data is what decides the shape of what a stranger sees, not only who
may mint the link:

* **The row stores the plan, not the plan's figures.** It holds a tenant id, a plan id, a token and when the door
  shut, and no measured value at all. Every number the page prints is recomputed from `plan_assessments` on the
  request that prints it, so a link keeps ageing in the open: a review filed after it was minted is on the page
  the next reader opens, and a review erased from the private side is gone from the public one too. The response
  cache does not get to hide that: a plan write drops the cached answer of every live token over the plan
  (`public_paths_of`), because a recomputation behind a minute-old cached page is still a stale page.
* **The public page is the shape of progress, not the child.** It prints the plan's status, focus, goals, stage
  and the arithmetic over its reviews. It prints no name, no player address, no exact age, no position, no rating,
  no sheet, no coach, no free text a coach wrote and no clip. `redacted` lists every omission with its reason,
  because a minimised page and a thin page look alike from the outside and only one of them is a decision.
* **A token is a capability, so it is stored raw and answers reach.** `secrets.token_hex(16)` inside a
  `String(64)` unique column, the same shape §17's board token and §38's CV token use; a door that has to read
  the value back cannot store a digest. An unknown token, a closed one and one that never existed are one 404
  with one sentence, because a door that distinguished them would report which tokens this build has heard of.
* **Only a plan its owner can open can be shared.** `open_share` walks `academy.plan_for_reader`, the same gate
  `GET …/plans/{plan}` walks, and then asks §40's minors' gate (`academy.plan_consent`) before minting: a child's
  plan needs a granted `plan` consent to become a public page even when the caller is staff. The refusals are
  therefore the private doors' own — `no_such_plan`, `insufficient_role`, `consent_required`, `scope_not_consented`.
* **The ledger is the account's, not the tenant's.** A link can outlive a membership: a guardian who was removed
  from an organisation must still be able to close what they opened. So the ledger and the revoke door are
  account-scoped, exactly as §24's scout shares are, and a lead who mints links for several tenants sees them
  in one list.
* **Twenty open links per account.** The cap counts live rows only, so closing links makes room, and the refusal
  names both figures — the same ceiling §24's links use, because an unbounded ledger is a way to fill a table
  from a loop.

`plan_consent` may raise `consent_required` / `scope_not_consented` from the academy service, and both travel to
the router, which answers them from `services/club/answers.py` like every other club code.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import drop_public_response
from app.core.security import new_public_id
from app.models import (
    AcademyPlanShare,
    CoachFeedback,
    DevelopmentPlan,
    Organization,
    PlanAssessment,
    PlanVideoEvidence,
    RealPlayer,
    User,
    utcnow,
)
from app.services.club import academy as edu
from app.services.club.organizations import ClubRefusal

#: The same shape as every other share token in this project: 16 bytes printed as 32 hex characters.
TOKEN_BYTES: Final = 16

#: The one path a public answer is served from. The router that opens the door, the sweep that retires the cached
#: answer, and the tests all spell it from here.
PUBLIC_PATH: Final = "/api/v1/club/academy/shared/{token}"

#: How many open links one account may hold. Closing one makes room, so the ceiling bounds the live ledger.
MAX_LIVE: Final = 20

#: The fields a public page deliberately does not carry, with the reason each one is absent. A reader can tell
#: this from a page that simply had nothing to show.
REDACTED: Final = (
    ("name", "the child's name and player address are not on a public page"),
    ("exact_age", "the page prints `stage` (youth or adult), never a birth date or an age"),
    ("position_and_rating", "the world's rating, potential and position stay behind the private doors"),
    ("team_name", "a club's team name plus a stage is a small enough group to name the child"),
    ("coach", "the author's display name and role are not published"),
    ("feedback_text", "how many coach notes are filed, never what they say"),
    ("review_notes", "the strengths, areas and next focus are the coach's own words about a child"),
    ("video", "a citation is a label and a window over a clip; a public page carries neither"),
    ("account_and_guardian", "neither the account that minted the link nor the guardian row behind the plan is part of the payload"),
)

REFUSALS: Final = (
    "no_such_share",
    "share_already_revoked",
    "share_subject_gone",
    "too_many_shares",
)

#: What this tier's own capabilities door prints beside the other limitations: one sentence about what a public
#: page is not, so a reader is never told a link is "the plan" rather than the minimised read of it.
LIMITATION: Final = (
    "a public plan link prints the shape of progress — status, focus, goals, stage and the arithmetic over the reviews — "
    "and never the child's name, exact age, position, rating, team, coach, the free text a coach wrote or a clip; "
    "the link is revocable at any moment and dies with the plan it names"
)

#: A link that never existed, a closed one and somebody else's are the one answer; a plan that has since been
#: erased is the same absence one level down, and gets its own sentence so a reader is not told the link is
#: wrong when it is the question's subject that went.
NOT_FOUND_CODES: Final[frozenset[str]] = frozenset({"no_such_share", "share_subject_gone"})
UNPROCESSABLE_CODES: Final[frozenset[str]] = frozenset()
CONFLICT_CODES: Final[frozenset[str]] = frozenset({"share_already_revoked", "too_many_shares"})
#: A share is not a role — it is a key. Nothing in this module answers 403.
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()
PUBLISHED: Final = REFUSALS


def _iso(value: datetime | None) -> str | None:
    """One spelling of a timestamp: UTC with an offset, whether this process built the value or SQLite read it."""
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC).isoformat()


def _live_rows(session: Session, user_id: str) -> list[AcademyPlanShare]:
    """This account's open links, oldest first. Deterministic ordering, as every other ledger here has."""
    return list(
        session.scalars(
            select(AcademyPlanShare)
            .where(AcademyPlanShare.user_id == user_id, AcademyPlanShare.revoked_at.is_(None))
            .order_by(AcademyPlanShare.created_at, AcademyPlanShare.id)
        )
    )


def _names(session: Session, row: AcademyPlanShare) -> dict[str, Any]:
    """The two names a *private* ledger may print: the plan and the child it was opened for.

    Both lookups are this link owner's own read, so naming the child here is the same fact the plan page prints.
    The public payload below never calls this function.
    """
    plan = session.get(DevelopmentPlan, row.plan_id)
    player = session.get(RealPlayer, plan.player_id) if plan is not None else None
    return {
        "plan": row.plan_id,
        "plan_status": plan.status if plan is not None else None,
        "player": ({"slug": player.slug, "name": player.name} if player is not None else None),
    }


def as_record(session: Session, row: AcademyPlanShare, *, token_visible: bool) -> dict[str, Any]:
    """One row in the shape every private door prints it: the live link's token, and never a closed one's."""
    named = _names(session, row)
    return {
        "share": row.id,
        "token": row.share_token if token_visible else None,
        "plan": named["plan"],
        "plan_status": named["plan_status"],
        "player": named["player"],
        "organization": row.organization_id,
        "opened_at": _iso(row.created_at),
        "revoked_at": _iso(row.revoked_at),
        "live": row.revoked_at is None,
    }


def open_share(session: Session, user: User, ident: str, plan_ident: str) -> dict[str, Any]:
    """Mint a link over one plan, or return the live one this account already holds for it.

    The plan is resolved through the private read gate first, and §40's minors' gate after it, so a link cannot be
    created over a plan the caller could not open or a child whose guardian has not consented to plan work. Asking
    the same question twice returns the same live token — a share is a door, and re-opening a door should not move
    it.
    """
    organization, plan, _reader = edu.plan_for_reader(session, user, ident, plan_ident)
    player = session.get(RealPlayer, plan.player_id)
    consented = edu.plan_consent(session, organization, player) if player is not None else None
    for row in _live_rows(session, user.id):
        if row.plan_id == plan.id:
            return {**as_record(session, row, token_visible=True), "created": False, "max_live": MAX_LIVE, "consented_by": _consent_figure(consented)}
    live = _live_rows(session, user.id)
    if len(live) >= MAX_LIVE:
        raise ClubRefusal(
            "too_many_shares",
            f"this account already holds {len(live)} open plan links, the ceiling this tier sets; close one before opening another",
            live=len(live),
            max_live=MAX_LIVE,
        )
    row = AcademyPlanShare(
        id=new_public_id("aps"),
        user_id=user.id,
        share_token=secrets.token_hex(TOKEN_BYTES),
        organization_id=organization.id,
        plan_id=plan.id,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(row)
    session.commit()
    return {**as_record(session, row, token_visible=True), "created": True, "max_live": MAX_LIVE, "consented_by": _consent_figure(consented)}


def _consent_figure(consent: Any) -> dict[str, Any] | None:
    """Whose agreement a minor's link rests on, named by id — `None` when the player is an adult."""
    if consent is None:
        return None
    return {"consent": consent.id, "guardian": consent.guardian_user_id, "scopes": [str(item) for item in (consent.scopes or ())]}


def list_shares(session: Session, user_id: str, organization_id: str | None = None) -> dict[str, Any]:
    """Every link this account ever opened, newest first, with a closed link's token left out.

    A revoked token is a dead key; printing it on a page invites a reader to try it in the address bar. The row still
    says when it shut, which is the part the owner asked for. `organization_id` narrows the ledger to one tenant
    without changing who may read it: the filter is applied to this account's own rows.
    """
    statement = select(AcademyPlanShare).where(AcademyPlanShare.user_id == user_id)
    if organization_id is not None:
        statement = statement.where(AcademyPlanShare.organization_id == organization_id)
    rows = list(session.scalars(statement.order_by(AcademyPlanShare.created_at.desc(), AcademyPlanShare.id.desc())))
    live = [row for row in rows if row.revoked_at is None]
    return {
        "shares": [as_record(session, row, token_visible=row.revoked_at is None) for row in rows],
        "counts": {"opened": len(rows), "live": len(live), "revoked": len(rows) - len(live)},
        "max_live": MAX_LIVE,
        "rule": (
            "a link is the account's, not the tenant's: one minted here can be closed after a membership ends, "
            "which is why this ledger is read by owner rather than by standing"
        ),
    }


def revoke(session: Session, user_id: str, token: str) -> dict[str, Any]:
    """Close the link a token opens. The row survives; only the door shuts.

    A token that is not this account's answers `no_such_share`, the same as one that never existed: the owner-scoped
    lookup is what makes "somebody else's link" indistinguishable from "no link" without inventing a second code.
    """
    row = session.scalar(select(AcademyPlanShare).where(AcademyPlanShare.share_token == str(token), AcademyPlanShare.user_id == user_id))
    if row is None:
        raise ClubRefusal("no_such_share", f"no plan link of yours answers to {str(token)!r}", token=str(token))
    if row.revoked_at is not None:
        raise ClubRefusal(
            "share_already_revoked",
            f"that link was already closed at {_iso(row.revoked_at)}",
            token=str(token),
            revoked_at=_iso(row.revoked_at),
        )
    row.revoked_at = utcnow()
    row.updated_at = row.revoked_at
    session.commit()
    return as_record(session, row, token_visible=False)


def public_paths_of(session: Session, plan_ids: Iterable[str]) -> list[str]:
    """The cached path of every open link over these plans, so a write can retire what it made false.

    `main.cached_response_for` holds a successful anonymous GET for sixty seconds. That cache is what makes a
    "recomputed on every read" page print a review filed a moment ago as if it did not exist — the recomputation
    is right, the answer it lands in is stale. So every write that changes what a public page prints collects the
    live tokens *before* it commits (an erased plan takes its share rows with it) and drops each path afterwards.

    Erasing also removes the rows this function would find, which is why the caller collects paths first rather
    than sweeping after the delete.
    """
    ids = [str(plan_id) for plan_id in plan_ids]
    if not ids:
        return []
    tokens = session.scalars(select(AcademyPlanShare.share_token).where(AcademyPlanShare.plan_id.in_(ids), AcademyPlanShare.revoked_at.is_(None)))
    return [PUBLIC_PATH.format(token=token) for token in tokens]


def drop_public_paths(paths: Iterable[str]) -> int:
    """Retire each path's anonymous answer from every tier that can serve it. Returns how many entries died."""
    return sum(drop_public_response(path) for path in paths)


def public_plan(session: Session, token: str) -> dict[str, Any]:
    """What an unauthenticated reader sees: the shape of one plan, re-read from its own rows.

    This is the one function in the module that must never touch `_names` or `plan.player_id`: the public payload
    names a plan and a tenant, and nothing that could name the child. The omissions are published in `redacted`
    rather than left implicit.
    """
    row = _live_by_token(session, token)
    plan = session.get(DevelopmentPlan, row.plan_id)
    organization = session.get(Organization, row.organization_id)
    if plan is None or organization is None or plan.organization_id != organization.id:
        raise ClubRefusal(
            "share_subject_gone",
            "the plan this link was opened about is no longer held by the tenant that wrote it",
            plan=row.plan_id,
            token=str(token),
        )
    player = session.get(RealPlayer, plan.player_id)
    age = int(player.age) if player is not None else 0
    assessments = list(session.scalars(select(PlanAssessment).where(PlanAssessment.plan_id == plan.id).order_by(PlanAssessment.assessed_on, PlanAssessment.id)))
    feedback_total = int(session.scalar(select(func.count()).select_from(CoachFeedback).where(CoachFeedback.plan_id == plan.id)) or 0)
    feedback_shared = int(
        session.scalar(select(func.count()).select_from(CoachFeedback).where(CoachFeedback.plan_id == plan.id, CoachFeedback.shared_with_guardian.is_(True))) or 0
    )
    evidence_total = int(session.scalar(select(func.count()).select_from(PlanVideoEvidence).where(PlanVideoEvidence.plan_id == plan.id)) or 0)
    goals = [{"title": str(item.get("title", "")), "measure": str(item.get("measure", "")), "by": str(item.get("by", ""))} for item in (plan.goals or []) if isinstance(item, dict)]
    return {
        "shared": {
            "opened_at": _iso(row.created_at),
            "plan": plan.id,
            "organization": {"slug": organization.slug, "name": organization.name, "kind": organization.kind},
            "note": (
                "this page is a live read of the plan its owner shared, not a copy: every figure is counted from the "
                "plan's own review rows at the moment of the request. The child is not named and the words a coach "
                "wrote are not published; every omission is listed in `redacted` with its reason."
            ),
        },
        "plan": {
            "status": plan.status,
            "focus": list(plan.focus or []),
            "goals": goals,
            "review_weeks": int(plan.review_weeks),
            "opened_at": _iso(plan.created_at),
            "stage": "youth" if age < edu.MINOR_AGE else "adult",
            "minor_at_open": bool(plan.minor_at_open),
        },
        "progress": edu.progress_of(session, plan),
        "assessments": [
            {
                "assessed_on": item.assessed_on,
                "ratings": {str(axis): int(score) for axis, score in (item.ratings or {}).items()},
                "axes_missing": [axis for axis in edu.AXES if axis not in (item.ratings or {})],
                "mean_rating": (round(sum(int(score) for score in (item.ratings or {}).values()) / len(item.ratings), 1) if item.ratings else None),
                "overall_observed": int(item.overall_observed),
                "measured_from": "`overall_observed` is the world's rating copied on the day this review was written",
            }
            for item in assessments
        ],
        "counts": {
            "assessments": len(assessments),
            "feedback": feedback_total,
            "feedback_shared_with_guardian": feedback_shared,
            "evidence": evidence_total,
        },
        "redacted": [{"field": field, "why": why} for field, why in REDACTED],
        "figures_from": "`development_plans`, `plan_assessments`, `coach_feedback` and `plan_video_evidence` for this plan, read on this request; counts are of rows, never of what they say",
        "demo_data": False,
    }


def _live_by_token(session: Session, token: str) -> AcademyPlanShare:
    """The one lookup a stranger is allowed to make: a token, and only an open one."""
    row = session.scalar(select(AcademyPlanShare).where(AcademyPlanShare.share_token == str(token), AcademyPlanShare.revoked_at.is_(None)))
    if row is None:
        # One sentence for "never existed", "closed" and "somebody else's", because a door that distinguished them
        # would be reporting which tokens this build has heard of.
        raise ClubRefusal("no_such_share", f"no open plan link answers to {str(token)!r}", token=str(token))
    return row
