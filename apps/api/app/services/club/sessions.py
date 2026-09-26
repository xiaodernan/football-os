"""§41's Sessions: what a team actually did on a date, inside one tenant.

§40 wrote down where a child is going; this is the other half of a week of work — a group, a date, a duration,
a load, and who was there. Four things hold it to the rest of the tier:

* **The load is arithmetic, printed with its formula.** `load_units = duration_min × rpe ÷ 60` over the row's own
  columns, recomputed on every read. A stored product would disagree with a corrected duration the next morning,
  which is the mistake §40 already refused for `progress`.
* **Attendance is a selection over the sheet.** Every attendee must be on *this team's* sheet, so a session cannot
  quietly widen who a tenant trains, and cannot name a player another tenant holds.
* **A child on that sheet still needs their guardian.** Each minor among the attendees passes the same scope gate
  that opens a plan, so the §40 consent row is in front of the §41 record rather than beside it.
* **One refusal code means one thing.** `no_attendees`, `duration_range`, `rpe_range`, `slot_taken`,
  `session_limit`, `no_such_session` — and 403 still reserved for the matrix's single `insufficient_role`.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import AcademyCurriculum, ClubSession, ClubTeam, ClubTeamMember, DevelopmentPlan, GuardianConsent, Organization, RealPlayer, User
from app.services.club import access
from app.services.club.academy import _clip, _focus, _is_minor, _iso, _player_of, _require_scope, _today
from app.services.club.organizations import ClubRefusal, require, resolve_team, standing

MAX_SESSIONS_PER_ORGANIZATION: Final = 400
#: A session is a block of work, not a diary entry: the range is wide enough for a match warm-up and a pre-season
#: double, and narrow enough that a typed `9000` is refused rather than averaged into a tenant's week.
DURATION_MIN: Final = 5
DURATION_MAX: Final = 600
RPE_MIN: Final = 1
RPE_MAX: Final = 10
SLOT_MIN: Final = 1
SLOT_MAX: Final = 4
FOCUS_ITEMS_MAX: Final = 8
DRILLS_MAX: Final = 12
NOTE_MAX: Final = 280

LOAD_FORMULA: Final = "duration_min × rpe ÷ 60, over this row's own two columns — recomputed on every read, never stored"

#: Every code this part of the tier can answer with, so the rulebook prints one row per meaning. An absence is a
#: 404 and a caller-correctable figure is a 422; only the permission matrix earns a 403, as §39 reserved it.
REFUSALS: Final = (
    "no_such_session",
    "slot_taken",
    "session_limit",
    "duration_range",
    "rpe_range",
    "slot_range",
    "no_attendees",
    "attendance_limit",
    "plan_attends",
    "date_shape",
    "text_too_long",
)

NOT_FOUND_CODES: Final = frozenset({"no_such_session"})
UNPROCESSABLE_CODES: Final = frozenset({"duration_range", "rpe_range", "slot_range", "no_attendees", "attendance_limit", "plan_attends", "date_shape", "text_too_long"})
CONFLICT_CODES: Final = frozenset({"slot_taken", "session_limit"})
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()

#: The codes only this tier can be refused with: `date_shape` and `text_too_long` are §40's and are not claimed twice.
PUBLISHED: Final = tuple(code for code in REFUSALS if code not in {"date_shape", "text_too_long"})

#: The published numbers a page prints instead of guessing them.
CAPS: Final = {
    "max_sessions_per_organization": MAX_SESSIONS_PER_ORGANIZATION,
    "duration_range": [DURATION_MIN, DURATION_MAX],
    "rpe_range": [RPE_MIN, RPE_MAX],
    "slot_range": [SLOT_MIN, SLOT_MAX],
    "session_focus_max": FOCUS_ITEMS_MAX,
    "session_drills_max": DRILLS_MAX,
    "session_note_max": NOTE_MAX,
    "attendance_max": 60,
}

LIMITATION: Final = (
    "a session records work that happened: the date may not be in the future, attendance has to already be on the "
    "team's sheet, and a child present needs the same guardian's yes that opens their plan. The load figure is "
    "computed from the row's own minutes and rpe on every read — it is not a stored column"
)


def session_counts(session: Session, *, ready: bool) -> dict[str, Any]:
    """The rulebook's count of session rows — and 0 rather than a crash when this database has no such table.

    `academy_ready()` already asks that question for §40's tables, and a capabilities door that dies on a
    missing relation would take the published rulebook down with it on a half-migrated host.
    """
    if not ready:
        return {"sessions": 0}
    return {"sessions": int(session.scalar(select(func.count()).select_from(ClubSession)) or 0)}


def _sessions_of(session: Session, organization: Organization) -> list[ClubSession]:
    return list(session.scalars(select(ClubSession).where(ClubSession.organization_id == organization.id).order_by(ClubSession.scheduled_on.desc(), ClubSession.id)))


def _session(session: Session, organization: Organization, ident: str) -> ClubSession:
    """A session is found by id inside its own tenant, and nowhere else."""
    row = session.get(ClubSession, str(ident))
    if row is None or row.organization_id != organization.id:
        # The caller's own string comes back; the tenant they typed is not resolved into anything else, so an
        # id walked across organisations answers the same way a stranger's would.
        raise ClubRefusal("no_such_session", f"no session of this tenant answers to {str(ident)!r}", session=str(ident), organization=organization.slug)
    return row


def load_units(duration_min: int, rpe: int) -> float:
    return round(duration_min * rpe / 60, 1)


def session_view(session: Session, row: ClubSession) -> dict[str, Any]:
    team = session.get(ClubTeam, row.team_id)
    attendees = [session.get(RealPlayer, pid) for pid in list(row.attendees or [])]
    named = [item for item in attendees if item is not None]
    return {
        "id": row.id,
        "team": ({"id": team.id, "name": team.name, "age_group": team.age_group} if team else None),
        "scheduled_on": row.scheduled_on,
        "slot": int(row.slot),
        "duration_min": int(row.duration_min),
        "rpe": int(row.rpe),
        "load_units": load_units(int(row.duration_min), int(row.rpe)),
        "focus": list(row.focus or []),
        "drill_slugs": list(row.drill_slugs or []),
        "attendees": [{"slug": person.slug, "name": person.name, "age": int(person.age), "is_minor": int(person.age) < 18} for person in named],
        "attendees_gone": len(attendees) - len(named),
        "note": row.note,
        "planned_for": row.plan_id,
        "curriculum": row.curriculum_id,
        "coach": ({"display_name": coach.display_name, "role": coach.role} if (coach := session.get(User, row.coach_user_id)) else None),
        "recorded_on": row.created_at.isoformat() if row.created_at else None,
    }


def create_session(
    session: Session,
    user: User,
    ident: str,
    *,
    team: str,
    scheduled_on: str,
    duration_min: int,
    rpe: int,
    slot: int = 1,
    focus: Any = None,
    drill_slugs: Any = None,
    attendees: Any = None,
    plan: str | None = None,
    curriculum: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Record what the team did. Every refusal here names the figure it tripped over."""
    organization, _ = require(session, user, ident, "plan.write")
    sheet_team = resolve_team(session, organization, team)
    day = _iso(scheduled_on, label="a session date")
    if date.fromisoformat(day) > _today():
        raise ClubRefusal("date_in_future", f"a session is a record of work done, and {day} has not happened yet", scheduled_on=day, today=_today().isoformat())
    minutes = int(duration_min)
    if not DURATION_MIN <= minutes <= DURATION_MAX:
        raise ClubRefusal("duration_range", f"a session lasts between {DURATION_MIN} and {DURATION_MAX} minutes; {minutes} is outside that", duration_min=minutes, min=DURATION_MIN, max=DURATION_MAX)
    effort = int(rpe)
    if not RPE_MIN <= effort <= RPE_MAX:
        raise ClubRefusal("rpe_range", f"rpe is a scale of {RPE_MIN} to {RPE_MAX}; {effort} is not on it", rpe=effort, min=RPE_MIN, max=RPE_MAX)
    place = int(slot)
    if not SLOT_MIN <= place <= SLOT_MAX:
        raise ClubRefusal("slot_range", f"a date offers slots {SLOT_MIN} to {SLOT_MAX}; {place} is not one of them", slot=place, min=SLOT_MIN, max=SLOT_MAX)
    held = len(_sessions_of(session, organization))
    if held >= MAX_SESSIONS_PER_ORGANIZATION:
        raise ClubRefusal("session_limit", f"this tenant already records {MAX_SESSIONS_PER_ORGANIZATION} sessions, which is the cap", held=held, limit=MAX_SESSIONS_PER_ORGANIZATION)
    taken = session.scalar(
        select(func.count())
        .select_from(ClubSession)
        .where(ClubSession.organization_id == organization.id, ClubSession.team_id == sheet_team.id, ClubSession.scheduled_on == day, ClubSession.slot == place)
    )
    if taken:
        raise ClubRefusal("slot_taken", f"{sheet_team.name} already has a session on {day} in slot {place}; a second one needs the next slot", team=sheet_team.name, scheduled_on=day, slot=place)

    names = _attendee_ids(attendees)
    if not names:
        raise ClubRefusal("no_attendees", "a session needs at least one player on the sheet; attendance left empty is not a session", attendees=0)
    on_sheet = _sheet_size(session, sheet_team)
    # The row stores the id each address *resolved to*, not the string the caller typed: the read path looks an
    # attendee up by primary key to print their slug, age and `is_minor`, so a session recorded from a page — which
    # addresses players by slug, the same way every other door here is addressed — would otherwise come back with
    # empty attendance, and a guardian reading their own child's log would be told their child was at nothing.
    # Two spellings of one player are one attendee.
    present: list[str] = []
    minors = 0
    for player_id in names:
        person = _player_of(session, organization, player_id, on_sheet=False)
        _require_scope(session, organization, person, "plan")
        if person.id in present:
            continue
        present.append(person.id)
        if _is_minor(int(person.age)):
            minors += 1
    # The ceiling is counted over the players the list names, not over the strings that named them: a sheet of one
    # child and an attendance of `slug, id` for that same child is one attendee, and refusing it would print a
    # figure — "the session names 2" — that is false about the session in front of it.
    if len(present) > on_sheet:
        raise ClubRefusal(
            "not_on_sheet",
            f"this team's sheet holds {on_sheet} player(s) and the session names {len(present)}",
            team=sheet_team.name,
            named=len(present),
            on_sheet=on_sheet,
        )

    items = _focus_list(focus)
    drills = _string_list(drill_slugs, cap=DRILLS_MAX, label="drill slugs")
    text = _clip(note, NOTE_MAX, label="a session note")
    plan_row = _optional_plan(session, organization, plan)
    if plan_row is not None and plan_row.player_id not in present:
        raise ClubRefusal("plan_attends", "the plan this session is filed under belongs to a child who is not on the attendance list", plan=plan_row.id)
    curriculum_id = _optional_curriculum(session, organization, curriculum)

    row = ClubSession(
        id=new_public_id("ses"),
        organization_id=organization.id,
        team_id=sheet_team.id,
        plan_id=(plan_row.id if plan_row else None),
        curriculum_id=curriculum_id,
        coach_user_id=user.id,
        scheduled_on=day,
        slot=place,
        duration_min=minutes,
        rpe=effort,
        focus=items,
        drill_slugs=drills,
        attendees=present,
        note=text,
    )
    session.add(row)
    session.commit()
    return {
        "session": session_view(session, row),
        "sessions": held + 1,
        "minors_present": minors,
        "limit": MAX_SESSIONS_PER_ORGANIZATION,
        "load_units": load_units(minutes, effort),
        "formulas": {"load_units": LOAD_FORMULA},
        "rule": "a session records what happened: the date may not be in the future, attendance is the sheet's own, and each child present needs the guardian's yes that opens a plan",
        "demo_data": False,
    }


def list_sessions(session: Session, user: User, ident: str, *, team: str | None = None, since: str | None = None) -> dict[str, Any]:
    """The tenant's log, newest first, with the week's load summed from the rows it names."""
    organization, member = standing(session, user, ident)
    staff = access.may(member.role, "plan.read_all")
    if not staff and not access.may(member.role, "plan.read_own_child"):
        require(session, user, ident, "plan.read_all")
    rows = _sessions_of(session, organization)
    claims = {row.player_id for row in _consent_claims(session, organization, user)}
    if not staff:
        # A guardian reads the sessions their own child was at, and nothing else — the same scoping rule that
        # decides which plans they see, applied to a different table.
        rows = [row for row in rows if str(user.id) != "" and any(pid in claims for pid in list(row.attendees or []))]
    if team:
        wanted = resolve_team(session, organization, team)
        rows = [row for row in rows if row.team_id == wanted.id]
    if since:
        start = _iso(since, label="a since date")
        rows = [row for row in rows if row.scheduled_on >= start]

    total_load = round(sum(load_units(int(row.duration_min), int(row.rpe)) for row in rows), 1)
    minutes = sum(int(row.duration_min) for row in rows)
    # Counted under the slug a reader can follow, not the internal id the row stores: `most_attended` is printed
    # as a figure about a person, and a person on this platform is addressed by slug.
    by_player: dict[str, int] = {}
    for row in rows:
        for player_id in list(row.attendees or []):
            person = session.get(RealPlayer, str(player_id))
            key = person.slug if person is not None else str(player_id)
            by_player[key] = by_player.get(key, 0) + 1
    return {
        "organization": organization.slug,
        "items": [session_view(session, row) for row in rows],
        "total": len(rows),
        "total_minutes": minutes,
        "total_load_units": total_load,
        "mean_rpe": (round(sum(int(row.rpe) for row in rows) / len(rows), 2) if rows else None),
        "most_attended": max(by_player, key=lambda key: by_player[key]) if by_player else None,
        "attendance_counts": by_player,
        "role": member.role,
        "read_through": ("plan.read_all" if staff else "plan.read_own_child"),
        # The day the write rule will judge against, printed by the read rule's own door. A page that pre-fills a
        # date from its host clock can be a day ahead of this one — opened before midnight, used after — and a
        # form default is worth nothing if the door refuses it for a reason it could have said in advance.
        "today": _today().isoformat(),
        "formulas": {
            "total_load_units": LOAD_FORMULA + ", summed over the rows in this list",
            "total_minutes": "sum of `duration_min` over the rows in this list",
            "mean_rpe": "sum of `rpe` divided by the number of rows shown; null when there are none",
        },
        "rule": "a listing and a read agree: every session here is one this caller may open, and none of these figures is stored — they are summed from the rows on screen",
        "today_rule": "`today` is the date a `scheduled_on` is compared against: a later one is refused with date_in_future, so a form should open on this value rather than on the reader's own clock",
        "demo_data": False,
    }


def session_detail(session: Session, user: User, ident: str, session_ident: str) -> dict[str, Any]:
    organization, member = standing(session, user, ident)
    row = _session(session, organization, session_ident)
    staff = access.may(member.role, "plan.read_all")
    claims = {item.player_id for item in _consent_claims(session, organization, user)}
    if not staff and not any(pid in claims for pid in list(row.attendees or [])):
        # A guardian who was not at this session is answered as if it did not exist: the row belongs to the tenant,
        # and confirming which of its dates are real is not their question to ask.
        raise ClubRefusal("no_such_session", f"no session of this tenant answers to {str(session_ident)!r}", session=str(session_ident), organization=organization.slug)
    return {"session": session_view(session, row), "role": member.role, "formulas": {"load_units": LOAD_FORMULA}, "demo_data": False}


def delete_session(session: Session, user: User, ident: str, session_ident: str) -> dict[str, Any]:
    """Erase one session row. The clip, plan and sheet it named all survive it."""
    organization, _ = require(session, user, ident, "plan.write")
    row = _session(session, organization, session_ident)
    held = len(_sessions_of(session, organization))
    session.delete(row)
    session.commit()
    return {
        "deleted": True,
        "id": session_ident,
        "sessions": held - 1,
        "rule": "a session deleted is a record the tenant no longer holds; the players it named stay on their sheets and a clip it cited stays with whoever uploaded it",
        "demo_data": False,
    }


def _attendee_ids(value: Any) -> list[str]:
    items = list(value or [])
    if len(items) > 60:
        raise ClubRefusal("attendance_limit", f"attendance names {len(items)} players and a session lists at most 60", named=len(items), max=60)
    seen: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.append(text)
    return seen


def _string_list(value: Any, *, cap: int, label: str) -> list[str]:
    items = [str(item).strip() for item in list(value or []) if str(item).strip()]
    if len(items) > cap:
        raise ClubRefusal("text_too_long", f"{label} allows {cap} entries and {len(items)} were sent", field=label, length=len(items), max=cap)
    return items


def _focus_list(value: Any) -> list[str]:
    return _focus(value)[:FOCUS_ITEMS_MAX]


def _sheet_size(session: Session, team: Any) -> int:
    return int(session.scalar(select(func.count()).select_from(ClubTeamMember).where(ClubTeamMember.team_id == team.id)) or 0)


def _optional_plan(session: Session, organization: Organization, ident: Any) -> DevelopmentPlan | None:
    text = str(ident or "").strip()
    if not text:
        return None
    row = session.get(DevelopmentPlan, text)
    if row is None or row.organization_id != organization.id:
        raise ClubRefusal("no_such_plan", f"no plan of this tenant answers to {text!r}", plan=text, organization=organization.slug)
    return row


def _optional_curriculum(session: Session, organization: Organization, ident: Any) -> str | None:
    text = str(ident or "").strip()
    if not text:
        return None
    row = session.get(AcademyCurriculum, text)
    if row is None or row.organization_id != organization.id:
        raise ClubRefusal("no_such_curriculum", f"no curriculum of this tenant answers to {text!r}", curriculum=text, organization=organization.slug)
    return row.id


def _consent_claims(session: Session, organization: Organization, user: User) -> list[GuardianConsent]:
    return list(session.scalars(select(GuardianConsent).where(GuardianConsent.organization_id == organization.id, GuardianConsent.guardian_user_id == user.id, GuardianConsent.state == "granted")))


__all__ = [
    "DURATION_MAX",
    "DURATION_MIN",
    "MAX_SESSIONS_PER_ORGANIZATION",
    "NOTE_MAX",
    "RPE_MAX",
    "RPE_MIN",
    "SLOT_MAX",
    "SLOT_MIN",
    "create_session",
    "delete_session",
    "list_sessions",
    "load_units",
    "session_detail",
    "session_view",
]
