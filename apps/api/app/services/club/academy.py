"""§40's youth academy: a plan per player, the reviews that measure it, and the rules that bind a minor's rows.

Seven capabilities are asked for — Player Development, Individual Development Plan, Training Curriculum,
Assessment, Coach Feedback, Video Evidence, Progress — and six constraints about children: parental consent,
privacy, data minimisation, access controls, deletion, age-appropriate design. This module is the second half of
that sentence, because the six constraints are what make the seven capabilities safe to build.

Four rules decide the shape of everything below.

* **A minor's plan cannot exist without a consent row.** `open_plan` reads the player's age from the world's own
  row and, under `MINOR_AGE`, refuses with `consent_required` until a *granted* `guardian_consents` row names
  that child and that scope. The consent is self-declared — no software here can verify guardianship — and
  `limitations()` says so instead of implying a check that does not exist.
* **A parent's right is scoped by that same row.** `plan.read_own_child` opens one child's plan, and a plan of
  another family's child in the same tenant is answered exactly as one that does not exist. A role that holds
  neither plan right is answered 403 with the matrix beside it, because for that caller the tenant is already
  theirs and the useful question is about their role.
* **Progress is arithmetic, never a column.** `progress_of()` reads the plan's own `plan_assessments` rows and
  prints the formula next to every figure. One assessment measures a level; two measure a direction.
* **Minimisation is the column list.** There is no field for an address, a phone number, an email, a birth date,
  a location, a school or a medical note, so there is nothing for such a value to be stored into; the request
  bodies forbid unknown keys, and `STORED_FIELDS` is held against the live tables by the suite.

The tenant rule from §39 is untouched and load-bearing: every door here resolves the organisation first, through
`organizations.require()` or `organizations.standing()`, so a foreign tenant answers `no_such_organization` at an
academy door exactly as it does at a team door — which is what the isolation walk over in
`tests/test_club_organizations.py` proves by counting the doors.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any, Final

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import (
    AcademyCurriculum,
    ClubTeam,
    ClubTeamMember,
    CoachFeedback,
    DevelopmentPlan,
    GuardianConsent,
    Organization,
    OrganizationMember,
    PlanAssessment,
    PlanVideoEvidence,
    RealPlayer,
    User,
    VideoAsset,
)
from app.services.club import access
from app.services.club.organizations import ClubRefusal, require, resolve_team, standing

MINOR_AGE: Final = 18
#: What a guardian is asked to agree to, and the only vocabulary `guardian_consents.scopes` accepts. `video` is
#: absent from `DEFAULT_SCOPES`: consenting to a plan is not consenting to footage of a child.
SCOPES: Final = ("plan", "assessment", "feedback", "video")
DEFAULT_SCOPES: Final = ("plan", "assessment", "feedback")

PLAN_STATUSES: Final = ("draft", "active", "paused", "closed")

#: §40's development axes. These are not `models.ATTRIBUTES`: the world's 25 attributes are what a generated
#: player *has*, and an academy rating is what a coach *saw* in a training block, on a scale the coach owns.
AXES: Final = ("technique", "tactics", "physical", "mental", "competition_readiness")

MAX_CURRICULA_PER_ORGANIZATION: Final = 12
MAX_PHASES_PER_CURRICULUM: Final = 8
WEEKLY_MINUTES_MAX: Final = 1200
MAX_PLANS_PER_ORGANIZATION: Final = 100
REVIEW_WEEKS_MIN: Final = 1
REVIEW_WEEKS_MAX: Final = 52
FOCUS_ITEMS_MAX: Final = 6
GOALS_MAX: Final = 8
GOAL_KEYS: Final = ("title", "measure", "by")
MAX_ASSESSMENTS_PER_PLAN: Final = 52
MAX_FEEDBACK_PER_PLAN: Final = 200
MAX_EVIDENCE_PER_PLAN: Final = 20
MAX_CONSENTS_PER_GUARDIAN: Final = 10

CURRICULUM_NAME_MAX: Final = 120
PHASE_LABEL_MAX: Final = 60
FOCUS_ITEM_MAX: Final = 48
GOAL_TITLE_MAX: Final = 120
GOAL_MEASURE_MAX: Final = 120
ASSESSMENT_TEXT_MAX: Final = 600
NEXT_FOCUS_MAX: Final = 120
FEEDBACK_MAX: Final = 600
EVIDENCE_LABEL_MAX: Final = 120

#: The refusal codes this tier raises itself. `_ANSWERS` in the route module joins these with §39's, and the
#: suite holds the two sets apart, so one code can never mean two answers.
REFUSALS: Final = (
    "no_such_curriculum",
    "no_such_plan",
    "no_such_assessment",
    "no_such_evidence",
    "no_such_clip",
    "no_such_consent",
    "not_on_sheet",
    "curriculum_name_taken",
    "curriculum_limit",
    "phase_limit",
    "phase_shape",
    "weekly_minutes_range",
    "plan_already_open",
    "plan_limit",
    "plan_is_closed",
    "unknown_status",
    "focus_limit",
    "goal_shape",
    "unknown_axis",
    "rating_range",
    "date_shape",
    "date_in_future",
    "date_before_plan",
    "assessment_limit",
    "feedback_limit",
    "feedback_required",
    "evidence_limit",
    "evidence_window",
    "already_linked",
    "consent_limit",
    "consent_required",
    "scope_not_consented",
    "unknown_scope",
    "text_too_long",
    "erase_confirmation",
    "review_weeks_range",
)

#: The codes §39 owns and this tier raises through it. Listed so a page can print every answer it may meet, and
#: kept out of `REFUSALS` so the two tiers' sets stay disjoint and each code keeps exactly one HTTP answer.
SHARED_REFUSALS: Final = ("no_such_organization", "no_such_player", "name_required", "insufficient_role")

NOT_FOUND_CODES: Final = frozenset({"no_such_curriculum", "no_such_plan", "no_such_assessment", "no_such_evidence", "no_such_clip", "no_such_consent"})
UNPROCESSABLE_CODES: Final = frozenset(
    {
        "not_on_sheet",
        "curriculum_limit",
        "phase_limit",
        "phase_shape",
        "weekly_minutes_range",
        "plan_limit",
        "unknown_status",
        "focus_limit",
        "goal_shape",
        "unknown_axis",
        "rating_range",
        "date_shape",
        "date_in_future",
        "date_before_plan",
        "assessment_limit",
        "feedback_limit",
        "feedback_required",
        "evidence_limit",
        "evidence_window",
        "consent_limit",
        "consent_required",
        "scope_not_consented",
        "unknown_scope",
        "text_too_long",
        "erase_confirmation",
        "review_weeks_range",
    }
)
CONFLICT_CODES: Final = frozenset({"curriculum_name_taken", "plan_already_open", "plan_is_closed", "already_linked"})
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Every column this tier writes about a player, published so a page can answer *what do you hold on my child?*
#: without reading a migration. The suite compares this against the live tables in both directions.
STORED_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "academy_curricula": ("age_group", "created_at", "data_origin", "id", "is_demo_data", "name", "organization_id", "phases", "updated_at", "weekly_minutes"),
    "development_plans": (
        "age_at_open",
        "author_user_id",
        "created_at",
        "curriculum_id",
        "data_origin",
        "focus",
        "goals",
        "id",
        "is_demo_data",
        "minor_at_open",
        "organization_id",
        "player_id",
        "review_weeks",
        "status",
        "team_id",
        "updated_at",
    ),
    "plan_assessments": (
        "areas",
        "assessed_on",
        "assessor_user_id",
        "created_at",
        "data_origin",
        "id",
        "is_demo_data",
        "next_focus",
        "overall_observed",
        "plan_id",
        "ratings",
        "strengths",
        "updated_at",
    ),
    "coach_feedback": ("coach_user_id", "created_at", "data_origin", "id", "is_demo_data", "message", "plan_id", "shared_with_guardian", "updated_at"),
    "plan_video_evidence": ("asset_id", "assessment_id", "created_at", "data_origin", "id", "is_demo_data", "label", "plan_id", "t_end", "t_start", "updated_at"),
    "guardian_consents": ("created_at", "data_origin", "guardian_user_id", "id", "is_demo_data", "organization_id", "player_id", "scopes", "state", "updated_at"),
}

#: What §40 asks this tier never to hold. Nothing here has a column, and a body that offers one is refused by
#: the schema before the service reads it; the wording is published so the promise is checkable rather than
#: a list of things a reader has to trust.
RESTRICTED_FIELDS: Final = (
    "home address",
    "postcode",
    "telephone number",
    "email address",
    "date of birth",
    "precise location",
    "school attended",
    "medical or injury record",
    "government identifier",
    "photo or video held outside the clip the guardian consented to",
)


def _today() -> date:
    return datetime.now(UTC).date()


def _is_minor(age: int) -> bool:
    return int(age) < MINOR_AGE


def _player_of(session: Session, organization: Organization, ident: str, *, on_sheet: bool = True) -> RealPlayer:
    """The world's row for a player, and — when the door asks for it — proof they are on this tenant's sheet.

    The sheet test is an access rule, not a tidy-up: without it a tenant could open a development plan for any
    of the world's several thousand players, and a guardian could claim a child who does not train there.
    """
    player = session.scalar(select(RealPlayer).where(RealPlayer.slug == str(ident))) or session.scalar(select(RealPlayer).where(RealPlayer.id == str(ident)))
    if player is None:
        raise ClubRefusal("no_such_player", f"no player in the generated world answers to {str(ident)!r}, so no plan can be written for them", ident=str(ident), organization=organization.slug)
    if on_sheet and not session.scalar(
        select(ClubTeamMember.id).join(ClubTeam, ClubTeam.id == ClubTeamMember.team_id).where(ClubTeam.organization_id == organization.id, ClubTeamMember.player_id == player.id)
    ):
        raise ClubRefusal(
            "not_on_sheet",
            f"{player.name} is not on any team sheet of {organization.name}, so this tenant has no development work to plan for them",
            player=player.slug,
            organization=organization.slug,
            teams=int(session.scalar(select(func.count()).select_from(ClubTeam).where(ClubTeam.organization_id == organization.id)) or 0),
        )
    return player


def consents_for(session: Session, organization: Organization, player: RealPlayer, *, granted_only: bool = True) -> list[GuardianConsent]:
    statement = select(GuardianConsent).where(GuardianConsent.organization_id == organization.id, GuardianConsent.player_id == player.id)
    if granted_only:
        statement = statement.where(GuardianConsent.state == "granted")
    return list(session.scalars(statement.order_by(GuardianConsent.created_at, GuardianConsent.id)))


def _scope_names(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in (value or ()))


def _require_scope(session: Session, organization: Organization, player: RealPlayer, scope: str) -> GuardianConsent | None:
    """The minors' gate: an adult needs nothing, a child needs a granted consent that names this scope.

    Returns the consent row it accepted, so a caller can say whose agreement it acted on. The refusal prints the
    child's age, the threshold, the scope it asked for and the scopes already on file — a guardian told only
    "consent required" would not know which box to tick.
    """
    if not _is_minor(player.age):
        return None
    rows = consents_for(session, organization, player)
    for row in rows:
        if scope in _scope_names(row.scopes):
            return row
    raise ClubRefusal(
        "scope_not_consented" if rows else "consent_required",
        (
            f"{player.name} is {int(player.age)}, under {MINOR_AGE}, and the {len(rows)} consent row(s) on file here cover "
            f"{sorted({item for row in rows for item in _scope_names(row.scopes)})} — not {scope!r}"
            if rows
            else f"{player.name} is {int(player.age)}, under {MINOR_AGE}, and nobody has consented to {scope} work on them in {organization.name}"
        ),
        player=player.slug,
        age=int(player.age),
        threshold=MINOR_AGE,
        scope=scope,
        consent_rows=len(rows),
        scopes_present=sorted({item for row in rows for item in _scope_names(row.scopes)}),
        scopes_available=list(SCOPES),
    )


def _plan(session: Session, organization: Organization, ident: str) -> DevelopmentPlan:
    plan = session.scalar(select(DevelopmentPlan).where(DevelopmentPlan.organization_id == organization.id, DevelopmentPlan.id == str(ident)))
    if plan is None:
        # A page can also address a plan by the child it belongs to, and the tenant's own sheet narrows the
        # lookup so one player can only ever resolve to one plan here — the same guarantee `plan_already_open`
        # gives on the write side, read back on the address side.
        row = session.scalar(select(RealPlayer).where((RealPlayer.slug == str(ident)) | (RealPlayer.id == str(ident))))
        if row is not None:
            matches = list(
                session.scalars(
                    select(DevelopmentPlan).where(DevelopmentPlan.organization_id == organization.id, DevelopmentPlan.player_id == row.id).order_by(DevelopmentPlan.created_at, DevelopmentPlan.id)
                )
            )
            if len(matches) > 1:
                raise ClubRefusal(
                    "plan_already_open",
                    f"{row.name} has {len(matches)} plans in {organization.name} and the address {str(ident)!r} names a child, not one of them; use the plan id",
                    player=row.slug,
                    plans=len(matches),
                )
            plan = matches[0] if matches else None
    if plan is None:
        # The caller's own ident is echoed and nothing resolved: a plan that belongs to another tenant, or to
        # another family in this one, is answered as the absence of a row rather than as a refusal that names it.
        raise ClubRefusal("no_such_plan", f"no development plan of {organization.name} answers to {str(ident)!r}", ident=str(ident), organization=organization.slug)
    return plan


def _reader(session: Session, organization: Organization, user: User, player_id: str | None) -> dict[str, Any]:
    """What this account may see of one child: the staff right, or the guardian row, or neither.

    The second question is asked here because `require()` can only ask about a role. A `parent` holds
    `plan.read_own_child`, which is a right over one named child and not over the tenant's plans, and the row
    that names the child is a consent. A `withdrawn` consent reads nothing new and erases everything, which is
    why `may_erase` consults the rows in both states while `guardian` only counts granted ones.
    """
    member = session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization.id, OrganizationMember.user_id == user.id))
    role = str(member.role) if (member is not None and member.status == "active") else ""
    staff = bool(role) and access.may(role, "plan.read_all")
    consent = None
    if bool(role) and access.may(role, "plan.read_own_child"):
        consent = session.scalar(
            select(GuardianConsent).where(
                GuardianConsent.organization_id == organization.id,
                GuardianConsent.player_id == player_id,
                GuardianConsent.guardian_user_id == user.id,
                GuardianConsent.state == "granted",
            )
        )
    any_claim = session.scalar(
        select(GuardianConsent.id).where(GuardianConsent.organization_id == organization.id, GuardianConsent.player_id == player_id, GuardianConsent.guardian_user_id == user.id)
    )
    return {
        "role": role,
        "staff": staff,
        "may_write": bool(staff or (role and access.may(role, "plan.write"))),
        "may_erase": bool((role and access.may(role, "plan.erase")) or any_claim is not None),
        "guardian": consent is not None,
        "consent": consent,
        "scopes": _scope_names(consent.scopes) if consent is not None else (),
        "can_read": bool(staff or consent is not None),
    }


def _assessments(session: Session, plan: DevelopmentPlan) -> list[PlanAssessment]:
    return list(session.scalars(select(PlanAssessment).where(PlanAssessment.plan_id == plan.id).order_by(PlanAssessment.assessed_on, PlanAssessment.id)))


def _feedback(session: Session, plan: DevelopmentPlan) -> list[CoachFeedback]:
    return list(session.scalars(select(CoachFeedback).where(CoachFeedback.plan_id == plan.id).order_by(CoachFeedback.created_at, CoachFeedback.id)))


def _evidence(session: Session, plan: DevelopmentPlan) -> list[PlanVideoEvidence]:
    return list(session.scalars(select(PlanVideoEvidence).where(PlanVideoEvidence.plan_id == plan.id).order_by(PlanVideoEvidence.created_at, PlanVideoEvidence.id)))


def progress_of(session: Session, plan: DevelopmentPlan) -> dict[str, Any]:
    """§40's Progress: the arithmetic over this plan's own assessments, with the formula beside each figure."""
    rows = _assessments(session, plan)
    observed = [int(row.overall_observed) for row in rows]
    first, last = (rows[0], rows[-1]) if rows else (None, None)
    span_days = (date.fromisoformat(last.assessed_on) - date.fromisoformat(first.assessed_on)).days if (first is not None and last is not None) else 0
    due_every = max(1, int(plan.review_weeks)) * 7
    since_review = (_today() - date.fromisoformat(last.assessed_on)).days if last is not None else None
    opened_on = plan.created_at.date() if plan.created_at is not None else None
    plan_days_open = (_today() - opened_on).days if opened_on is not None else None
    axes_means: dict[str, float] = {}
    for axis in AXES:
        values = [int(row.ratings[axis]) for row in rows if isinstance(row.ratings, dict) and axis in row.ratings]
        if values:
            axes_means[axis] = round(sum(values) / len(values), 1)
    # The mean says how high an axis has been rated; only first-to-last says which way it went. An axis one of
    # the two ends never rated has no direction to report, so it is named rather than guessed at.
    axes_change: dict[str, int] = {}
    unrated_at_an_end: list[str] = []
    if first is not None and last is not None and first is not last:
        first_ratings = first.ratings or {}
        last_ratings = last.ratings or {}
        for axis in AXES:
            if axis in first_ratings and axis in last_ratings:
                axes_change[axis] = int(last_ratings[axis]) - int(first_ratings[axis])
            elif axis in first_ratings or axis in last_ratings:
                unrated_at_an_end.append(axis)
    expected = (plan_days_open // due_every) if plan_days_open is not None else None
    return {
        "assessments": len(rows),
        "first_assessed_on": first.assessed_on if first else None,
        "last_assessed_on": last.assessed_on if last else None,
        "overall_first": observed[0] if observed else None,
        "overall_last": observed[-1] if observed else None,
        "overall_change": (observed[-1] - observed[0]) if len(observed) > 1 else None,
        "axis_means": axes_means,
        "axis_change": axes_change,
        "axis_change_unrated_at_one_end": unrated_at_an_end,
        "span_days": span_days,
        "opened_on": opened_on.isoformat() if opened_on else None,
        "plan_days_open": plan_days_open,
        "reviews_due_by_cadence": expected,
        "reviews_behind": (max(0, int(expected) - len(rows)) if expected is not None else None),
        "days_since_review": since_review,
        "due_in_days": (None if since_review is None else due_every - since_review),
        "measured_from": "`plan_assessments` rows of this plan, ordered by `assessed_on` then `id`, against `development_plans.created_at`",
        "formulas": {
            "overall_change": "last `overall_observed` minus first — both are the world's rating copied on the day each review was written, so a plan cannot drift into reporting today's number as last month's",
            # The debt is counted from the day the plan opened, not from the day of its first review: a history
            # measured between two rows can only ever report the reviews that exist, so a plan with one review
            # would print itself up to date no matter how long it had been owed the next one.
            "reviews_due_by_cadence": f"floor(plan_days_open / ({plan.review_weeks} weeks x 7)) — one review owed for each cadence window that has closed since the plan opened; the window it is standing inside is not yet owed",
            "reviews_behind": "reviews_due_by_cadence minus the rows that exist, floored at zero; a plan with no rows at all still owes what its own age has asked for",
            "plan_days_open": "today minus `opened_on`; `span_days` is the separate figure between this plan's first review and its last, which is the distance the axis directions are measured over",
            "axis_means": "the mean of each axis over this plan's reviews, one decimal, axes nobody rated left out",
            "axis_change": f"`{last.assessed_on if last else 'first review'}` minus `{first.assessed_on if first else 'first review'}` on each axis rated at both ends — this is the direction §40 asks a plan to show, and `axis_change_unrated_at_one_end` names the axes it cannot tell you about",
            "axis_change_unrated_at_one_end": "axes rated at one end of the plan's history and not the other; no difference is printed for them because none can be measured",
            "days_since_review": f"today minus `last_assessed_on`; `due_in_days` is {plan.review_weeks * 7} minus that, and negative means the review is overdue",
        },
        "not_a_column": "no figure here is stored: a plan has no progress field to go stale",
        "one_review_is_not_a_direction": len(rows) == 1,
    }


def _clip(value: Any, cap: int, *, label: str) -> str:
    """Trim, and refuse what will not fit. One code for every over-long field in the tier.

    The caps differ per field and the message prints both figures, so the code does not need to carry the
    field's identity — and it must not, because a caller told `feedback_limit` after writing too long a
    *strength line* would go delete a row they did not need to delete.
    """
    text = str(value).strip()
    if len(text) > cap:
        raise ClubRefusal("text_too_long", f"{label} is capped at {cap} characters and this one is {len(text)}", field=label, length=len(text), max=cap)
    return text


def _iso(value: Any, *, label: str) -> str:
    text = str(value).strip()
    if not _DATE.match(text):
        raise ClubRefusal("date_shape", f"{label} must be an ISO date like 2026-09-25; {text!r} is not one", value=text, expected="YYYY-MM-DD")
    try:
        date.fromisoformat(text)
    except ValueError as error:  # a shape that matches and still is not a calendar day: 2026-13-40
        raise ClubRefusal("date_shape", f"{label} reads as a date and is not one: {text!r} ({error})", value=text) from None
    return text


def _focus(value: Any) -> list[str]:
    items = [str(item).strip() for item in (value or []) if str(item).strip()]
    if len(items) > FOCUS_ITEMS_MAX:
        raise ClubRefusal("focus_limit", f"a plan names at most {FOCUS_ITEMS_MAX} focus areas and this one names {len(items)}", held=len(items), max=FOCUS_ITEMS_MAX)
    return [_clip(item, FOCUS_ITEM_MAX, label="a focus area") for item in items]


def _goals(value: Any) -> list[dict[str, str]]:
    """A goal is a sentence, what would show it moved, and a date. Nothing else — and that is the minimisation."""
    rows = value or []
    if len(rows) > GOALS_MAX:
        raise ClubRefusal("goal_shape", f"a plan holds at most {GOALS_MAX} goals and this one offers {len(rows)}", held=len(rows), max=GOALS_MAX)
    goals: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ClubRefusal("goal_shape", f"a goal is an object with {list(GOAL_KEYS)}; this one is a bare {type(row).__name__}", keys=list(GOAL_KEYS))
        extra = sorted(set(row) - set(GOAL_KEYS))
        if extra:
            raise ClubRefusal(
                "goal_shape",
                f"a goal carries {list(GOAL_KEYS)} and nothing else; {extra} has no column to be stored in, which is the point",
                keys=list(GOAL_KEYS),
                extra=extra,
            )
        title = _clip(row.get("title", ""), GOAL_TITLE_MAX, label="a goal title")
        if not title:
            raise ClubRefusal("goal_shape", f"a goal needs a title between 1 and {GOAL_TITLE_MAX} characters; this one is empty after stripping", length=0, max=GOAL_TITLE_MAX)
        goal = {"title": title}
        if str(row.get("measure", "")).strip():
            goal["measure"] = _clip(row["measure"], GOAL_MEASURE_MAX, label="a goal measure")
        if str(row.get("by", "")).strip():
            goal["by"] = _iso(row["by"], label="a goal date")
        goals.append(goal)
    return goals


def _ratings(value: Any) -> dict[str, int]:
    rows = value or {}
    if not isinstance(rows, dict):
        raise ClubRefusal("unknown_axis", f"ratings are an object of axis to score; this one is a bare {type(rows).__name__}", axes=list(AXES))
    if not rows:
        raise ClubRefusal("unknown_axis", f"an assessment rates at least one of {list(AXES)}; this one rates nothing", axes=list(AXES))
    ratings: dict[str, int] = {}
    for axis, score in rows.items():
        if str(axis) not in AXES:
            raise ClubRefusal("unknown_axis", f"{axis!r} is not one of the published development axes", axis=str(axis), axes=list(AXES))
        try:
            number = int(score)
        except (TypeError, ValueError) as error:
            raise ClubRefusal("rating_range", f"the {axis} rating must be a whole number 0-100; {score!r} is not one", axis=str(axis), value=str(score)) from error
        if not 0 <= number <= 100:
            raise ClubRefusal("rating_range", f"the {axis} rating is {number}, outside the published 0 to 100", axis=str(axis), value=number, low=0, high=100)
        ratings[str(axis)] = number
    return ratings


def _phases(value: Any) -> list[dict[str, Any]]:
    rows = value or []
    if len(rows) > MAX_PHASES_PER_CURRICULUM:
        raise ClubRefusal("phase_limit", f"a curriculum is blocked into at most {MAX_PHASES_PER_CURRICULUM} phases and this one offers {len(rows)}", held=len(rows), max=MAX_PHASES_PER_CURRICULUM)
    phases: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ClubRefusal("phase_shape", f"a phase is an object with `label`, `focus` and `minutes`; this one is a bare {type(row).__name__}")
        extra = sorted(set(row) - {"label", "focus", "minutes"})
        if extra:
            raise ClubRefusal("phase_shape", f"a phase carries `label`, `focus` and `minutes`; {extra} has nowhere to be stored", extra=extra)
        minutes = row.get("minutes", 0)
        try:
            width = max(0, int(minutes))
        except (TypeError, ValueError) as error:
            raise ClubRefusal("phase_shape", f"a phase's minutes must be a whole number of minutes; {minutes!r} is not one", value=str(minutes)) from error
        phases.append({"label": _clip(row.get("label", ""), PHASE_LABEL_MAX, label="a phase label"), "focus": _clip(row.get("focus", ""), FOCUS_ITEM_MAX, label="a phase focus"), "minutes": width})
    return phases


def _scopes(value: Any) -> list[str]:
    """What a guardian ticked. A missing field means the published default; an empty list means nothing.

    The two are not the same request, and collapsing them would let a body that says `scopes: []` grant plan,
    assessment and feedback work on a child that nobody ticked. `None` is the only thing that means "default".
    """
    rows = [str(item).strip() for item in (DEFAULT_SCOPES if value is None else value)]
    if not rows:
        raise ClubRefusal("unknown_scope", f"a consent must name at least one of {list(SCOPES)}; this one names nothing", scopes=list(SCOPES))
    unknown = sorted(set(rows) - set(SCOPES))
    if unknown:
        raise ClubRefusal("unknown_scope", f"{unknown} is not a purpose a guardian can consent to", unknown=unknown, scopes=list(SCOPES))
    return [item for item in SCOPES if item in set(rows)]


def _curriculum(session: Session, organization: Organization, ident: str) -> AcademyCurriculum:
    row = session.scalar(select(AcademyCurriculum).where(AcademyCurriculum.organization_id == organization.id, AcademyCurriculum.id == str(ident))) or session.scalar(
        select(AcademyCurriculum).where(AcademyCurriculum.organization_id == organization.id, AcademyCurriculum.name == str(ident))
    )
    if row is None:
        raise ClubRefusal("no_such_curriculum", f"no curriculum of {organization.name} answers to {str(ident)!r}", ident=str(ident), organization=organization.slug)
    return row


def curriculum_view(session: Session, row: AcademyCurriculum) -> dict[str, Any]:
    phases = [dict(item) for item in (row.phases or [])]
    assigned = sum(int(item.get("minutes", 0)) for item in phases)
    return {
        "id": row.id,
        "name": row.name,
        "age_group": row.age_group,
        "weekly_minutes": int(row.weekly_minutes),
        "phases": phases,
        "phase_count": len(phases),
        "phase_minutes": assigned,
        "unassigned_minutes": int(row.weekly_minutes) - assigned,
        "plans_using_it": int(session.scalar(select(func.count()).select_from(DevelopmentPlan).where(DevelopmentPlan.curriculum_id == row.id)) or 0),
        "formulas": {
            "phase_minutes": "the sum of the stored phases' minutes",
            "unassigned_minutes": f"weekly_minutes ({int(row.weekly_minutes)}) minus phase_minutes — a curriculum that schedules less than it claims says so here",
        },
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "data_origin": row.data_origin,
        "is_demo_data": bool(row.is_demo_data),
    }


def list_curricula(session: Session, user: User, ident: str) -> dict[str, Any]:
    """Every age-band curriculum of the tenant. §40 puts the training curriculum beside the plan it feeds."""
    organization, member = standing(session, user, ident)
    rows = list(session.scalars(select(AcademyCurriculum).where(AcademyCurriculum.organization_id == organization.id).order_by(AcademyCurriculum.age_group, AcademyCurriculum.name)))
    return {
        "organization": organization.slug,
        "items": [curriculum_view(session, row) for row in rows],
        "total": len(rows),
        "limit": MAX_CURRICULA_PER_ORGANIZATION,
        "room_left": max(0, MAX_CURRICULA_PER_ORGANIZATION - len(rows)),
        "role": member.role,
        "rule": "a curriculum names no child, so every standing role may read one — including `parent` and `scout`, which see no plan",
        "demo_data": False,
    }


def create_curriculum(session: Session, user: User, ident: str, *, name: str, age_group: str = "open", weekly_minutes: int = 0, phases: Any = None) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "curriculum.write")
    label = _clip(name, CURRICULUM_NAME_MAX, label="a curriculum name")
    if not label:
        raise ClubRefusal("name_required", f"a curriculum needs a name between 1 and {CURRICULUM_NAME_MAX} characters; this one is {len(label)} after stripping", length=0, max=CURRICULUM_NAME_MAX)
    held = int(session.scalar(select(func.count()).select_from(AcademyCurriculum).where(AcademyCurriculum.organization_id == organization.id)) or 0)
    if held >= MAX_CURRICULA_PER_ORGANIZATION:
        raise ClubRefusal("curriculum_limit", f"{organization.name} runs {MAX_CURRICULA_PER_ORGANIZATION} curricula, which is the cap", held=held, limit=MAX_CURRICULA_PER_ORGANIZATION)
    if any(row.lower() == label.lower() for row in session.scalars(select(AcademyCurriculum.name).where(AcademyCurriculum.organization_id == organization.id))):
        raise ClubRefusal("curriculum_name_taken", f"{organization.name} already has a curriculum called {label!r}", name=label)
    minutes = int(weekly_minutes or 0)
    if not 0 <= minutes <= WEEKLY_MINUTES_MAX:
        raise ClubRefusal("weekly_minutes_range", f"a week of training is between 0 and {WEEKLY_MINUTES_MAX} minutes; {minutes} is not", value=minutes, low=0, high=WEEKLY_MINUTES_MAX)
    row = AcademyCurriculum(id=new_public_id("acm"), organization_id=organization.id, name=label, age_group=str(age_group).strip()[:24] or "open", weekly_minutes=minutes, phases=_phases(phases))
    session.add(row)
    session.commit()
    return {"organization": organization.slug, "curriculum": curriculum_view(session, row), "curricula": held + 1, "room_left": max(0, MAX_CURRICULA_PER_ORGANIZATION - held - 1)}


def update_curriculum(
    session: Session, user: User, ident: str, curriculum_ident: str, *, name: str | None = None, age_group: str | None = None, weekly_minutes: int | None = None, phases: Any = None
) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "curriculum.write")
    row = _curriculum(session, organization, curriculum_ident)
    changed: dict[str, Any] = {}
    if name is not None:
        label = _clip(name, CURRICULUM_NAME_MAX, label="a curriculum name")
        if not label:
            raise ClubRefusal("name_required", f"a curriculum name must be between 1 and {CURRICULUM_NAME_MAX} characters; this one is {len(label)}", length=len(label), max=CURRICULUM_NAME_MAX)
        if label.lower() != row.name.lower() and any(
            other.lower() == label.lower() for other in session.scalars(select(AcademyCurriculum.name).where(AcademyCurriculum.organization_id == organization.id, AcademyCurriculum.id != row.id))
        ):
            raise ClubRefusal("curriculum_name_taken", f"{organization.name} already has a curriculum called {label!r}", name=label)
        row.name = changed["name"] = label
    if age_group is not None:
        row.age_group = changed["age_group"] = str(age_group).strip()[:24] or "open"
    if weekly_minutes is not None:
        minutes = int(weekly_minutes)
        if not 0 <= minutes <= WEEKLY_MINUTES_MAX:
            raise ClubRefusal("weekly_minutes_range", f"a week of training is between 0 and {WEEKLY_MINUTES_MAX} minutes; {minutes} is not", value=minutes, low=0, high=WEEKLY_MINUTES_MAX)
        row.weekly_minutes = changed["weekly_minutes"] = minutes
    if phases is not None:
        row.phases = changed["phases"] = _phases(phases)
    session.commit()
    return {
        "curriculum": curriculum_view(session, row),
        "changed": changed,
        "rule": "the phases are the tenant's own words; they are not rows of the §65 drill catalogue and no drill is renamed by this door",
    }


def delete_curriculum(session: Session, user: User, ident: str, curriculum_ident: str) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "curriculum.write")
    row = _curriculum(session, organization, curriculum_ident)
    name = row.name
    repointed = int(session.scalar(select(func.count()).select_from(DevelopmentPlan).where(DevelopmentPlan.curriculum_id == row.id)) or 0)
    session.delete(row)
    session.commit()
    return {
        "deleted": True,
        "curriculum": name,
        "plans_repointed": repointed,
        "rule": "a plan keeps its focus and its goals when the curriculum it was written against goes: the column is set null rather than the row deleted, because the plan is the child's and the curriculum was the tenant's",
    }


def plan_view(session: Session, plan: DevelopmentPlan, reader: dict[str, Any]) -> dict[str, Any]:
    """One plan as one account may read it — the same rows, redacted by the right that opened the door.

    Two things are withheld from a guardian and the response counts them rather than hiding that they exist: a
    video window their consent did not cover, and feedback a coach chose not to share. Counts, not contents —
    which is what lets a parent ask for the missing piece instead of wondering whether there is one.
    """
    player = session.get(RealPlayer, plan.player_id)
    team = session.get(ClubTeam, plan.team_id) if plan.team_id else None
    curriculum = session.get(AcademyCurriculum, plan.curriculum_id) if plan.curriculum_id else None
    assessments = _assessments(session, plan)
    feedback = _feedback(session, plan)
    evidence = _evidence(session, plan)
    guardian_view = not reader["staff"]
    shown_feedback = [row for row in feedback if not guardian_view or bool(row.shared_with_guardian)]
    video_allowed = bool(reader["staff"]) or "video" in set(reader["scopes"])
    shown_evidence = [row for row in evidence if video_allowed]
    author = session.get(User, plan.author_user_id) if plan.author_user_id else None
    live_age = int(player.age) if player else 0
    return {
        "plan": {
            "id": plan.id,
            "status": plan.status,
            "focus": list(plan.focus or []),
            "goals": [dict(item) for item in (plan.goals or [])],
            "review_weeks": int(plan.review_weeks),
            "age_at_open": int(plan.age_at_open),
            "minor_at_open": bool(plan.minor_at_open),
            "created_at": plan.created_at.isoformat() if plan.created_at else None,
            "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
            "data_origin": plan.data_origin,
            "is_demo_data": bool(plan.is_demo_data),
        },
        "player": (
            {
                "slug": player.slug,
                "name": player.name,
                "age": live_age,
                "is_minor": _is_minor(live_age),
                "position": player.position,
                "overall": int(player.overall),
                "potential": int(player.potential),
                "path": f"/player/{player.slug}",
            }
            if player
            else None
        ),
        "team": ({"id": team.id, "name": team.name, "age_group": team.age_group} if team else None),
        "curriculum": ({"id": curriculum.id, "name": curriculum.name, "weekly_minutes": int(curriculum.weekly_minutes)} if curriculum else None),
        "author": ({"display_name": author.display_name, "role": author.role} if author else None),
        "assessments": [assessment_view(row) for row in assessments],
        "feedback": [feedback_view(row, guardian_view=guardian_view) for row in shown_feedback],
        "evidence": [evidence_view(session, row) for row in shown_evidence],
        "progress": progress_of(session, plan),
        "withheld": {
            "video_evidence": (len(evidence) - len(shown_evidence)),
            "coach_feedback": (len(feedback) - len(shown_feedback)),
            "rule": "a count, never a sentence: the plan says what you are not being shown and why, and the guardian's own consent row is the answer to the why",
            "why_video": (None if video_allowed else f"the consent that names {player.slug if player else 'this player'} covers {sorted(set(reader['scopes']))}, which does not include 'video'"),
        },
        "your_standing": {
            "role": reader["role"],
            "staff": reader["staff"],
            "guardian_of_this_child": reader["guardian"],
            "scopes_held": list(reader["scopes"]),
            "read_through": ("plan.read_all" if reader["staff"] else "plan.read_own_child" if reader["guardian"] else "none"),
        },
        "aged_past_minority": bool(plan.minor_at_open and live_age >= MINOR_AGE),
        "figures_from": "`development_plans` and its own child rows, read on this request; the player's live rating comes from `real_players`",
        "limitations": limitations(),
        "demo_data": False,
    }


def assessment_view(row: PlanAssessment) -> dict[str, Any]:
    ratings = {str(axis): int(score) for axis, score in (row.ratings or {}).items()}
    return {
        "id": row.id,
        "assessed_on": row.assessed_on,
        "ratings": ratings,
        "axes_missing": [axis for axis in AXES if axis not in ratings],
        "mean_rating": (round(sum(ratings.values()) / len(ratings), 1) if ratings else None),
        "strengths": row.strengths,
        "areas": row.areas,
        "overall_observed": int(row.overall_observed),
        "next_focus": row.next_focus,
        "measured_from": "`overall_observed` is the world's rating for the player copied on the day this review was written",
    }


def feedback_view(row: CoachFeedback, *, guardian_view: bool = False) -> dict[str, Any]:
    return {
        "id": row.id,
        "message": row.message,
        "shared_with_guardian": bool(row.shared_with_guardian),
        "written_at": row.created_at.isoformat() if row.created_at else None,
        "seen_as": ("guardian copy" if guardian_view else "staff copy"),
    }


def evidence_view(session: Session, row: PlanVideoEvidence) -> dict[str, Any]:
    asset = session.get(VideoAsset, row.asset_id) if row.asset_id else None
    return {
        "id": row.id,
        "label": row.label,
        "t_start": float(row.t_start),
        "t_end": float(row.t_end),
        "window_seconds": round(float(row.t_end) - float(row.t_start), 2),
        "assessment_id": row.assessment_id,
        "clip_present": asset is not None,
        "clip": ({"id": asset.id, "title": asset.title, "duration_s": round(float(asset.duration_s), 2), "owner": asset.owner_id} if asset else None),
        "linked_at": row.created_at.isoformat() if row.created_at else None,
        "playback": "the clip itself is M5's and answers only to its owner; this row is a citation — a label and a window — not a way to watch it",
    }


def list_plans(session: Session, user: User, ident: str) -> dict[str, Any]:
    """Every plan of the tenant for staff, and only the named child's plan for a guardian."""
    organization, member = standing(session, user, ident)
    staff = access.may(member.role, "plan.read_all")
    scoped = access.may(member.role, "plan.read_own_child")
    if not staff and not scoped:
        # `require` gives the 403 with the matrix beside it: this caller's tenant already is theirs, and the
        # open question is which right their role is short of.
        require(session, user, ident, "plan.read_all")
    claims = {row.player_id for row in consents_of_guardian(session, organization, user)}
    rows = list(session.scalars(select(DevelopmentPlan).where(DevelopmentPlan.organization_id == organization.id).order_by(DevelopmentPlan.created_at, DevelopmentPlan.id)))
    if not staff:
        rows = [row for row in rows if row.player_id in claims]
    items = []
    for plan in rows:
        player = session.get(RealPlayer, plan.player_id)
        items.append(
            {
                "id": plan.id,
                "player": ({"slug": player.slug, "name": player.name, "age": int(player.age), "is_minor": _is_minor(player.age)} if player else None),
                "status": plan.status,
                "focus": list(plan.focus or []),
                "goals": len(plan.goals or []),
                "review_weeks": int(plan.review_weeks),
                "assessments": int(session.scalar(select(func.count()).select_from(PlanAssessment).where(PlanAssessment.plan_id == plan.id)) or 0),
                "progress": progress_of(session, plan)["overall_change"],
                "path": f"/club/{organization.slug}/plans/{plan.id}",
            }
        )
    return {
        "organization": organization.slug,
        "items": items,
        "total": len(items),
        "minors_in_list": sum(1 for item in items if (item["player"] or {}).get("is_minor")),
        "limit": MAX_PLANS_PER_ORGANIZATION,
        "role": member.role,
        "read_through": ("plan.read_all" if staff else "plan.read_own_child"),
        # A listing prints one derived figure, so it prints where it comes from: `progress` here is the same
        # `overall_change` the plan read publishes, and `null` means the plan has fewer than two reviews.
        "formulas": {"progress": "last `overall_observed` minus first over this plan's own reviews; null with one or no review, and the axis-by-axis direction is only in `GET {ident}/plans/{plan}`"},
        "rule": (
            "a guardian reads the plans of the children their consent rows name — you hold no granted consent in this tenant, so the answer is an empty list rather than a refusal"
            if not staff and not claims
            else "a listing and a read agree: every plan here is one this caller may open, and a plan they may not open is not here at all"
        ),
        "demo_data": False,
    }


def consents_of_guardian(session: Session, organization: Organization, user: User, *, granted_only: bool = True) -> list[GuardianConsent]:
    statement = select(GuardianConsent).where(GuardianConsent.organization_id == organization.id, GuardianConsent.guardian_user_id == user.id)
    if granted_only:
        statement = statement.where(GuardianConsent.state == "granted")
    return list(session.scalars(statement.order_by(GuardianConsent.created_at, GuardianConsent.id)))


def open_plan(
    session: Session,
    user: User,
    ident: str,
    *,
    player: str,
    focus: Any = None,
    goals: Any = None,
    review_weeks: int = 6,
    curriculum: str | None = None,
    team: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    """Write the first page of one child's development plan — and, for a child, only with a guardian's yes."""
    organization, _ = require(session, user, ident, "plan.write")
    person = _player_of(session, organization, player)
    weeks = int(review_weeks or REVIEW_WEEKS_MAX)
    if not REVIEW_WEEKS_MIN <= weeks <= REVIEW_WEEKS_MAX:
        raise ClubRefusal(
            "review_weeks_range",
            f"a review is due every {REVIEW_WEEKS_MIN} to {REVIEW_WEEKS_MAX} weeks; {weeks} is not a cadence this tier can check against",
            value=weeks,
            low=REVIEW_WEEKS_MIN,
            high=REVIEW_WEEKS_MAX,
        )
    if str(status) not in PLAN_STATUSES:
        raise ClubRefusal("unknown_status", f"{status!r} is not a plan status", status=str(status), statuses=list(PLAN_STATUSES))
    consent = _require_scope(session, organization, person, "plan")
    held = int(session.scalar(select(func.count()).select_from(DevelopmentPlan).where(DevelopmentPlan.organization_id == organization.id)) or 0)
    if held >= MAX_PLANS_PER_ORGANIZATION:
        raise ClubRefusal("plan_limit", f"{organization.name} holds {MAX_PLANS_PER_ORGANIZATION} plans, which is the cap", held=held, limit=MAX_PLANS_PER_ORGANIZATION)
    live = session.scalar(select(DevelopmentPlan.id).where(DevelopmentPlan.organization_id == organization.id, DevelopmentPlan.player_id == person.id, DevelopmentPlan.status != "closed"))
    if live:
        raise ClubRefusal(
            "plan_already_open",
            f"{person.name} already has a plan here that is not closed ({live}); close it before opening another, so the history of one child is never two half-plans",
            player=person.slug,
            plan=live,
        )
    curriculum_row = _curriculum(session, organization, curriculum) if curriculum else None
    team_row = resolve_team(session, organization, team) if team else None
    plan = DevelopmentPlan(
        id=new_public_id("idp"),
        organization_id=organization.id,
        player_id=person.id,
        author_user_id=user.id,
        status=str(status),
        focus=_focus(focus),
        goals=_goals(goals),
        review_weeks=weeks,
        curriculum_id=(curriculum_row.id if curriculum_row else None),
        team_id=(team_row.id if team_row else None),
        age_at_open=int(person.age),
        minor_at_open=_is_minor(person.age),
    )
    session.add(plan)
    session.commit()
    reader = _reader(session, organization, user, person.id)
    return {
        **plan_view(session, plan, reader),
        "organization": organization.slug,
        "consented_by": ({"consent": consent.id, "guardian": consent.guardian_user_id, "scopes": _scope_names(consent.scopes)} if consent else None),
        "not_stored": " ".join(field for field in RESTRICTED_FIELDS) + " — there is no column here for any of them",
        "rule": "one child, one live plan per tenant; a closed one stays for the record and the next season starts a new row",
    }


def get_plan(session: Session, user: User, ident: str, plan_ident: str) -> dict[str, Any]:
    """One plan, read through the right that opens it — and a child nobody here consented for is not in the answer."""
    organization, member = standing(session, user, ident)
    plan = _plan(session, organization, plan_ident)
    reader = _reader(session, organization, user, plan.player_id)
    if not reader["can_read"]:
        if access.may(member.role, "plan.read_own_child"):
            # A parent asking for another family's child: answered as a plan that does not exist, because the
            # useful half of a 403 — "your role is below this" — would tell them the row is real.
            raise ClubRefusal("no_such_plan", f"no development plan of {organization.slug} that you may read answers to {str(plan_ident)!r}", ident=str(plan_ident), organization=organization.slug)
        raise ClubRefusal(
            "insufficient_role",
            f"the role {member.role!r} on this organisation does not hold any plan right",
            organization=organization.slug,
            permission="plan.read_all",
            **access.grant(member.role, member.status),
        )
    return {**plan_view(session, plan, reader), "organization": organization.slug, "integrity": academy_problems(session, user), "demo_data": False}


def update_plan(
    session: Session, user: User, ident: str, plan_ident: str, *, status: str | None = None, focus: Any = None, goals: Any = None, review_weeks: int | None = None, curriculum: str | None = None
) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "plan.write")
    plan = _plan(session, organization, plan_ident)
    player = session.get(RealPlayer, plan.player_id)
    reader = _reader(session, organization, user, plan.player_id)
    if str(plan.status) == "closed" and (status is None or str(status) != "draft"):
        raise ClubRefusal(
            "plan_is_closed",
            f"{(player.name if player else 'this player')}'s plan is closed; open a new one rather than writing into the record of the season that ended",
            plan=plan.id,
            status=plan.status,
        )
    if status is not None and str(status) not in PLAN_STATUSES:
        raise ClubRefusal("unknown_status", f"{status!r} is not a plan status", status=str(status), statuses=list(PLAN_STATUSES))
    if review_weeks is not None and not REVIEW_WEEKS_MIN <= int(review_weeks) <= REVIEW_WEEKS_MAX:
        raise ClubRefusal(
            "review_weeks_range",
            f"a review is due every {REVIEW_WEEKS_MIN} to {REVIEW_WEEKS_MAX} weeks; {int(review_weeks)} is not",
            value=int(review_weeks),
            low=REVIEW_WEEKS_MIN,
            high=REVIEW_WEEKS_MAX,
        )
    # Both validators run before anything is assigned, and the consent is re-asked before the write: a refusal
    # half-way through an edit would leave a plan with a new focus and no answer about whether it was stored.
    new_focus = _focus(focus) if focus is not None else None
    new_goals = _goals(goals) if goals is not None else None
    if (new_focus is not None or new_goals is not None) and player is not None:
        _require_scope(session, organization, player, "plan")
    changed: dict[str, Any] = {}
    if status is not None:
        plan.status = changed["status"] = str(status)
    if new_focus is not None:
        plan.focus = changed["focus"] = new_focus
    if new_goals is not None:
        plan.goals = changed["goals"] = new_goals
    if review_weeks is not None:
        plan.review_weeks = changed["review_weeks"] = int(review_weeks)
    if curriculum is not None:
        plan.curriculum_id = changed["curriculum"] = _curriculum(session, organization, curriculum).id
    session.commit()
    return {
        **plan_view(session, plan, reader),
        "changed": changed,
        "rule": "editing a plan re-asks the consent that let it be opened: a guardian who withdrew `plan` stops the next edit, not only the next plan",
        "demo_data": False,
    }


def add_assessment(session: Session, user: User, ident: str, plan_ident: str, *, assessed_on: str, ratings: Any = None, strengths: str = "", areas: str = "", next_focus: str = "") -> dict[str, Any]:
    """§40's Assessment: five axes rated on a day, and the world's rating copied down beside them."""
    organization, _ = require(session, user, ident, "plan.write")
    plan = _plan(session, organization, plan_ident)
    player = session.get(RealPlayer, plan.player_id)
    if player is None:
        raise ClubRefusal("no_such_player", "the player this plan was written for is no longer in the world, so nothing can be assessed", plan=plan.id)
    consent = _require_scope(session, organization, player, "assessment")
    rows = _assessments(session, plan)
    if len(rows) >= MAX_ASSESSMENTS_PER_PLAN:
        raise ClubRefusal("assessment_limit", f"this plan already holds {MAX_ASSESSMENTS_PER_PLAN} assessments, which is the cap", held=len(rows), limit=MAX_ASSESSMENTS_PER_PLAN)
    day = _iso(assessed_on, label="an assessment date")
    if date.fromisoformat(day) > _today():
        raise ClubRefusal(
            "date_in_future",
            f"a review cannot be dated {day}: today is {_today().isoformat()}, and a rating of a session that has not happened is a guess written as a measurement",
            value=day,
            today=_today().isoformat(),
        )
    if rows and day < rows[-1].assessed_on:
        raise ClubRefusal(
            "date_before_plan",
            f"{day} is earlier than the {len(rows)} review(s) already on this plan, the newest dated {rows[-1].assessed_on}; a back-dated review would rewrite which number is 'first' in the progress figures",
            value=day,
            newest=rows[-1].assessed_on,
            assessments=len(rows),
        )
    if str(plan.status) == "closed":
        raise ClubRefusal("plan_is_closed", f"{player.name}'s plan is closed, so a new review would be written into a season that ended", plan=plan.id, status=plan.status)
    row = PlanAssessment(
        id=new_public_id("pas"),
        plan_id=plan.id,
        assessor_user_id=user.id,
        assessed_on=day,
        ratings=_ratings(ratings),
        strengths=_clip(strengths, ASSESSMENT_TEXT_MAX, label="a strength line"),
        areas=_clip(areas, ASSESSMENT_TEXT_MAX, label="an improvement line"),
        overall_observed=int(player.overall),
        next_focus=_clip(next_focus, NEXT_FOCUS_MAX, label="the next focus"),
    )
    session.add(row)
    session.commit()
    return {
        "assessment": assessment_view(row),
        "progress": progress_of(session, plan),
        "consented_by": (consent.id if consent else None),
        "observed_from": f"`real_players.overall` for {player.slug} read on this request: {int(player.overall)}",
        "demo_data": False,
    }


def add_feedback(session: Session, user: User, ident: str, plan_ident: str, *, message: str, shared_with_guardian: bool = True) -> dict[str, Any]:
    """§40's Coach Feedback: one sentence to one player, and the choice about whether the guardian reads it."""
    organization, _ = require(session, user, ident, "plan.write")
    plan = _plan(session, organization, plan_ident)
    player = session.get(RealPlayer, plan.player_id)
    if player is None:
        raise ClubRefusal("no_such_player", "the player this plan was written for is no longer in the world, so there is nobody to write to", plan=plan.id)
    _require_scope(session, organization, player, "feedback")
    text = _clip(message, FEEDBACK_MAX, label="a feedback message")
    if not text:
        # `feedback_limit` already means *this plan holds too many rows*, and a caller who is told that about an
        # empty message will go delete a row they did not need to delete.
        raise ClubRefusal("feedback_required", f"feedback needs words between 1 and {FEEDBACK_MAX} characters; this one is empty after stripping", length=0, max=FEEDBACK_MAX)
    held = len(_feedback(session, plan))
    if held >= MAX_FEEDBACK_PER_PLAN:
        raise ClubRefusal("feedback_limit", f"this plan already holds {MAX_FEEDBACK_PER_PLAN} feedback rows, which is the cap", held=held, limit=MAX_FEEDBACK_PER_PLAN)
    row = CoachFeedback(id=new_public_id("cfb"), plan_id=plan.id, coach_user_id=user.id, message=text, shared_with_guardian=bool(shared_with_guardian))
    session.add(row)
    session.commit()
    return {
        "feedback": feedback_view(row),
        "feedback_rows": held + 1,
        "shared_with_guardian": bool(row.shared_with_guardian),
        "rule": "a message held back from the guardian still counts toward `withheld.coach_feedback`, so a parent can ask for it instead of guessing",
        "demo_data": False,
    }


def link_evidence(session: Session, user: User, ident: str, plan_ident: str, *, clip: str, label: str = "", t_start: float = 0.0, t_end: float = 0.0, assessment: str | None = None) -> dict[str, Any]:
    """§40's Video Evidence: cite a window of a clip somebody uploaded to M5, with the consent that allows it."""
    organization, _ = require(session, user, ident, "plan.write")
    plan = _plan(session, organization, plan_ident)
    player = session.get(RealPlayer, plan.player_id)
    if player is None:
        raise ClubRefusal("no_such_player", "the player this plan was written for is no longer in the world, so nothing can be cited for them", plan=plan.id)
    asset = session.get(VideoAsset, str(clip))
    if asset is None:
        raise ClubRefusal("no_such_clip", f"no uploaded clip answers to {str(clip)!r}; §40 cites footage M5 already holds, it does not take an upload", clip=str(clip))
    if asset.owner_id != user.id:
        # Somebody else's upload answers as absent: the clip exists, and whose it is is not this caller's to learn.
        raise ClubRefusal("no_such_clip", f"no clip of yours answers to {str(clip)!r}, and a plan cites only footage the author uploaded", clip=str(clip), reason="owned_by_another_account")
    start, end = float(t_start or 0.0), float(t_end or 0.0)
    duration = float(asset.duration_s or 0.0)
    if end <= start:
        raise ClubRefusal("evidence_window", f"a cited window needs an end after its start; this one is {start} to {end}", start=start, end=end)
    if end > duration:
        raise ClubRefusal("evidence_window", f"{duration}s of footage exists on this clip and the window asked for {end}s", start=start, end=end, duration=duration)
    assessment_row = None
    if assessment:
        assessment_row = session.scalar(select(PlanAssessment).where(PlanAssessment.plan_id == plan.id, PlanAssessment.id == str(assessment)))
        if assessment_row is None:
            raise ClubRefusal("no_such_assessment", f"no assessment of this plan answers to {str(assessment)!r}", assessment=str(assessment), plan=plan.id)
    rows = _evidence(session, plan)
    if len(rows) >= MAX_EVIDENCE_PER_PLAN:
        raise ClubRefusal("evidence_limit", f"this plan already cites {MAX_EVIDENCE_PER_PLAN} clips, which is the cap", held=len(rows), limit=MAX_EVIDENCE_PER_PLAN)
    if any(row.asset_id == asset.id and float(row.t_start) == start and float(row.t_end) == end for row in rows):
        raise ClubRefusal("already_linked", f"this plan already cites {start}s to {end}s of that clip", clip=asset.id, start=start, end=end)
    consent = _require_scope(session, organization, player, "video")
    row = PlanVideoEvidence(
        id=new_public_id("pve"),
        plan_id=plan.id,
        assessment_id=(assessment_row.id if assessment_row else None),
        asset_id=asset.id,
        label=_clip(label, EVIDENCE_LABEL_MAX, label="a clip label"),
        t_start=start,
        t_end=end,
    )
    session.add(row)
    session.commit()
    return {
        "evidence": evidence_view(session, row),
        "evidence_rows": len(rows) + 1,
        "consented_by": (consent.id if consent else None),
        "rule": "a citation is a label and two numbers: watching the clip still answers to M5's owner-only door, and nothing here hands a token to anybody",
        "demo_data": False,
    }


def unlink_evidence(session: Session, user: User, ident: str, plan_ident: str, evidence_ident: str) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "plan.write")
    plan = _plan(session, organization, plan_ident)
    row = session.scalar(select(PlanVideoEvidence).where(PlanVideoEvidence.plan_id == plan.id, PlanVideoEvidence.id == str(evidence_ident)))
    if row is None:
        raise ClubRefusal("no_such_evidence", f"this plan cites no footage answering to {str(evidence_ident)!r}", evidence=str(evidence_ident), plan=plan.id)
    label = row.label
    session.delete(row)
    session.commit()
    return {"deleted": True, "evidence": label, "rule": "the citation goes and the clip stays: an upload belongs to the account that uploaded it, and unlinking it from a plan edits nobody's file"}


def _guardian_standing(session: Session, user: User, ident: str) -> tuple[Organization, OrganizationMember]:
    """The second question behind `consent.grant_own`, which the matrix alone cannot ask.

    `require()` reads a role table, and every staff role holds `consent.grant_own` there — so a door that asked
    only that would let a tenant's own director mint the guardian's yes that gates that tenant's children. The
    published scoped rule says the claim has to come from a `parent` standing, and a promise the matrix cannot
    keep is a promise the door has to keep.
    """
    organization, member = require(session, user, ident, "consent.grant_own")
    if member.role != "parent":
        rule = access.matrix()["scoped"]["consent.grant_own"]
        grant = access.grant(member.role, member.status)
        raise ClubRefusal(
            "insufficient_role",
            f"the role {member.role!r} ({member.status}) may not claim a child: {rule}",
            organization=organization.slug,
            permission="consent.grant_own",
            role=member.role,
            status=member.status,
            permissions_held=grant["permissions"],
            known_role=grant["known_role"],
            why=grant["why"],
            # The two figures `require()`'s version of this refusal cannot carry: the standing the right is
            # scoped to, and the published sentence that scopes it, so the answer quotes its own rule.
            required_role="parent",
            scoped_rule=rule,
        )
    return organization, member


def grant_consent(session: Session, user: User, ident: str, *, player: str, scopes: Any = None) -> dict[str, Any]:
    """A guardian's yes, recorded as a row. Self-declared, scoped, and the only way a minor's plan can open."""
    organization, _ = _guardian_standing(session, user, ident)
    person = _player_of(session, organization, player)
    held = len(consents_of_guardian(session, organization, user, granted_only=False))
    existing = session.scalar(select(GuardianConsent).where(GuardianConsent.organization_id == organization.id, GuardianConsent.player_id == person.id, GuardianConsent.guardian_user_id == user.id))
    if existing is None and held >= MAX_CONSENTS_PER_GUARDIAN:
        raise ClubRefusal("consent_limit", f"this account has claimed {MAX_CONSENTS_PER_GUARDIAN} children in one tenant, which is the cap", held=held, limit=MAX_CONSENTS_PER_GUARDIAN)
    granted = _scopes(scopes)
    if existing is None:
        existing = GuardianConsent(id=new_public_id("gcn"), organization_id=organization.id, guardian_user_id=user.id, player_id=person.id, state="granted", scopes=granted)
        session.add(existing)
    else:
        existing.state = "granted"
        existing.scopes = granted
    session.commit()
    return {
        "organization": organization.slug,
        "consent": consent_view(session, existing),
        "self_declared": "this platform cannot verify that an account is a child's guardian; the row is the claim, and the audit of who claimed what is the whole of the control",
        "rule": "scopes are a ceiling, not a request: nothing under a scope that is not listed here may be written about this child",
        "demo_data": False,
    }


def consent_view(session: Session, row: GuardianConsent) -> dict[str, Any]:
    player = session.get(RealPlayer, row.player_id)
    guardian = session.get(User, row.guardian_user_id)
    plans = int(session.scalar(select(func.count()).select_from(DevelopmentPlan).where(DevelopmentPlan.organization_id == row.organization_id, DevelopmentPlan.player_id == row.player_id)) or 0)
    return {
        "id": row.id,
        "player": ({"slug": player.slug, "name": player.name, "age": int(player.age), "is_minor": _is_minor(player.age)} if player else None),
        "guardian": ({"email": guardian.email, "display_name": guardian.display_name} if guardian else None),
        "state": row.state,
        "scopes": _scope_names(row.scopes),
        "plans_for_this_child": plans,
        "granted_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_consents(session: Session, user: User, ident: str) -> dict[str, Any]:
    """Which children have a yes on file, from whose account, and for what — staff see the tenant's, a guardian sees their own."""
    organization, member = standing(session, user, ident)
    staff = access.may(member.role, "plan.read_all")
    if not staff and not access.may(member.role, "consent.grant_own"):
        raise ClubRefusal(
            "insufficient_role",
            f"the role {member.role!r} holds no consent right on this organisation",
            organization=organization.slug,
            permission="consent.grant_own",
            **access.grant(member.role, member.status),
        )
    rows = (
        list(session.scalars(select(GuardianConsent).where(GuardianConsent.organization_id == organization.id).order_by(GuardianConsent.created_at, GuardianConsent.id)))
        if staff
        else consents_of_guardian(session, organization, user, granted_only=False)
    )
    minors = 0
    for row in rows:
        player = session.get(RealPlayer, row.player_id)
        if player is not None and _is_minor(player.age):
            minors += 1
    return {
        "organization": organization.slug,
        "items": [consent_view(session, row) for row in rows],
        "total": len(rows),
        "under_18": minors,
        "seen_as": ("tenant" if staff else "own_child"),
        "rule": "a tenant with a minor on a sheet and no consent row here is a tenant that cannot write a plan for them — `GET /club/academy/{ident}/plans` will say why",
        "demo_data": False,
    }


def withdraw_consent(session: Session, user: User, ident: str, player: str) -> dict[str, Any]:
    """Take the yes back. New writes stop at once; the rows already written stay until somebody erases them."""
    organization, _ = _guardian_standing(session, user, ident)
    person = _player_of(session, organization, player, on_sheet=False)
    row = session.scalar(select(GuardianConsent).where(GuardianConsent.organization_id == organization.id, GuardianConsent.player_id == person.id, GuardianConsent.guardian_user_id == user.id))
    if row is None:
        raise ClubRefusal(
            "no_such_consent", f"you have no consent row for {person.name} in {organization.slug}, so there is nothing here for you to withdraw", player=person.slug, organization=organization.slug
        )
    row.state = "withdrawn"
    session.commit()
    return {
        "consent": consent_view(session, row),
        "withdrawn": True,
        "plans_left_open": int(
            session.scalar(
                select(func.count()).select_from(DevelopmentPlan).where(DevelopmentPlan.player_id == person.id, DevelopmentPlan.organization_id == organization.id, DevelopmentPlan.status != "closed")
            )
            or 0
        ),
        "rule": "withdrawal stops the next write and reads nothing new; it does not delete the record, because a tenant must still be able to say what it held and when. Deletion is the erase door, and a guardian may use it for their own child",
    }


def _erase_guard(session: Session, user: User, ident: str, player_ident: str) -> tuple[Organization, RealPlayer, dict[str, Any]]:
    """Who may see or destroy one child's rows: staff with `plan.erase`, or the guardian who claimed them."""
    organization, member = standing(session, user, ident)
    person = _player_of(session, organization, player_ident, on_sheet=False)
    reader = _reader(session, organization, user, person.id)
    claims = int(
        session.scalar(
            select(func.count())
            .select_from(GuardianConsent)
            .where(GuardianConsent.organization_id == organization.id, GuardianConsent.player_id == person.id, GuardianConsent.guardian_user_id == user.id)
        )
        or 0
    )
    reader["may_erase"] = bool(reader["may_erase"]) or claims > 0
    if not reader["may_erase"]:
        if access.may(member.role, "plan.read_own_child"):
            raise ClubRefusal(
                "no_such_player", f"no child of {organization.slug} whose own academy data you may reach answers to {str(player_ident)!r}", ident=str(player_ident), organization=organization.slug
            )
        require(session, user, ident, "plan.erase")
    return organization, person, reader


def _rows_about(session: Session, organization: Organization, player: RealPlayer) -> dict[str, int]:
    plan_ids = list(session.scalars(select(DevelopmentPlan.id).where(DevelopmentPlan.organization_id == organization.id, DevelopmentPlan.player_id == player.id)))
    counts = {
        "development_plans": len(plan_ids),
        "plan_assessments": 0,
        "coach_feedback": 0,
        "plan_video_evidence": 0,
        "guardian_consents": int(
            session.scalar(select(func.count()).select_from(GuardianConsent).where(GuardianConsent.organization_id == organization.id, GuardianConsent.player_id == player.id)) or 0
        ),
    }
    if plan_ids:
        counts["plan_assessments"] = int(session.scalar(select(func.count()).select_from(PlanAssessment).where(PlanAssessment.plan_id.in_(plan_ids))) or 0)
        counts["coach_feedback"] = int(session.scalar(select(func.count()).select_from(CoachFeedback).where(CoachFeedback.plan_id.in_(plan_ids))) or 0)
        counts["plan_video_evidence"] = int(session.scalar(select(func.count()).select_from(PlanVideoEvidence).where(PlanVideoEvidence.plan_id.in_(plan_ids))) or 0)
    return counts


def player_data_inventory(session: Session, user: User, ident: str, player: str) -> dict[str, Any]:
    """Everything this tenant holds about one child, table by table — the answer to *what do you have on them?*"""
    organization, person, reader = _erase_guard(session, user, ident, player)
    counts = _rows_about(session, organization, person)
    return {
        "organization": organization.slug,
        "player": {"slug": person.slug, "name": person.name, "age": int(person.age), "is_minor": _is_minor(person.age)},
        "held_by_this_tenant": counts,
        "total_rows": sum(counts.values()),
        "columns": {table: list(fields) for table, fields in STORED_FIELDS.items()},
        "never_stored": list(RESTRICTED_FIELDS),
        "outside_this_tenant": {
            "generated_world": f"the `real_players` row for {person.slug} is the world's, not the tenant's — synthetic, and not this door's to delete",
            "other_tenants": "another club's plans about the same person are not listed and not erased here; §39's one sentence cuts both ways",
            "uploaded_clips": "the footage cited by `plan_video_evidence` belongs to whoever uploaded it to M5; erasing a plan unlinks the citation and leaves the file",
        },
        "seen_as": ("staff" if reader["staff"] else "guardian"),
        "demo_data": False,
    }


def erase_player_data(session: Session, user: User, ident: str, player: str, *, confirm: bool = False) -> dict[str, Any]:
    """§40's Deletion: every row this tenant holds about one child, gone, with the counts printed on both sides."""
    organization, person, _ = _erase_guard(session, user, ident, player)
    counts = _rows_about(session, organization, person)
    if not confirm:
        raise ClubRefusal(
            "erase_confirmation",
            f"erasing {(person.name)!r} would remove {sum(counts.values())} rows of {organization.name}, and nothing here can undo it — send confirm=true to go ahead",
            **counts,
            total=sum(counts.values()),
            confirm_required=True,
        )
    plans = list(session.scalars(select(DevelopmentPlan).where(DevelopmentPlan.organization_id == organization.id, DevelopmentPlan.player_id == person.id)))
    clips_linked = sum(1 for plan in plans for row in _evidence(session, plan) if row.asset_id)
    consents = list(session.scalars(select(GuardianConsent).where(GuardianConsent.organization_id == organization.id, GuardianConsent.player_id == person.id)))
    for plan in plans:
        session.delete(plan)
    for consent in consents:
        session.delete(consent)
    session.commit()
    after = _rows_about(session, organization, person)
    return {
        "organization": organization.slug,
        "player": person.slug,
        "before": counts,
        "after": after,
        "rows_removed": sum(counts.values()) - sum(after.values()),
        "clips_unlinked": clips_linked,
        "consents_removed": len(consents),
        "rule": "the plans go with their assessments, feedback and citations; the consent rows go too, because a consent that names no data has nothing to be about",
        "not_touched": "the world's `real_players` row, the tenant's team sheet, any other tenant's rows, and the uploaded clip files themselves",
        "demo_data": False,
    }


def erase_plan(session: Session, user: User, ident: str, plan_ident: str, *, confirm: bool = False) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "plan.erase")
    plan = _plan(session, organization, plan_ident)
    player = session.get(RealPlayer, plan.player_id)
    counts = {
        "assessments": int(session.scalar(select(func.count()).select_from(PlanAssessment).where(PlanAssessment.plan_id == plan.id)) or 0),
        "coach_feedback": int(session.scalar(select(func.count()).select_from(CoachFeedback).where(CoachFeedback.plan_id == plan.id)) or 0),
        "video_citations": int(session.scalar(select(func.count()).select_from(PlanVideoEvidence).where(PlanVideoEvidence.plan_id == plan.id)) or 0),
    }
    if not confirm:
        raise ClubRefusal(
            "erase_confirmation", f"this plan holds {sum(counts.values())} rows of review and feedback; send confirm=true to erase them with it", plan=plan.id, **counts, confirm_required=True
        )
    session.delete(plan)
    session.commit()
    return {
        "deleted": True,
        "plan": plan_ident,
        "player": (player.slug if player else None),
        "rows_removed": sum(counts.values()),
        "rule": "closing a plan keeps the record; erasing one removes it, and only a role holding `plan.erase` may ask for that",
        "demo_data": False,
    }


def academy_tables_present(session: Session) -> bool:
    names = inspect(session.get_bind()).get_table_names()
    return all(table in names for table in STORED_FIELDS)


def academy_ready(session: Session) -> bool:
    return academy_tables_present(session) and bool(session.scalar(select(User.id).limit(1)))


def academy_counts(session: Session) -> dict[str, Any]:
    if not academy_tables_present(session):
        return {
            "curricula": 0,
            "plans": 0,
            "assessments": 0,
            "coach_feedback": 0,
            "video_citations": 0,
            "consents_granted": 0,
            "consents_withdrawn": 0,
            "rule": "the academy tables are not in this database yet; nothing here is counted because nothing here exists",
        }
    plans = int(session.scalar(select(func.count()).select_from(DevelopmentPlan)) or 0)
    return {
        "curricula": int(session.scalar(select(func.count()).select_from(AcademyCurriculum)) or 0),
        "plans": plans,
        "plans_of_minors": int(session.scalar(select(func.count()).select_from(DevelopmentPlan).where(DevelopmentPlan.minor_at_open.is_(True))) or 0),
        "closed_plans": int(session.scalar(select(func.count()).select_from(DevelopmentPlan).where(DevelopmentPlan.status == "closed")) or 0),
        "assessments": int(session.scalar(select(func.count()).select_from(PlanAssessment)) or 0),
        "coach_feedback": int(session.scalar(select(func.count()).select_from(CoachFeedback)) or 0),
        "feedback_held_from_guardian": int(session.scalar(select(func.count()).select_from(CoachFeedback).where(CoachFeedback.shared_with_guardian.is_(False))) or 0),
        "video_citations": int(session.scalar(select(func.count()).select_from(PlanVideoEvidence)) or 0),
        "citations_without_clip": int(session.scalar(select(func.count()).select_from(PlanVideoEvidence).where(PlanVideoEvidence.asset_id.is_(None))) or 0),
        "consents_granted": int(session.scalar(select(func.count()).select_from(GuardianConsent).where(GuardianConsent.state == "granted")) or 0),
        "consents_withdrawn": int(session.scalar(select(func.count()).select_from(GuardianConsent).where(GuardianConsent.state == "withdrawn")) or 0),
        "rule": "row counts of every tenant on the platform, so a page can say how much academy data exists; nothing here names a child",
    }


def academy_problems(session: Session, user: User) -> dict[str, Any]:
    """The invariants §40 exists to hold, checked over the caller's own tenants.

    Each one is a way the consent rule could stop being true without any single row looking wrong: a minor's
    plan with no granted consent behind it, two live plans for one child, a rating outside the published scale,
    a citation pointing at another plan's assessment, a plan of one tenant aimed at a curriculum of another.
    """
    if not academy_tables_present(session):
        return {
            "clean": False,
            "problems": ["the academy tables are not in this database"],
            "checked": {"organizations": 0, "plans": 0, "consent_rows": 0},
            "rule": "an un-migrated database is reported, not assumed sound",
        }
    problems: list[str] = []
    organizations = list(
        session.scalars(
            select(Organization).join(OrganizationMember, OrganizationMember.organization_id == Organization.id).where(OrganizationMember.user_id == user.id, OrganizationMember.status == "active")
        )
    )
    plans = 0
    consent_rows = 0
    for organization in organizations:
        rows = list(session.scalars(select(DevelopmentPlan).where(DevelopmentPlan.organization_id == organization.id)))
        plans += len(rows)
        for plan in rows:
            player = session.get(RealPlayer, plan.player_id)
            if player is None:
                problems.append(f"{plan.id}: a plan whose player is no longer in the world")
                continue
            if _is_minor(player.age) and not _has_plan_consent(session, organization, player):
                problems.append(f"{plan.id}: {player.name} is {int(player.age)} and has no granted consent covering 'plan', so this plan should not exist")
            if plan.curriculum_id and not session.scalar(select(AcademyCurriculum.id).where(AcademyCurriculum.id == plan.curriculum_id, AcademyCurriculum.organization_id == organization.id)):
                problems.append(f"{plan.id}: its curriculum belongs to another tenant")
            if plan.team_id and not session.scalar(select(ClubTeam.id).where(ClubTeam.id == plan.team_id, ClubTeam.organization_id == organization.id)):
                problems.append(f"{plan.id}: its team belongs to another tenant")
            for assessment in _assessments(session, plan):
                for axis, score in (assessment.ratings or {}).items():
                    if str(axis) not in AXES:
                        problems.append(f"{assessment.id}: rated {axis!r}, which is not one of the published axes")
                    elif not 0 <= int(score) <= 100:
                        problems.append(f"{assessment.id}: the {axis} rating is {score}, outside the published 0 to 100")
                if date.fromisoformat(assessment.assessed_on) > _today():
                    problems.append(f"{assessment.id}: dated {assessment.assessed_on}, which has not happened yet")
            seen: set[tuple[str, float, float]] = set()
            for row in _evidence(session, plan):
                if row.asset_id is None:
                    continue
                # The same test `link_evidence` applies: two windows of one clip are one review of a first touch
                # and another of a second, which is ordinary. The same window cited twice is the accident.
                window = (str(row.asset_id), float(row.t_start), float(row.t_end))
                if window in seen:
                    problems.append(f"{row.id}: this plan cites {row.t_start}s to {row.t_end}s of the same clip twice")
                seen.add(window)
                if row.assessment_id and not session.scalar(select(PlanAssessment.id).where(PlanAssessment.id == row.assessment_id, PlanAssessment.plan_id == plan.id)):
                    problems.append(f"{row.id}: its citation points at an assessment of a different plan")
        for player_id in {plan.player_id for plan in rows}:
            live = [plan.id for plan in rows if plan.player_id == player_id and str(plan.status) != "closed"]
            if len(live) > 1:
                problems.append(f"{player_id}: {len(live)} plans that are not closed in one tenant — {live}")
        consents = list(session.scalars(select(GuardianConsent).where(GuardianConsent.organization_id == organization.id)))
        for consent in consents:
            unknown = sorted(set(_scope_names(consent.scopes)) - set(SCOPES))
            if unknown:
                problems.append(f"{consent.id}: a consent naming {unknown}, which is not a purpose this tier can honour")
            if consent.state not in ("granted", "withdrawn"):
                problems.append(f"{consent.id}: consent state {consent.state!r} is not one this tier understands, so it grants nothing and blocks nothing")
            if session.get(RealPlayer, consent.player_id) is None:
                problems.append(f"{consent.id}: a consent about a player who is no longer in the world, so it gates nothing and permits nothing")
        consent_rows += len(consents)
    return {
        "clean": not problems,
        "problems": problems,
        "checked": {"organizations": len(organizations), "plans": plans, "consent_rows": consent_rows},
        "rule": "every check here is one shape of §40's sentence: a child's plan exists only while a guardian's consent says it may",
    }


def _has_plan_consent(session: Session, organization: Organization, player: RealPlayer) -> bool:
    return any("plan" in _scope_names(row.scopes) for row in consents_for(session, organization, player))


def rules() -> dict[str, Any]:
    return {
        "axes": list(AXES),
        "scopes": list(SCOPES),
        "default_scopes": list(DEFAULT_SCOPES),
        "plan_statuses": list(PLAN_STATUSES),
        "minor_age": MINOR_AGE,
        "consent": "a player under 18 needs a granted consent row naming each scope before that kind of row can be written; an adult needs none",
        "guardianship": "self-declared: the row is an account's claim about a child, and the tier can check that the child trains in this tenant and nothing beyond that",
        "scoped_rights": {
            "plan.read_own_child": "reads one child's plan, and a plan of another child in the same tenant answers as one that does not exist",
            "consent.grant_own": "only a `parent` standing may claim a child or set scopes",
            "plan.erase": "staff erase a child's rows; a guardian may erase their own child's without holding this right",
        },
        "video": "a plan cites a window of a clip M5 already holds, and never hands out a way to watch it; playback answers to the uploader",
        "stored_fields": {table: list(fields) for table, fields in STORED_FIELDS.items()},
        "never_stored": list(RESTRICTED_FIELDS),
        "max_curricula_per_organization": MAX_CURRICULA_PER_ORGANIZATION,
        "max_phases_per_curriculum": MAX_PHASES_PER_CURRICULUM,
        "max_weekly_minutes": WEEKLY_MINUTES_MAX,
        "max_plans_per_organization": MAX_PLANS_PER_ORGANIZATION,
        "max_assessments_per_plan": MAX_ASSESSMENTS_PER_PLAN,
        "max_feedback_per_plan": MAX_FEEDBACK_PER_PLAN,
        "max_evidence_per_plan": MAX_EVIDENCE_PER_PLAN,
        "max_consents_per_guardian": MAX_CONSENTS_PER_GUARDIAN,
        "review_weeks_range": [REVIEW_WEEKS_MIN, REVIEW_WEEKS_MAX],
        "rating_range": [0, 100],
        "curriculum_name_max": CURRICULUM_NAME_MAX,
        "focus_items_max": FOCUS_ITEMS_MAX,
        "goals_max": GOALS_MAX,
        "assessment_text_max": ASSESSMENT_TEXT_MAX,
        "feedback_max": FEEDBACK_MAX,
        "evidence_label_max": EVIDENCE_LABEL_MAX,
        "goal_keys": list(GOAL_KEYS),
        "refusals": list(REFUSALS),
        "refusals_shared_with_club_tier": list(SHARED_REFUSALS),
    }


def limitations() -> list[str]:
    return [
        "guardianship is claimed, not proved: this platform has no way to check that an account belongs to a child's parent, so the consent row is a self-declared claim and every gate that reads it inherits that",
        "free text is capped and shaped, never scanned: a coach who types a telephone number into a strength line has stored one in a column that is allowed to hold it, and the erase door is the remedy rather than a filter that would refuse a sentence about a left foot",
        "an academy plan points at the generated world's player row and cascades from it: regenerating the world deletes those rows, and every plan, review, note and citation of every tenant goes with them — a copy would have survived and would have disagreed with the person it described",
        "no medical, welfare or safeguarding record is stored anywhere here, and §40's list of what must stay private is the reason: this tier has no column for it, so a club with a duty of care still needs the system that has one",
        "a curriculum phase names a focus in the coach's own words and is not linked to the §65 drill catalogue, so nothing here can tell you which stored drill a phase was built from",
        "the review cadence is counted in whole days against a weekly interval; a plan due a review on a Sunday reports `due_in_days` negative from Monday, and nothing here books a room",
        "progress is the difference between two reviews of the same player by whoever wrote them; two coaches with different standards produce a delta that is about the clipboards, not the child",
    ]
