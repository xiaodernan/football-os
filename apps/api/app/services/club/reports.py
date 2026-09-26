"""§41's Reports: a saved question about a tenant, answered from whatever the reader may see.

Four rules shape the module, and all four come from the tier it sits in:

* **Nothing is stored but the question.** The row names a kind, a team and a window; every figure is re-summed at
  read time from the sessions, consents, assessments and sheets that exist then. A stored body would keep
  asserting a number the tenant had since corrected, and would assert it to readers who are not entitled to it.
* **The scope is applied per reader, not baked in.** A director's squad-load report sums the tenant's teams; the
  same report read by a guardian sums only the rows naming their own consented children. One row, two honest
  answers, because the answer is derived rather than remembered.
* **A figure with no rows says so.** An empty window prints `0` *and* the row counts it came from; it does not
  print a mean, a direction or a trend, because none of those exist over nothing.
* **One refusal code, one meaning** — and 403 stays reserved for the matrix's single `insufficient_role`.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import ClubReport, ClubSession, ClubTeam, ClubTeamMember, DevelopmentPlan, GuardianConsent, Organization, PlanAssessment, RealPlayer, User
from app.services import entitlements as ent
from app.services.club import access
from app.services.club.academy import _iso, _today
from app.services.club.organizations import ClubRefusal, require, resolve_team, standing
from app.services.club.sessions import load_units

#: The readings this tier can actually produce. Anything else is refused by name rather than answered with the
#: nearest thing that exists — a report that quietly means something else is the one kind of document a club
#: should not be handed.
KINDS: Final = ("squad_load", "consent_gap")
MAX_REPORTS_PER_ORGANIZATION: Final = 60
WINDOW_MAX_DAYS: Final = 366

NOT_FOUND_CODES: Final[frozenset[str]] = frozenset({"no_such_report"})
UNPROCESSABLE_CODES: Final[frozenset[str]] = frozenset({"unknown_kind", "window_shape", "window_reversed", "window_too_wide"})
CONFLICT_CODES: Final[frozenset[str]] = frozenset({"report_limit"})
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()
REFUSALS: Final = tuple(sorted(NOT_FOUND_CODES | UNPROCESSABLE_CODES | CONFLICT_CODES))

LIMITATION: Final = (
    "a report stores the question, not the answer: its figures are re-summed from the rows that exist at read time "
    "and scoped to what this reader may see, so a report re-read after a correction prints the correction. Only "
    f"{' and '.join(KINDS)} are implemented; any other reading is refused by name rather than approximated"
)


def report_counts(session: Session, *, ready: bool) -> dict[str, Any]:
    if not ready:
        return {"reports": 0}
    from sqlalchemy import func

    return {"reports": int(session.scalar(select(func.count()).select_from(ClubReport)) or 0)}


def _window(row: ClubReport) -> dict[str, Any]:
    days = (date.fromisoformat(row.window_to) - date.fromisoformat(row.window_from)).days + 1
    return {"window_from": row.window_from, "window_to": row.window_to, "window_days": days}


def _claims(session: Session, organization: Organization, user: User) -> set[str]:
    """The player ids this account has answered for — the same claim that scopes a guardian's plan reads."""
    rows = list(session.scalars(select(GuardianConsent).where(GuardianConsent.organization_id == organization.id, GuardianConsent.guardian_user_id == user.id, GuardianConsent.state == "granted")))
    return {str(row.player_id) for row in rows}


def _visible_players(session: Session, organization: Organization, user: User, *, staff: bool) -> set[str] | None:
    """`None` means "no filter": a staff read sees the tenant. A guardian read is cut to the children they named."""
    return None if staff else _claims(session, organization, user)


def _squad_load(session: Session, organization: Organization, row: ClubReport, *, visible: set[str] | None) -> dict[str, Any]:
    rows = list(
        session.scalars(
            select(ClubSession)
            .where(ClubSession.organization_id == organization.id, ClubSession.scheduled_on >= row.window_from, ClubSession.scheduled_on <= row.window_to)
            .order_by(ClubSession.scheduled_on, ClubSession.id)
        )
    )
    if row.team_id:
        rows = [item for item in rows if item.team_id == row.team_id]
    if visible is not None:
        rows = [item for item in rows if any(str(player) in visible for player in list(item.attendees or []))]

    minutes = sum(int(item.duration_min) for item in rows)
    loads = [load_units(int(item.duration_min), int(item.rpe)) for item in rows]
    appearances: dict[str, int] = {}
    for item in rows:
        for player in list(item.attendees or []):
            appearances[str(player)] = appearances.get(str(player), 0) + 1
    named = {slug: count for key, count in appearances.items() if (person := session.get(RealPlayer, key)) and (slug := person.slug)}
    return {
        "sessions": len(rows),
        "total_minutes": minutes,
        "total_load_units": round(sum(loads), 1),
        "mean_rpe": (round(sum(int(item.rpe) for item in rows) / len(rows), 2) if rows else None),
        "appearances": dict(sorted(named.items(), key=lambda entry: (-entry[1], entry[0]))),
        "most_worked": (max(named, key=lambda key: named[key]) if named else None),
        "empty_window": (len(rows) == 0),
        "formulas": {
            "total_minutes": "sum of `duration_min` over the session rows in this window",
            "total_load_units": "sum of " + "`duration_min × rpe ÷ 60` over the same rows",
            "mean_rpe": "sum of `rpe` divided by the rows counted; null when there are none — a mean over nothing is not zero",
            "appearances": "how many of the counted sessions each player was named present at",
        },
        "figures_from": {"club_sessions": len(rows)},
    }


def _consent_gap(session: Session, organization: Organization, row: ClubReport, *, visible: set[str] | None) -> dict[str, Any]:
    """Who is on a sheet, under the threshold, with nobody having answered for them."""
    from app.services.club.academy import MINOR_AGE

    teams = [team for team in list(session.scalars(select(ClubTeam).where(ClubTeam.organization_id == organization.id))) if (not row.team_id or team.id == row.team_id)]
    sheet_ids = {str(item.player_id) for team in teams for item in session.scalars(select(ClubTeamMember).where(ClubTeamMember.team_id == team.id))}
    granted = {str(item.player_id) for item in session.scalars(select(GuardianConsent).where(GuardianConsent.organization_id == organization.id, GuardianConsent.state == "granted"))}
    minors, waiting = 0, []
    for player_id in sorted(sheet_ids):
        person = session.get(RealPlayer, player_id)
        if person is None or int(person.age) >= MINOR_AGE:
            continue
        if visible is not None and player_id not in visible:
            continue
        minors += 1
        if player_id not in granted:
            waiting.append({"slug": person.slug, "name": person.name, "age": int(person.age)})
    return {
        "minors_on_sheets": minors,
        "without_consent": len(waiting),
        "waiting_for_an_answer": waiting,
        "teams_checked": len(teams),
        "threshold": MINOR_AGE,
        "formulas": {
            "minors_on_sheets": "rows on the checked sheets whose world age is under the published threshold",
            "without_consent": "of those, the ones no granted consent row names for the `plan` scope",
        },
        "figures_from": {"club_teams": len(teams), "club_team_members": len(sheet_ids), "guardian_consents": len(granted)},
    }


def _body(session: Session, organization: Organization, row: ClubReport, *, staff: bool, user: User) -> dict[str, Any]:
    visible = _visible_players(session, organization, user, staff=staff)
    body = _squad_load(session, organization, row, visible=visible) if row.kind == "squad_load" else _consent_gap(session, organization, row, visible=visible)
    return {**body, "scoped_to": ("the whole tenant, as far as your standing reaches" if staff else "the children your consent rows name")}


def report_view(session: Session, organization: Organization, row: ClubReport, *, staff: bool, user: User) -> dict[str, Any]:
    team = session.get(ClubTeam, row.team_id) if row.team_id else None
    return {
        "id": row.id,
        "kind": row.kind,
        "team": ({"id": team.id, "name": team.name} if team else None),
        **_window(row),
        "asked_by": ({"display_name": person.display_name} if (person := session.get(User, row.asked_by_user_id)) else None),
        "asked_on": row.created_at.isoformat() if row.created_at else None,
        "body": _body(session, organization, row, staff=staff, user=user),
        "path": f"/club/{organization.slug}/reports/{row.id}",
    }


def _span(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def create_report(session: Session, user: User, ident: str, *, kind: str, window_from: str, window_to: str, team: str | None = None) -> dict[str, Any]:
    """Ask a question of the tenant and save it. The answer is never the thing that gets stored."""
    organization, _ = require(session, user, ident, "plan.read_all")
    # §42's ceiling is checked before the row exists, and against the tenant's plan — nothing grants a plan
    # yet, so that is `free`, and the refusal prints the number it tripped over rather than a silent no.
    if kind not in KINDS:
        raise ClubRefusal("unknown_kind", f"{kind!r} is not a reading this tier can produce; it knows {list(KINDS)}", kind=kind, kinds=list(KINDS))
    start = _iso(window_from, label="a report window start")
    end = _iso(window_to, label="a report window end")
    span = _span(start, end)
    if span < 1:
        raise ClubRefusal("window_reversed", f"a report window ends {end} and starts {start}, which is {span} days — the end has to come after the start", window_from=start, window_to=end)
    if span > WINDOW_MAX_DAYS:
        raise ClubRefusal("window_too_wide", f"a report window covers at most {WINDOW_MAX_DAYS} days and {start} to {end} is {span}", days=span, max=WINDOW_MAX_DAYS)
    held = len(_rows(session, organization))
    if held >= MAX_REPORTS_PER_ORGANIZATION:
        raise ClubRefusal("report_limit", f"this tenant already saves {MAX_REPORTS_PER_ORGANIZATION} reports, which is the cap", held=held, limit=MAX_REPORTS_PER_ORGANIZATION)
    team_row = resolve_team(session, organization, team) if team else None

    existing = session.scalar(
        select(ClubReport).where(
            ClubReport.organization_id == organization.id,
            ClubReport.kind == kind,
            ClubReport.window_from == start,
            ClubReport.window_to == end,
            ClubReport.team_id == (team_row.id if team_row else None),
        )
    )
    created = existing is None
    if existing is None:
        # A new act spends the ceiling, so the meter is consulted here — after every validation of the request
        # itself, so a caller who sent an unknown kind or a reversed window is told about that rather than about
        # a plan, and after the dedupe lookup, so re-asking the same question does not spend twice. The key is
        # the report's own natural key, which is what `uq_club_report_window` enforces: meter and row agree by
        # construction rather than by two lists kept in step.
        ent.guard(session, subject_id=organization.id, feature="reports_saved", plan="free", source_id=f"{kind}:{start}:{end}:{team or 'tenant'}")
        existing = ClubReport(
            id=new_public_id("rep"), organization_id=organization.id, asked_by_user_id=user.id, kind=kind, team_id=(team_row.id if team_row else None), window_from=start, window_to=end
        )
        session.add(existing)
    else:
        # Re-asking the same question is not a new document; the row is kept and the read below recomputes.
        existing.updated_at = _now()
    session.commit()
    # The spend is recorded after the row exists: a report that failed to be written did not use anybody's
    # allowance, and an allowance charged for a write that never happened is a meter that lies the other way.
    if created:
        ent.record(session, subject_id=organization.id, subject_kind="organization", feature="reports_saved", plan="free", source_id=f"{kind}:{start}:{end}:{team or 'tenant'}")
    _, member = standing(session, user, ident)
    return {
        "report": report_view(session, organization, existing, staff=access.may(member.role, "plan.read_all"), user=user),
        "reports": len(_rows(session, organization)),
        "limit": MAX_REPORTS_PER_ORGANIZATION,
        "kinds": list(KINDS),
        "rule": "the row stores the question; the figures above are re-summed from the rows that exist now, for this reader",
        "demo_data": False,
    }


def _rows(session: Session, organization: Organization) -> list[ClubReport]:
    return list(session.scalars(select(ClubReport).where(ClubReport.organization_id == organization.id).order_by(ClubReport.created_at, ClubReport.id)))


def _one(session: Session, organization: Organization, ident: str) -> ClubReport:
    row = session.get(ClubReport, str(ident))
    if row is None or row.organization_id != organization.id:
        raise ClubRefusal("no_such_report", f"no report of this tenant answers to {str(ident)!r}", report=str(ident), organization=organization.slug)
    return row


def list_reports(session: Session, user: User, ident: str) -> dict[str, Any]:
    organization, member = standing(session, user, ident)
    staff = access.may(member.role, "plan.read_all")
    rows = _rows(session, organization)
    return {
        "organization": organization.slug,
        "items": [report_view(session, organization, row, staff=staff, user=user) for row in rows],
        "total": len(rows),
        "kinds": list(KINDS),
        "role": member.role,
        "limit": MAX_REPORTS_PER_ORGANIZATION,
        "rule": "every report here is a question this tenant saved; what each one answers is computed as you read it",
        "demo_data": False,
    }


def report_detail(session: Session, user: User, ident: str, report_ident: str) -> dict[str, Any]:
    organization, member = standing(session, user, ident)
    row = _one(session, organization, report_ident)
    staff = access.may(member.role, "plan.read_all")
    return {
        "report": report_view(session, organization, row, staff=staff, user=user),
        "role": member.role,
        "generated_on": _today().isoformat(),
        "rule": "a report is a read, not a file: it holds no figure, and these figures came from the rows this account may see",
        "demo_data": False,
    }


def delete_report(session: Session, user: User, ident: str, report_ident: str) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "plan.read_all")
    row = _one(session, organization, report_ident)
    held = len(_rows(session, organization))
    session.delete(row)
    session.commit()
    return {
        "deleted": True,
        "id": report_ident,
        "reports": held - 1,
        "rule": "deleting a report removes the question, not one row of what it was asking about",
        "demo_data": False,
    }


def _now() -> Any:
    from datetime import UTC, datetime

    return datetime.now(UTC)
