"""§39's Communication row: a notice one member posts to an audience, and the record of who has read it.

This is the fourth thing stored on a tenant, and the first whose *readership* is derived rather than written. A
person sees a notice because of the role their membership row holds, not because a row names them — so there is no
`recipient` column here at all, and three consequences follow from that one decision:

* **The denominator is the roster as it stands.** `recipients` counts the *active* memberships the audience selects,
  recomputed on every read. A member revoked yesterday leaves it immediately, and their old receipt leaves `read_by`
  with it. A stored count would keep insisting that a person who no longer stands in the tenant never read a notice
  they were never going to see again.
* **A receipt is a fact about one account.** `club_announcement_reads` holds `(announcement, user)` and nothing
  else, so marking a notice read twice is one row — the database says so, not just the code path.
* **A notice addresses an audience and can never address a child.** §40's data-minimisation rule is structural
  here rather than a validation on a field: the door has no parameter that could name a person. `parent` holds
  `announce.read` for that reason — a guardian receives what an audience selects, which is the whole reason the row
  exists in a youth academy's product.

The ceiling is one constant, `MAX_ANNOUNCEMENTS_PER_ORGANIZATION`, which `CAPS` publishes, the guard below applies
and the refusal prints with its own figures. That is §49's lesson applied before it could recur here: a figure
written three times is a figure that can disagree with itself.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import ClubAnnouncement, ClubAnnouncementRead, Organization, OrganizationMember, User
from app.services.club.academy import _today
from app.services.club.organizations import ClubRefusal, require

#: One notice per act, and an audience is a predicate over memberships, not a distribution list.
AUDIENCES: Final = ("members", "staff", "parents")
MAX_ANNOUNCEMENTS_PER_ORGANIZATION: Final = 200
PINNED_MAX: Final = 3
TITLE_MAX: Final = 120
BODY_MAX: Final = 2000

#: What the derived figures on this tier's answers are made of, printed beside the figures themselves.
FORMULAS: Final = {
    "recipients": "count of this tenant's `active` membership rows whose role the audience selects — recomputed on every read, so a revoked member leaves the denominator at once",
    "read_by": "count of this notice's receipt rows whose account is still one of `recipients`",
    "unread": "`recipients` minus `read_by`, over those two figures on this page",
    "announcement_total": "count of this tenant's notice rows, before any audience filter",
}

#: Every code this part of the tier can answer with. An absence is a 404, a caller-correctable figure a 422, a
#: ceiling already reached a 409 — and 403 stays the permission matrix's single meaning, so this tier registers
#: no forbidden code of its own: a member without the right is answered by `organizations.require`, here as
#: everywhere else in the club OS.
REFUSALS: Final = (
    "no_such_announcement",
    "announcement_audience",
    "announcement_title",
    "announcement_body",
    "announcement_limit",
    "pinned_limit",
    "not_an_audience",
)

NOT_FOUND_CODES: Final = frozenset({"no_such_announcement"})
UNPROCESSABLE_CODES: Final = frozenset({"announcement_audience", "announcement_title", "announcement_body", "not_an_audience"})
CONFLICT_CODES: Final = frozenset({"announcement_limit", "pinned_limit"})
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()

#: The codes this tier's own doors are the first to print — which here is all of them.
PUBLISHED: Final = REFUSALS

CAPS: Final = {
    "announcement_max": MAX_ANNOUNCEMENTS_PER_ORGANIZATION,
    "pinned_max": PINNED_MAX,
    "title_max": TITLE_MAX,
    "body_max": BODY_MAX,
    "audiences": list(AUDIENCES),
    "audience_rule": "an audience is one predicate over the tenant's active memberships: `members` is all of them, `staff` is every role that is not `parent`, `parents` is the `parent` rows alone",
}

LIMITATION: Final = (
    "a notice is posted to an audience and never to a named child: the door takes a role predicate and no person, "
    "so §40's minimisation rule is the shape of this tier rather than a check inside it. Read receipts count the "
    "roster as it stands, which means a revoked member's receipt stops being printed rather than being deleted — "
    "the row stays, and grants nothing to anybody"
)


def announcement_counts(session: Session, *, ready: bool) -> dict[str, Any]:
    """The rulebook's count of notice rows — 0 rather than a crash when this database has no such table."""
    if not ready:
        return {"announcements": 0, "announcement_reads": 0}
    return {
        "announcements": int(session.scalar(select(func.count()).select_from(ClubAnnouncement)) or 0),
        "announcement_reads": int(session.scalar(select(func.count()).select_from(ClubAnnouncementRead)) or 0),
    }


def announcements_ready(session: Session) -> bool:
    """Whether this database holds the two tables this tier writes."""
    from sqlalchemy import inspect

    existing = set(inspect(session.get_bind()).get_table_names())
    return {"club_announcements", "club_announcement_reads"} <= existing


def _audience_condition(audience: str) -> Any:
    """The one predicate an audience means. Written once so a listing's rows and its denominator cannot drift."""
    if audience == "members":
        return None
    if audience == "staff":
        return OrganizationMember.role != "parent"
    return OrganizationMember.role == "parent"


def _active_memberships(session: Session, organization: Organization, audience: str) -> list[OrganizationMember]:
    statement = select(OrganizationMember).where(OrganizationMember.organization_id == organization.id, OrganizationMember.status == "active")
    condition = _audience_condition(audience)
    if condition is not None:
        statement = statement.where(condition)
    return list(session.scalars(statement.order_by(OrganizationMember.role, OrganizationMember.user_id)))


def _audience(audience: Any) -> str:
    text = str(audience or "").strip().lower()
    if text not in AUDIENCES:
        raise ClubRefusal(
            "announcement_audience",
            f"a notice is posted to {' or '.join(repr(item) for item in AUDIENCES)}; {text!r} is none of them, and an unknown audience would select nobody",
            sent=text,
            audiences=list(AUDIENCES),
        )
    return text


def _announcements_of(session: Session, organization: Organization) -> list[ClubAnnouncement]:
    return list(session.scalars(select(ClubAnnouncement).where(ClubAnnouncement.organization_id == organization.id).order_by(ClubAnnouncement.published_on.desc(), ClubAnnouncement.id)))


def _announcement(session: Session, organization: Organization, ident: str) -> ClubAnnouncement:
    """A notice is found by id inside its own tenant, and nowhere else."""
    row = session.get(ClubAnnouncement, str(ident))
    if row is None or row.organization_id != organization.id:
        raise ClubRefusal("no_such_announcement", f"no notice of this tenant answers to {str(ident)!r}", announcement=str(ident), organization=organization.slug)
    return row


def _receipts(session: Session, row: ClubAnnouncement) -> set[str]:
    return {str(user_id) for user_id in session.scalars(select(ClubAnnouncementRead.user_id).where(ClubAnnouncementRead.announcement_id == row.id))}


def _addressed(session: Session, organization: Organization, row: ClubAnnouncement, user: User) -> bool:
    """Whether the audience of this notice selects this account's standing in the tenant, right now."""
    return any(member.user_id == user.id for member in _active_memberships(session, organization, row.audience))


def readership(session: Session, organization: Organization, row: ClubAnnouncement) -> dict[str, Any]:
    """The three derived figures of one notice, and the arithmetic that produced them."""
    recipients = _active_memberships(session, organization, row.audience)
    held = _receipts(session, row)
    read_by = len([member for member in recipients if str(member.user_id) in held])
    return {
        "recipients": len(recipients),
        "read_by": read_by,
        "unread": len(recipients) - read_by,
        "receipts_on_row": len(held),
        "formulas": dict(FORMULAS),
    }


def announcement_view(session: Session, organization: Organization, row: ClubAnnouncement, *, for_user: User | None = None) -> dict[str, Any]:
    author = session.get(User, row.author_id) if row.author_id else None
    return {
        "id": row.id,
        "title": row.title,
        "body": row.body,
        "audience": row.audience,
        "pinned": bool(row.pinned),
        "published_on": row.published_on,
        # The role the author held when they posted it, kept on the row: a later role change must not rewrite
        # who wrote a notice that is still on the board.
        # A notice names the person who wrote it by display name only. An account has no slug in this
        # schema, and an email on a board every member reads would be a contact list, not a notice.
        "author": ({"name": author.display_name} if author else None),
        "author_role": row.author_role,
        "read": (bool(_addressed(session, organization, row, for_user)) and str(for_user.id) in _receipts(session, row)) if for_user is not None else None,
        **readership(session, organization, row),
    }


def create_announcement(session: Session, user: User, ident: str, *, title: str, body: str = "", audience: str = "members", pinned: bool = False) -> dict[str, Any]:
    """Post one notice to an audience. Nothing here names a person, and that is the rule rather than the default."""
    organization, member = require(session, user, ident, "announce.write")
    text = str(title or "").strip()
    if not text:
        raise ClubRefusal("announcement_title", "a notice needs a title, because a board of blank rows tells a member nothing", sent=str(title), max=TITLE_MAX)
    if len(text) > TITLE_MAX:
        raise ClubRefusal("announcement_title", f"a notice title is at most {TITLE_MAX} characters and this one is {len(text)}", length=len(text), max=TITLE_MAX)
    words = str(body or "").strip()
    if len(words) > BODY_MAX:
        raise ClubRefusal("announcement_body", f"a notice body is at most {BODY_MAX} characters and this one is {len(words)}", length=len(words), max=BODY_MAX)
    chosen = _audience(audience)
    held = len(_announcements_of(session, organization))
    if held >= MAX_ANNOUNCEMENTS_PER_ORGANIZATION:
        raise ClubRefusal(
            "announcement_limit",
            f"this tenant already posts {MAX_ANNOUNCEMENTS_PER_ORGANIZATION} notices, which is the cap",
            held=held,
            limit=MAX_ANNOUNCEMENTS_PER_ORGANIZATION,
        )
    if pinned:
        # The guard asks what the *audience* would see: three pinned notices to `staff` and three to `parents` are
        # six rows and two boards, so a tenant-wide count would refuse the second one for no reason.
        standing = sum(1 for row in _announcements_of(session, organization) if bool(row.pinned) and row.audience == chosen)
        if standing >= PINNED_MAX:
            raise ClubRefusal("pinned_limit", f"at most {PINNED_MAX} notices are pinned to an audience and {chosen!r} already has {standing}", pinned=standing, max=PINNED_MAX, audience=chosen)
    row = ClubAnnouncement(
        id=new_public_id("ann"),
        organization_id=organization.id,
        audience=chosen,
        title=text,
        body=words,
        author_id=user.id,
        author_role=member.role,
        pinned=bool(pinned),
        published_on=_today().isoformat(),
    )
    session.add(row)
    session.commit()
    return {
        "announcement": announcement_view(session, organization, row, for_user=user),
        "announcements": held + 1,
        "limit": MAX_ANNOUNCEMENTS_PER_ORGANIZATION,
        "role": member.role,
        "rule": "a notice stores its own words, the audience it was posted to and the role its author held then; who has read it is a receipt, and what the audience selects is arithmetic",
        "demo_data": False,
    }


def list_announcements(session: Session, user: User, ident: str, *, audience: str | None = None) -> dict[str, Any]:
    """The tenant's board, newest first, with each notice's readership counted from the rows on this page."""
    organization, member = require(session, user, ident, "announce.read")
    rows = _announcements_of(session, organization)
    if audience:
        chosen = _audience(audience)
        rows = [row for row in rows if row.audience == chosen]
    pinned = {name: int(session.scalar(select(func.count()).select_from(ClubAnnouncement).where(ClubAnnouncement.audience == name, ClubAnnouncement.pinned.is_(True))) or 0) for name in AUDIENCES}
    return {
        "organization": organization.slug,
        "items": [announcement_view(session, organization, row, for_user=user) for row in rows],
        "total": len(rows),
        "pinned_by_audience": pinned,
        "announcements_held": len(_announcements_of(session, organization)),
        "limit": MAX_ANNOUNCEMENTS_PER_ORGANIZATION,
        "role": member.role,
        "read_through": "announce.read",
        "sees": [row.id for row in rows if _addressed(session, organization, row, user)],
        "today": _today().isoformat(),
        "caps": dict(CAPS),
        "formulas": dict(FORMULAS),
        "rule": "every figure on this page is counted from the rows it names, and `sees` is which of them the caller's own standing selects — a notice a member cannot see is listed with its readership and marked unread by nobody",
        "demo_data": False,
    }


def announcement_detail(session: Session, user: User, ident: str, announcement_ident: str) -> dict[str, Any]:
    """One notice, with the caller's own receipt beside the readership it belongs to."""
    organization, member = require(session, user, ident, "announce.read")
    row = _announcement(session, organization, announcement_ident)
    return {
        "announcement": announcement_view(session, organization, row, for_user=user),
        "role": member.role,
        "addressed_to_caller": _addressed(session, organization, row, user),
        "caps": dict(CAPS),
        "formulas": dict(FORMULAS),
        "demo_data": False,
    }


def mark_announcement_read(session: Session, user: User, ident: str, announcement_ident: str) -> dict[str, Any]:
    """Write the caller's own receipt. Reading a notice twice is one row, and the answer says which one it was."""
    organization, _ = require(session, user, ident, "announce.read")
    row = _announcement(session, organization, announcement_ident)
    if not _addressed(session, organization, row, user):
        raise ClubRefusal(
            "not_an_audience",
            f"this notice is posted to {row.audience!r} and your standing in this tenant is not selected by it, so there is no receipt to record",
            audience=row.audience,
            announcement=row.id,
        )
    day = _today().isoformat()
    existing = session.scalar(select(ClubAnnouncementRead).where(ClubAnnouncementRead.announcement_id == row.id, ClubAnnouncementRead.user_id == user.id))
    if existing is not None:
        return {
            "announcement": announcement_view(session, organization, row, for_user=user),
            "receipt": "already recorded",
            "read_on": existing.read_on,
            "recorded_now": False,
            "rule": "a receipt is one row per account and notice, so marking it again changes nothing — the figure that moved is the one that moved the first time",
            "demo_data": False,
        }
    session.add(ClubAnnouncementRead(id=new_public_id("anr"), organization_id=organization.id, announcement_id=row.id, user_id=user.id, read_on=day))
    session.commit()
    return {
        "announcement": announcement_view(session, organization, row, for_user=user),
        "receipt": "recorded",
        "read_on": day,
        "recorded_now": True,
        "rule": "a receipt says this account read this notice; it is not a reply, and nothing in this tier lets a notice be answered",
        "demo_data": False,
    }


def delete_announcement(session: Session, user: User, ident: str, announcement_ident: str) -> dict[str, Any]:
    """Erase a notice and the receipts on it. The roster it was counted against is untouched."""
    organization, _ = require(session, user, ident, "announce.erase")
    row = _announcement(session, organization, announcement_ident)
    receipts = int(session.scalar(select(func.count()).select_from(ClubAnnouncementRead).where(ClubAnnouncementRead.announcement_id == row.id)) or 0)
    remaining = len(_announcements_of(session, organization)) - 1
    session.delete(row)
    session.commit()
    return {
        "erased": row.id,
        "title": row.title,
        "receipts_removed": receipts,
        "announcements": remaining,
        "limit": MAX_ANNOUNCEMENTS_PER_ORGANIZATION,
        "rule": "the notice and its receipts go together; the memberships they were counted over stay, and every other tenant's board is unchanged",
        "demo_data": False,
    }
