"""§39's Club OS and §41's B2B spine: open a tenant, staff it, name its teams, fill a team sheet.

The one rule everything here serves is stated in `access.py`: *a member of one organisation can read and change
nothing in another*. In this module that rule is enforced in exactly one place — `require()` — and every route
below calls it before it reads a row. Two consequences are deliberate and are what the tests around this file are
built to hold:

* **A foreign tenant answers as one that does not exist.** Every failure to reach an organisation is
  `no_such_organization`, never `not_a_member`. An endpoint that returned 403 for someone else's slug would
  confirm which slugs are taken, and a page listing academies is not what this tier is for.
* **403 exists, but only for a member asking for more than their role grants.** By then the tenant is already
  theirs, so naming the permission and the role that holds it leaks nothing and answers the useful question.

`users.organization_id` — a column that predates this service — is written once, at the first membership, and
never again. It stays a convenience for anything that was reading it before tenants existed; membership rows are
the truth, and `access_problems()` reports any divergence instead of quietly trusting either side.
"""

from __future__ import annotations

from typing import Any, Final

from sqlalchemy import func, inspect, select, update
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import ClubTeam, ClubTeamMember, Organization, OrganizationMember, RealPlayer, User
from app.models import Team as WorldTeam
from app.services import entitlements as ent
from app.services.club import access
from app.services.world.names import slugify

MAX_ORGANIZATIONS_PER_USER: Final = 5
MAX_MEMBERS_PER_ORGANIZATION: Final = 40
MAX_TEAMS_PER_ORGANIZATION: Final = 12
MAX_SQUAD_PER_TEAM: Final = 40
NAME_MAX: Final = 160
TEAM_NAME_MAX: Final = 120
NOTE_MAX: Final = 240

KINDS: Final = ("academy", "club", "school", "scout_desk")
VISIBILITY_DEFAULTS: Final = ("members", "staff", "private")

REFUSALS: Final = (
    "no_such_organization",
    "no_such_team",
    "no_such_member",
    "no_such_player",
    "no_such_world_club",
    "no_such_user",
    "insufficient_role",
    "unknown_role",
    "unknown_kind",
    "unknown_visibility",
    "unknown_country",
    "name_required",
    "organization_limit",
    "already_a_member",
    "member_limit",
    "last_owner",
    "team_name_taken",
    "team_limit",
    "already_on_team",
    "squad_full",
)

#: Which answer each refusal deserves. Anything that reports an organisation's absence is a 404 on purpose.
NOT_FOUND_CODES: Final = frozenset({"no_such_organization", "no_such_team", "no_such_member", "no_such_player", "no_such_world_club", "no_such_user"})
UNPROCESSABLE_CODES: Final = frozenset({"unknown_role", "unknown_kind", "unknown_visibility", "unknown_country", "name_required", "organization_limit", "member_limit", "team_limit", "squad_full"})
#: A member asking for more than their role grants is the only 403 in this tier: by then the tenant is
#: already theirs, so naming the permission leaks nothing. Everything about an unknown tenant stays a 404.
FORBIDDEN_CODES: Final = frozenset({"insufficient_role"})
CONFLICT_CODES: Final = frozenset({"already_a_member", "last_owner", "team_name_taken", "already_on_team"})


class ClubRefusal(RuntimeError):
    """A refusal with the figures beside the sentence, as every other tier in this project does."""

    def __init__(self, code: str, message: str, **figures: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.figures = figures

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.figures}


def _organization(session: Session, ident: str) -> Organization:
    row = session.scalar(select(Organization).where(Organization.slug == str(ident))) or session.scalar(select(Organization).where(Organization.id == str(ident)))
    if row is None:
        raise ClubRefusal("no_such_organization", f"no organisation answers to {str(ident)!r}", ident=str(ident))
    return row


def membership_of(session: Session, organization: Organization, user: User) -> OrganizationMember | None:
    return session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == organization.id, OrganizationMember.user_id == user.id))


def _country(value: str) -> str:
    """Two letters, or a refusal that prints what it was given.

    Truncating was the obvious-looking implementation and it is a quiet liar: `POL` would have stored `PO`,
    which is nobody's country code, and the page would have shown a wrong flag rather than an error. A blank
    stays legal because a tenant with no country named is a real state of this world.
    """
    label = str(value).strip()
    if len(label) not in (0, 2):
        raise ClubRefusal("unknown_country", f"a country is two letters, or nothing at all; {value!r} is {len(label)} characters", country=str(value), length=len(label))
    if len(label) == 2 and not (label.isalpha() and label.isascii()):
        raise ClubRefusal("unknown_country", f"{value!r} is two characters but not two letters, so it cannot name a country", country=str(value))
    return label.upper()


def require(session: Session, user: User, ident: str, permission: str) -> tuple[Organization, OrganizationMember]:
    """The single door every write and every private read passes through.

    Order matters: an unknown or foreign tenant is the same 404 before the caller learns whether the permission
    exists, so the answer never depends on whether the slug is real.
    """
    organization = _organization(session, ident)
    membership = membership_of(session, organization, user)
    # An `invited` or `revoked` row is not a foothold: it grants nothing (access.matrix()'s default), so the
    # tenant it names is answered exactly as one this account has never stood in. The status is not reported,
    # because "you were invited and have not accepted" and "you were never invited" must look identical to
    # somebody probing which academies exist — and only an *active* member can be told they over-reached.
    if membership is None or membership.status != "active":
        raise ClubRefusal(
            "no_such_organization",
            f"no organisation of yours answers to {str(ident)!r} — another account's tenant is answered exactly as one that was never opened",
            ident=str(ident),
            permission=permission,
        )
    if not access.may(membership.role, permission):
        grant = access.grant(membership.role, membership.status)
        raise ClubRefusal(
            "insufficient_role",
            f"the role {membership.role!r} ({membership.status}) on this organisation does not hold {permission!r}",
            organization=organization.slug,
            permission=permission,
            role=membership.role,
            status=membership.status,
            permissions_held=grant["permissions"],
            # The branch is entered *because* the role does not hold the permission, so a `holds_this` figure
            # here could only ever have been false. What a page cannot read off that is which of the two ways
            # it grants nothing this is: a role below the right tier, or a role string that is not in the matrix.
            known_role=grant["known_role"],
            why=grant["why"],
        )
    return organization, membership


def standing(session: Session, user: User, ident: str) -> tuple[Organization, OrganizationMember]:
    """Resolve a tenant and prove this account stands in it, without asking which right it holds.

    §40's reads need this instead of `require()`: a parent listing their own child's plans is entitled to the
    answer and holds none of the staff permissions, so a permission-based door would refuse them for the right
    they do not need. The scoping happens in the academy service, against the consent row — which is why this
    returns the membership rather than hiding it. A foreign or unknown tenant answers with the same 404
    `require()` gives, and a revoked or unaccepted standing is not a foothold here either.
    """
    organization = _organization(session, ident)
    person = membership_of(session, organization, user)
    if person is None or person.status != "active":
        raise ClubRefusal("no_such_organization", f"no organisation of yours answers to {str(ident)!r}", ident=str(ident), rule="a standing that grants nothing is answered as a stranger's")
    return organization, person


def resolve_team(session: Session, organization: Organization, ident: str) -> ClubTeam:
    """A tenant's own team, by id or by name — the §40 doors take a sheet a plan is written against."""
    return _team(session, organization, ident)


def _member_row(session: Session, member: OrganizationMember) -> dict[str, Any]:
    person = session.get(User, member.user_id)
    return {
        "id": member.id,
        "role": member.role,
        "status": member.status,
        "email": person.email if person else None,
        "display_name": person.display_name if person else None,
        # The account's own role in the platform (`player`, `coach`, — is a different axis from the role it
        # holds inside this tenant, and printing both without the second label is how a reader conflates them.
        "account_role": person.role if person else None,
        "since": member.created_at.isoformat() if member.created_at else None,
        "invited_by": member.invited_by,
        **access.grant(member.role, member.status),
    }


def _count_members(session: Session, organization_id: str, status: str = "active") -> int:
    return int(session.scalar(select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == organization_id, OrganizationMember.status == status)) or 0)


def _owners(session: Session, organization_id: str) -> list[OrganizationMember]:
    return list(
        session.scalars(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.role == "owner",
                OrganizationMember.status == "active",
            )
        )
    )


def _teams_of(session: Session, organization_id: str) -> list[ClubTeam]:
    return list(session.scalars(select(ClubTeam).where(ClubTeam.organization_id == organization_id).order_by(ClubTeam.name)))


def team_view(session: Session, team: ClubTeam) -> dict[str, Any]:
    squad = list(session.scalars(select(ClubTeamMember).where(ClubTeamMember.team_id == team.id).order_by(ClubTeamMember.created_at, ClubTeamMember.id)))
    rows = []
    for item in squad:
        player = session.get(RealPlayer, item.player_id)
        if player is None:  # pragma: no cover - the foreign key cascades, so this is a guard, not a path
            continue
        rows.append(
            {
                "player_id": player.id,
                "slug": player.slug,
                "name": player.name,
                "path": f"/player/{player.slug}",
                "age": int(player.age),
                "is_minor": int(player.age) < 18,
                "position": player.position,
                "overall": int(player.overall),
                "potential": int(player.potential),
                "note": item.note,
                "added_at": item.created_at.isoformat() if item.created_at else None,
            }
        )
    world = session.get(WorldTeam, team.world_team_id) if team.world_team_id else None
    return {
        "id": team.id,
        "name": team.name,
        "age_group": team.age_group,
        "stage": team.stage,
        "world_team": ({"id": world.id, "slug": world.slug, "name": world.name, "path": f"/team/{world.slug}"} if world else None),
        "squad": rows,
        "squad_size": len(rows),
        "minors_on_sheet": sum(1 for row in rows if row["is_minor"]),
        "room_left": max(0, MAX_SQUAD_PER_TEAM - len(rows)),
        "figures_from": "`real_players` read on this request, so a team sheet cannot hold a stale rating any more than a shortlist can",
    }


def organization_view(session: Session, organization: Organization, user: User, *, ident: str) -> dict[str, Any]:
    """The tenant as one account sees it — and an invitation or a revoked row sees nothing at all.

    The read is gated on *standing*, not on permission, because there is no `org.read` in the matrix: every
    active member may read the tenant they stand in (a coach who could not read their own club's staff list
    would be unable to work), while a row that grants nothing must not be a way past the isolation rule. So
    `invited` and `revoked` answer as the absence of a membership rather than as a 403 — which is also the
    only answer that does not confirm to a stranger that their invitation, or their revocation, landed.

    `ident` is what the caller typed, and the refusal prints that and nothing resolved from the row. A tenant
    is reachable by id as well as by slug, so echoing the slug to somebody who addressed it by id would hand
    a stranger the readable name of a tenant they had only found a number for — the same confirmation the 404
    exists to withhold. Every caller here has an ident to pass: a route's, or its own row's.
    """
    membership = membership_of(session, organization, user)
    if membership is None or membership.status != "active":
        raise ClubRefusal("no_such_organization", f"no organisation of yours answers to {str(ident)!r}", ident=str(ident))
    teams = _teams_of(session, organization.id)
    members = list(session.scalars(select(OrganizationMember).where(OrganizationMember.organization_id == organization.id).order_by(OrganizationMember.role, OrganizationMember.created_at)))
    return {
        "organization": {
            "id": organization.id,
            "slug": organization.slug,
            "name": organization.name,
            "kind": organization.kind,
            "country": organization.country,
            "visibility_default": organization.visibility_default,
            "data_origin": organization.data_origin,
            "is_demo_data": bool(organization.is_demo_data),
            "created_at": organization.created_at.isoformat() if organization.created_at else None,
        },
        "my_grant": access.grant(membership.role, membership.status),
        "members": [_member_row(session, member) for member in members],
        "counts": {
            "active_members": _count_members(session, organization.id, "active"),
            "invited_members": _count_members(session, organization.id, "invited"),
            "owners": len(_owners(session, organization.id)),
            "teams": len(teams),
            "players_on_sheets": sum(int(session.scalar(select(func.count()).select_from(ClubTeamMember).where(ClubTeamMember.team_id == team.id)) or 0) for team in teams),
            "member_limit": MAX_MEMBERS_PER_ORGANIZATION,
            "team_limit": MAX_TEAMS_PER_ORGANIZATION,
        },
        "teams": [team_view(session, team) for team in teams],
        "rules": rules(),
        "limitations": limitations(),
        "isolation_rule": access.matrix()["rule"],
        "data_origin": "user",
        "is_demo_data": False,
        "demo_data": False,
    }


def organization_by_identifier(session: Session, user: User, ident: str) -> dict[str, Any]:
    """Resolve a tenant by slug or id and read it as this account sees it — a foreign one answers as absent."""
    return organization_view(session, _organization(session, ident), user, ident=ident)


def organization_entitlements(session: Session, user: User, ident: str) -> dict[str, Any]:
    """What this tenant is entitled to and what it has spent, in the current period.

    Gated on *standing* rather than on a permission for the same reason `organization_view` is: a ceiling is the
    tenant's contract with the platform, not a staff right, so a coach — or a `parent`, who holds none of them —
    is entitled to read the number their own write will be measured against. A foreign or unknown tenant answers
    with §39's absence here too, before any plan row is looked up.

    Two figures a page must not blend are printed apart on purpose. `items[].limit` is the *plan's* ceiling, and
    only the feature whose `enforced` is true is refused on today by a door that checks it; the tier's own
    constants (`counts.member_limit`, `sessions`' `limit`) come from the code that holds the rows and are printed
    by the doors that own them. And nothing grants a plan in this build, so every tenant is metered against the
    row `free` holds — which is a row somebody can edit, not a number chosen here.
    """
    organization, membership = standing(session, user, ident)
    view = ent.entitlements_view(session, organization.id, plan=ent.DEFAULT_PLAN, subject_kind="organization")
    return {
        **view,
        "organization": organization.slug,
        "subject_id": organization.id,
        "role": membership.role,
        "read_through": "standing — every active member of the tenant reads its own ceiling, whoever holds which permission",
        "plan_rule": f"nothing in this build grants a plan, so every tenant is metered against {ent.DEFAULT_PLAN!r}: that row is data an operator edits in the entitlements table, not a constant this function holds",
        "enforced_rule": "only a feature whose `enforced` is true is refused today by a door that checks it; the others are the plan's promise, and the tier that owns each wires it",
        "tier_limits": {
            "members": MAX_MEMBERS_PER_ORGANIZATION,
            "teams": MAX_TEAMS_PER_ORGANIZATION,
            "rule": "these two are the constants §39's own writes are refused on, printed beside the plan ceilings so a page can show which is which rather than choosing between them",
        },
        "no_payment": ent.NO_PAYMENT,
        "capabilities_door": "/api/v1/entitlements/capabilities",
        "account_door": "/api/v1/entitlements/me",
        "demo_data": False,
    }


def my_organizations(session: Session, user: User) -> dict[str, Any]:
    """The tenants this account *stands in*, which is not the same set as the tenants it has rows for.

    The status filter is the whole point of this query. An `invited` row is answered by `my_invitations`, and a
    `revoked` one is the record of a departure — listing either here would put a card on a page that 404s when
    clicked, because `organization_view()` refuses exactly the same row. A listing and a read must agree.
    """
    rows = list(
        session.scalars(
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user.id, OrganizationMember.status == "active")
            .order_by(Organization.name)
        )
    )
    items: list[dict[str, Any]] = []
    for organization in rows:
        # One lookup per tenant, not two: the membership is what the listing's role and status come from,
        # and the row is guaranteed by the join above even though its type does not say so.
        membership = membership_of(session, organization, user)
        items.append(
            {
                "slug": organization.slug,
                "name": organization.name,
                "kind": organization.kind,
                "role": membership.role if membership else "",
                "status": membership.status if membership else "",
                "active_members": _count_members(session, organization.id),
                "teams": len(_teams_of(session, organization.id)),
                "path": f"/club/{organization.slug}",
            }
        )
    return {
        "items": items,
        "total": len(rows),
        "limit": MAX_ORGANIZATIONS_PER_USER,
        "room_left": max(0, MAX_ORGANIZATIONS_PER_USER - len(rows)),
        "rule": "an organisation is listed for an active member and for nobody else; an invitation waits on GET /club/invitations, and a revoked standing lists nothing at all",
    }


def create_organization(session: Session, user: User, *, name: str, kind: str = "club", country: str = "", visibility_default: str = "members") -> dict[str, Any]:
    label = str(name).strip()
    if not label:
        raise ClubRefusal("name_required", f"an organisation needs a name between 1 and {NAME_MAX} characters; this one is {len(label)} after stripping", length=len(label), max=NAME_MAX)
    if len(label) > NAME_MAX:
        raise ClubRefusal("name_required", f"{label[:24]!r} — is {len(label)} characters and this column holds {NAME_MAX}", length=len(label), max=NAME_MAX)
    if str(kind) not in KINDS:
        raise ClubRefusal("unknown_kind", f"{kind!r} is not one of the tenant kinds §41 asks for", kind=kind, kinds=list(KINDS))
    if str(visibility_default) not in VISIBILITY_DEFAULTS:
        raise ClubRefusal("unknown_visibility", f"{visibility_default!r} is not a report visibility this tier understands", visibility_default=visibility_default, allowed=list(VISIBILITY_DEFAULTS))
    held = int(session.scalar(select(func.count()).select_from(Organization).where(Organization.created_by == user.id)) or 0)
    if held >= MAX_ORGANIZATIONS_PER_USER:
        raise ClubRefusal(
            "organization_limit",
            f"this account has opened {MAX_ORGANIZATIONS_PER_USER} organisations, which is the cap; being invited into another one is always free",
            held=held,
            limit=MAX_ORGANIZATIONS_PER_USER,
        )

    slug = slugify(label)[:90] or "organization"
    if session.scalar(select(Organization).where(Organization.slug == slug)):
        raise ClubRefusal(
            "name_required", f"an organisation called {label!r} already exists in this world; a second one would be reachable only by a number appended to its name", name=label, slug=slug
        )
    organization = Organization(id=new_public_id("org"), slug=slug, name=label, kind=str(kind), country=_country(country), visibility_default=str(visibility_default), created_by=user.id)
    session.add(organization)
    session.flush()
    # The founder is the owner and the first member, in the same transaction as the tenant itself: an
    # organisation nobody can act inside is a row that cannot be deleted by anyone.
    session.add(OrganizationMember(id=new_public_id("orgm"), organization_id=organization.id, user_id=user.id, role="owner", status="active"))
    if not user.organization_id:
        user.organization_id = organization.id
    session.commit()
    return {
        "organization": organization_view(session, organization, user, ident=organization.slug)["organization"],
        "my_grant": access.grant("owner", "active"),
        "members": 1,
        "teams": 0,
        "room_left": MAX_MEMBERS_PER_ORGANIZATION - 1,
    }


def rename_organization(
    session: Session, user: User, ident: str, *, name: str | None = None, kind: str | None = None, country: str | None = None, visibility_default: str | None = None
) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "org.rename")
    changed: dict[str, Any] = {}
    if name is not None:
        label = str(name).strip()
        if not label or len(label) > NAME_MAX:
            raise ClubRefusal("name_required", f"a tenant name must be between 1 and {NAME_MAX} characters; this one is {len(label)}", length=len(label), max=NAME_MAX)
        organization.name = changed["name"] = label
    if kind is not None:
        if str(kind) not in KINDS:
            raise ClubRefusal("unknown_kind", f"{kind!r} is not one of the tenant kinds §41 asks for", kind=kind, kinds=list(KINDS))
        organization.kind = changed["kind"] = str(kind)
    if country is not None:
        organization.country = changed["country"] = _country(country)
    if visibility_default is not None:
        if str(visibility_default) not in VISIBILITY_DEFAULTS:
            raise ClubRefusal(
                "unknown_visibility", f"{visibility_default!r} is not a report visibility this tier understands", visibility_default=visibility_default, allowed=list(VISIBILITY_DEFAULTS)
            )
        organization.visibility_default = changed["visibility_default"] = str(visibility_default)
    session.commit()
    return {
        "organization": organization_view(session, organization, user, ident=ident)["organization"],
        "changed": changed,
        "rule": "the slug is not one of these: a tenant's address is how other people's bookmarks, boards and reports reach it",
    }


def delete_organization(session: Session, user: User, ident: str) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "org.delete")
    teams = _teams_of(session, organization.id)
    sheets = int(session.scalar(select(func.count()).select_from(ClubTeamMember).where(ClubTeamMember.team_id.in_([team.id for team in teams]))) or 0)
    members = _count_members(session, organization.id, "active") + _count_members(session, organization.id, "invited") + _count_members(session, organization.id, "revoked")
    slug = organization.slug
    # `users.organization_id` is a pointer this tier does not own, and nothing in the database would stop it
    # naming a tenant that is being deleted. It is cleared here rather than left for `access_problems()` to
    # report later as an organisation that no longer answers to anybody.
    session.execute(update(User).where(User.organization_id == organization.id).values(organization_id=None))
    session.delete(organization)
    session.commit()
    return {
        "deleted": True,
        "organization": slug,
        "members_left": members,
        "teams_left": len(teams),
        "players_left_off": sheets,
        "rule": "the cascade takes the memberships and the team sheets; the players on them are the world's rows and are not touched by deleting a tenant that listed them",
    }


def invite_member(session: Session, user: User, ident: str, *, email: str, role: str) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "org.member.invite")
    if not access.is_role(role):
        raise ClubRefusal(
            "unknown_role", f"{role!r} is not a role this tier knows, and a role it does not know grants nothing — invite them as one of these instead", role=role, roles=list(access.ROLES)
        )
    person = session.scalar(select(User).where(User.email == str(email).strip().lower()))
    if person is None:
        raise ClubRefusal("no_such_user", f"no account on this platform uses {str(email)!r}; §41's B2B invitation joins an existing account to a tenant, it does not create one", email=str(email))
    if membership_of(session, organization, person) is not None:
        raise ClubRefusal("already_a_member", f"{person.display_name} already has a row on {organization.name}; change their role rather than adding a second membership", email=person.email)
    held = _count_members(session, organization.id, "active") + _count_members(session, organization.id, "invited")
    if held >= MAX_MEMBERS_PER_ORGANIZATION:
        raise ClubRefusal(
            "member_limit", f"{organization.name} holds {held} of {MAX_MEMBERS_PER_ORGANIZATION} memberships; revoke a departure before adding another", held=held, limit=MAX_MEMBERS_PER_ORGANIZATION
        )
    member = OrganizationMember(id=new_public_id("orgm"), organization_id=organization.id, user_id=person.id, role=str(role), status="invited", invited_by=user.id)
    session.add(member)
    session.commit()
    return {
        "organization": organization.slug,
        "member": _member_row(session, member),
        "no_mail_sent": "the invitation is a row, not an email: this platform has no mail transport, so the person it names accepts it themselves at GET /club/invitations",
        "members": held + 1,
        "room_left": max(0, MAX_MEMBERS_PER_ORGANIZATION - held - 1),
    }


def my_invitations(session: Session, user: User) -> dict[str, Any]:
    rows = list(session.scalars(select(OrganizationMember).where(OrganizationMember.user_id == user.id, OrganizationMember.status == "invited")))
    items: list[dict[str, Any]] = []
    for member in rows:
        tenant = session.get(Organization, member.organization_id)
        items.append(
            {
                "membership": member.id,
                "organization": tenant.slug if tenant else None,
                "name": tenant.name if tenant else None,
                "role": member.role,
                "invited_at": member.created_at.isoformat() if member.created_at else None,
            }
        )
    return {
        "items": items,
        "total": len(rows),
        "rule": "an invitation grants nothing until it is accepted here — see the matrix's `statuses` for why",
    }


def accept_invitation(session: Session, user: User, ident: str) -> dict[str, Any]:
    """Take up an invitation addressed to this account.

    A caller with no row here is a stranger, and `decline_invitation` and this door answer a stranger with the
    same 404 — one that repeats the address the caller typed and nothing the lookup resolved. Printing
    `organization.slug` would turn `POST /club/{opaque id}/accept` into a directory of every tenant on the
    platform, which is the exact confirmation the 404 exists to withhold.
    """
    organization = _organization(session, ident)
    member = membership_of(session, organization, user)
    if member is None:
        raise ClubRefusal("no_such_organization", f"nobody has invited you to {str(ident)!r}", ident=str(ident))
    if member.status != "invited":
        raise ClubRefusal(
            "already_a_member", f"your standing at {organization.name} is {member.status}, not an invitation waiting to be accepted", organization=organization.slug, status=member.status
        )
    member.status = "active"
    if not user.organization_id:
        user.organization_id = organization.id
    session.commit()
    return {"organization": organization.slug, "my_grant": access.grant(member.role, member.status), "accepted": True}


def decline_invitation(session: Session, user: User, ident: str) -> dict[str, Any]:
    """Turn an invitation down.

    A caller with no row here is a stranger to this tenant and is answered as one (`no_such_organization`),
    which is the same answer the isolation rule gives them on every other door — the second decline of an
    invitation you already declined has no row either, and it gets that same answer for that same reason. A
    caller who *does* hold a standing that simply is not an invitation (active, or revoked) is told
    `no_such_member`, because for them the tenant is already theirs and the useful answer is about the row.
    """
    organization = _organization(session, ident)
    member = membership_of(session, organization, user)
    if member is None:
        raise ClubRefusal("no_such_organization", f"no organisation of yours answers to {ident!r}", ident=str(ident))
    if member.status != "invited":
        raise ClubRefusal("no_such_member", f"there is no open invitation from {organization.slug!r} for you to decline", organization=organization.slug, status=member.status)
    session.delete(member)
    session.commit()
    return {
        "organization": organization.slug,
        "declined": True,
        "rule": "an unaccepted invitation is deleted rather than revoked: nothing was ever granted, so there is no standing to record the end of",
    }


def set_member_role(session: Session, user: User, ident: str, *, email: str, role: str) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "org.member.role")
    if not access.is_role(role):
        raise ClubRefusal("unknown_role", f"{role!r} is not a role this tier knows", role=role, roles=list(access.ROLES))
    person = session.scalar(select(User).where(User.email == str(email).strip().lower()))
    member = membership_of(session, organization, person) if person else None
    if member is None:
        raise ClubRefusal("no_such_member", f"{email!r} is not a member of {organization.name}, so there is no role to set", email=str(email), organization=organization.slug)
    if member.role == "owner" and str(role) != "owner" and len(_owners(session, organization.id)) <= 1:
        raise ClubRefusal(
            "last_owner",
            f"{organization.name} has one owner; demoting them would leave the tenant with nobody who can delete it or hand it over",
            organization=organization.slug,
            owners=len(_owners(session, organization.id)),
        )
    member.role = str(role)
    session.commit()
    return {
        "organization": organization.slug,
        "member": _member_row(session, member),
        "rule": "the role is what changes; the rights that move with it are the published matrix's, not stored per person",
    }


def revoke_member(session: Session, user: User, ident: str, *, email: str) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "org.member.revoke")
    person = session.scalar(select(User).where(User.email == str(email).strip().lower()))
    member = membership_of(session, organization, person) if person else None
    if member is None or member.status == "revoked":
        raise ClubRefusal("no_such_member", f"{email!r} is not standing in {organization.name}", email=str(email), organization=organization.slug)
    if member.role == "owner" and len(_owners(session, organization.id)) <= 1:
        raise ClubRefusal("last_owner", f"{organization.name} has one owner, and revoking them would orphan the tenant", organization=organization.slug, owners=1)
    member.status = "revoked"
    # The legacy pointer is cleared here for the same reason `delete_organization` clears it: leaving it
    # naming this tenant would turn an honest column into a divergence `access_problems()` has to report on
    # every read afterwards, and the row it points at already says `revoked`.
    if person is not None and person.organization_id == organization.id:
        person.organization_id = None
    session.commit()
    return {
        "organization": organization.slug,
        "member": _member_row(session, member),
        "rule": "the row is kept and marked revoked, so who could see what while they stood in the tenant remains answerable after they leave",
        "seat_freed": "a revoked membership is the record, not the headcount: it holds its row and gives its seat back, so `member_limit` counts only who is standing here now",
    }


def create_team(session: Session, user: User, ident: str, *, name: str, age_group: str = "open", stage: str = "youth", world_team: str | None = None) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "team.create")
    label = str(name).strip()
    if not label or len(label) > TEAM_NAME_MAX:
        raise ClubRefusal("name_required", f"a team needs a name between 1 and {TEAM_NAME_MAX} characters; this one is {len(label)}", length=len(label), max=TEAM_NAME_MAX)
    teams = _teams_of(session, organization.id)
    if len(teams) >= MAX_TEAMS_PER_ORGANIZATION:
        raise ClubRefusal("team_limit", f"{organization.name} already runs {MAX_TEAMS_PER_ORGANIZATION} teams, which is the cap", held=len(teams), limit=MAX_TEAMS_PER_ORGANIZATION)
    if any(team.name.lower() == label.lower() for team in teams):
        raise ClubRefusal("team_name_taken", f"{organization.name} already has a team called {label!r}; two sheets of one name cannot be told apart by the players on them", name=label)
    world: WorldTeam | None = None
    if world_team:
        world = session.scalar(select(WorldTeam).where(WorldTeam.slug == str(world_team))) or session.scalar(select(WorldTeam).where(WorldTeam.id == str(world_team)))
        if world is None:
            raise ClubRefusal("no_such_world_club", f"no club in the generated world is named {world_team!r}, so the team cannot be placed in that ladder", world_team=str(world_team))
    team = ClubTeam(
        id=new_public_id("ctm"), organization_id=organization.id, name=label, age_group=str(age_group)[:24] or "open", stage=str(stage)[:16] or "youth", world_team_id=(world.id if world else None)
    )
    session.add(team)
    session.commit()
    return {"organization": organization.slug, "team": team_view(session, team), "teams": len(teams) + 1, "room_left": max(0, MAX_TEAMS_PER_ORGANIZATION - len(teams) - 1)}


def update_team(session: Session, user: User, ident: str, team_ident: str, *, name: str | None = None, age_group: str | None = None, stage: str | None = None) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "team.edit")
    team = _team(session, organization, team_ident)
    changed: dict[str, Any] = {}
    if name is not None:
        label = str(name).strip()
        if not label or len(label) > TEAM_NAME_MAX:
            raise ClubRefusal("name_required", f"a team name must be between 1 and {TEAM_NAME_MAX} characters; this one is {len(label)}", length=len(label), max=TEAM_NAME_MAX)
        if label.lower() != team.name.lower() and any(other.name.lower() == label.lower() for other in _teams_of(session, organization.id) if other.id != team.id):
            raise ClubRefusal("team_name_taken", f"{organization.name} already has a team called {label!r}", name=label)
        team.name = changed["name"] = label
    if age_group is not None:
        team.age_group = changed["age_group"] = str(age_group)[:24] or "open"
    if stage is not None:
        team.stage = changed["stage"] = str(stage)[:16] or "youth"
    session.commit()
    return {"team": team_view(session, team), "changed": changed, "rule": "age_group is what the reporting tier reads to decide a squad contains minors; renaming a team does not change who is on it"}


def delete_team(session: Session, user: User, ident: str, team_ident: str) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "team.delete")
    team = _team(session, organization, team_ident)
    size = int(session.scalar(select(func.count()).select_from(ClubTeamMember).where(ClubTeamMember.team_id == team.id)) or 0)
    name = team.name
    session.delete(team)
    session.commit()
    return {"deleted": True, "team": name, "players_left_off": size, "rule": "the sheet is gone and the players are not; their rows belong to the generated world, and no team deletion edits them"}


def _team(session: Session, organization: Organization, ident: str) -> ClubTeam:
    team = session.scalar(select(ClubTeam).where(ClubTeam.organization_id == organization.id, ClubTeam.id == str(ident))) or session.scalar(
        select(ClubTeam).where(ClubTeam.organization_id == organization.id, ClubTeam.name == str(ident))
    )
    if team is None:
        raise ClubRefusal(
            "no_such_team", f"no team of {organization.name} answers to {str(ident)!r} — a team is found inside its own tenant, by id or by name", ident=str(ident), organization=organization.slug
        )
    return team


def add_to_squad(session: Session, user: User, ident: str, team_ident: str, *, player: str, note: str = "") -> dict[str, Any]:
    organization, _ = require(session, user, ident, "squad.write")
    team = _team(session, organization, team_ident)
    if len(str(note)) > NOTE_MAX:
        raise ClubRefusal("name_required", f"a squad note is capped at {NOTE_MAX} characters and this one is {len(str(note))}", length=len(str(note)), max=NOTE_MAX)
    person = session.scalar(select(RealPlayer).where(RealPlayer.slug == str(player).strip()))
    if person is None:
        raise ClubRefusal("no_such_player", f"no player in the generated world is called {str(player)!r}, so nobody can be put on a sheet under that name", ident=str(player))
    if session.scalar(select(ClubTeamMember.id).where(ClubTeamMember.team_id == team.id, ClubTeamMember.player_id == person.id)):
        raise ClubRefusal("already_on_team", f"{person.name} is already on {team.name}; a second row would make the sheet's own size lie about who it holds", team=team.name, player=person.slug)
    size = int(session.scalar(select(func.count()).select_from(ClubTeamMember).where(ClubTeamMember.team_id == team.id)) or 0)
    if size >= MAX_SQUAD_PER_TEAM:
        raise ClubRefusal("squad_full", f"{team.name} already has {MAX_SQUAD_PER_TEAM} players on its sheet, which is the cap", held=size, limit=MAX_SQUAD_PER_TEAM)
    session.add(ClubTeamMember(id=new_public_id("ctmm"), team_id=team.id, player_id=person.id, note=str(note).strip()))
    session.commit()
    return {
        "team": team_view(session, team),
        "stored": {"team_id": team.id, "player_id": person.id, "note": str(note).strip()},
        "not_stored": "age, overall, potential, position or any other figure — the sheet points at the player's row and reads it again on every request",
        "rule": "one sheet lists a player once; the same player may stand for another team of the same tenant, and for another tenant entirely",
    }


def remove_from_squad(session: Session, user: User, ident: str, team_ident: str, *, player: str) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "squad.write")
    team = _team(session, organization, team_ident)
    person = session.scalar(select(RealPlayer).where(RealPlayer.slug == str(player).strip()))
    row = session.scalar(select(ClubTeamMember).where(ClubTeamMember.team_id == team.id, ClubTeamMember.player_id == person.id)) if person else None
    if row is None:
        raise ClubRefusal("no_such_player", f"{str(player)!r} is not on {team.name}'s sheet, so there is nothing here to take off it", player=str(player), team=team.name)
    session.delete(row)
    session.commit()
    return {"team": team_view(session, team), "removed": (person.slug if person else str(player)), "rule": "the sheet loses a pointer; the player's row and every other sheet he is on keep it"}


def squad_view(session: Session, user: User, ident: str, team_ident: str) -> dict[str, Any]:
    organization, _ = require(session, user, ident, "squad.read")
    return team_view(session, _team(session, organization, team_ident))


def rules() -> dict[str, Any]:
    return {
        "matrix": access.matrix(),
        "kinds": list(KINDS),
        "visibility_defaults": list(VISIBILITY_DEFAULTS),
        "country": "two letters, stored upper-cased, or blank; a longer value is refused rather than cut down to a code that names nothing",
        "max_organizations_per_user": MAX_ORGANIZATIONS_PER_USER,
        "max_members_per_organization": MAX_MEMBERS_PER_ORGANIZATION,
        "max_teams_per_organization": MAX_TEAMS_PER_ORGANIZATION,
        "max_squad_per_team": MAX_SQUAD_PER_TEAM,
        "name_max": NAME_MAX,
        "team_name_max": TEAM_NAME_MAX,
        "note_max": NOTE_MAX,
        "founder": "the account that opens a tenant is its owner and its first active member, in the same transaction as the tenant",
        "invitations": "a row, not an email — nothing here sends anything to anybody",
        "addressing": "a tenant is reached by its slug or its id; a team inside it by its id or its name; both are scoped to the tenant, and a foreign one is answered as one that does not exist",
        "refusals": list(REFUSALS),
    }


def limitations() -> list[str]:
    return [
        "no match report or message exists in this tier — §39's remaining rows arrive in the ones after it, and this one only decides who may see them; §40's development plans and §41's sessions and saved reports are separate services, read through /club/academy",
        "an organisation's teams point at the generated world's players, not at copies of them: a tenant's sheet is a selection over the same rows the scout searches, so a rating cannot go stale on a sheet any more than on a shortlist",
        "the invitation is a row and not a message: no mail transport exists in this project, and none is claimed by it",
        "revoked memberships keep their rows for the record and grant nothing, and they give their seat back to `member_limit`; there is no audit trail of who did what before the revocation, only of who stood where",
        "a parent's row in the matrix holds three rights and every one of them is scoped by a consent row, not by the tenant: `plan.read_own_child` opens one named child's plan and no other, which is why the row is short rather than empty",
        "deleting a tenant removes its memberships and sheets, and rewrites nothing about a player, a club, or a career in the generated world",
        "the per-minute ceilings on these doors are counted per client address over one path, so a deployment behind a proxy that forwards from a single address gives every tenant it serves the same bucket: a 429 says the address is busy, not which account tripped it, and the ceilings themselves are code at each door rather than a published figure",
    ]


def club_tables_present(session: Session) -> bool:
    """Whether this database has been migrated to `0016` — the gate is presence, not usage.

    Without it the capability flags would raise on any environment that has not run the migration yet, which is
    a page-load path, and a page-load path must report an empty working surface rather than a 500.
    """
    names = inspect(session.get_bind()).get_table_names()
    return "organizations" in names and "organization_members" in names


def club_ready(session: Session) -> bool:
    return club_tables_present(session) and bool(session.scalar(select(User.id).limit(1)))


READY_RULE = (
    "`ready` is two conditions and no third: this database holds the tables this tier writes to, and it holds at least one "
    "account. A freshly created database therefore answers false here, which is the honest answer rather than a fault a caller "
    "works around — and the first account registered is what turns it true."
)


def club_counts(session: Session) -> dict[str, Any]:
    if not club_tables_present(session):
        return {
            "organizations": 0,
            "memberships": 0,
            "active_memberships": 0,
            "teams": 0,
            "squad_rows": 0,
            "rule": "the tenant tables are not in this database yet; nothing here is counted because nothing here exists",
        }
    return {
        "organizations": int(session.scalar(select(func.count()).select_from(Organization)) or 0),
        "memberships": int(session.scalar(select(func.count()).select_from(OrganizationMember)) or 0),
        "active_memberships": int(session.scalar(select(func.count()).select_from(OrganizationMember).where(OrganizationMember.status == "active")) or 0),
        "teams": int(session.scalar(select(func.count()).select_from(ClubTeam)) or 0),
        "squad_rows": int(session.scalar(select(func.count()).select_from(ClubTeamMember)) or 0),
        "rule": "counts of tenants and standing only; every player figure a club page prints is read from `real_players` on the request",
    }


def access_problems(session: Session, user: User) -> dict[str, Any]:
    """The invariants this tier exists to hold, checked over the caller's own tenants.

    A tenant with no owner, a membership outside the matrix's roles, an inactive membership that still grants a
    right, and a `users.organization_id` pointing at a tenant the account is not an active member of — each one is
    a way for the isolation rule to stop being true without any single row looking wrong.
    """
    if not club_tables_present(session):
        return {
            "clean": False,
            "problems": ["the tenant tables are not in this database"],
            "checked": {"organizations": 0, "memberships": 0, "teams": 0},
            "rule": "an un-migrated database is reported, not assumed sound",
        }
    problems: list[str] = []
    organizations = list(
        session.scalars(select(Organization).join(OrganizationMember, OrganizationMember.organization_id == Organization.id).where(OrganizationMember.user_id == user.id).order_by(Organization.slug))
    )
    for organization in organizations:
        if not _owners(session, organization.id):
            problems.append(f"{organization.slug}: no active owner, so nothing in it can be renamed, handed over, or deleted")
        for member in session.scalars(select(OrganizationMember).where(OrganizationMember.organization_id == organization.id)):
            if not access.is_role(member.role):
                problems.append(f"{member.id}: the role {member.role!r} is not one of the published roles, so it grants nothing")
            if member.status not in ("active", "invited", "revoked"):
                problems.append(f"{member.id}: status {member.status!r} is not one this tier understands")
            if member.status != "active" and access.permissions_of(member.role) and access.grant(member.role, member.status)["permissions"]:
                problems.append(f"{member.id}: a {member.status} membership still grants permissions")
        for team in _teams_of(session, organization.id):
            size = int(session.scalar(select(func.count()).select_from(ClubTeamMember).where(ClubTeamMember.team_id == team.id)) or 0)
            if size > MAX_SQUAD_PER_TEAM:
                problems.append(f"{team.id}: {size} players on one sheet, above the cap of {MAX_SQUAD_PER_TEAM}")
            if not team.name.strip():
                problems.append(f"{team.id}: a team with no name cannot be picked out of a tenant's list")
    own = session.scalar(select(User).where(User.id == user.id))
    if own is not None and own.organization_id:
        link = session.get(Organization, own.organization_id)
        # `own_member`, not `member`: the row above iterates `OrganizationMember`, and reusing the name
        # would narrow the loop variable's type to something that can hold None.
        own_member = membership_of(session, link, own) if link else None
        if link is None:
            problems.append(f"{own.id}: organization_id names no organisation this platform has")
        elif own_member is None or own_member.status != "active":
            problems.append(f"{own.id}: organization_id points at {link.slug}, where this account is not an active member")
    return {
        "clean": not problems,
        "problems": problems,
        "checked": {
            "organizations": len(organizations),
            "memberships": sum(
                int(session.scalar(select(func.count()).select_from(OrganizationMember).where(OrganizationMember.organization_id == organization.id)) or 0) for organization in organizations
            ),
            "teams": sum(len(_teams_of(session, organization.id)) for organization in organizations),
        },
        "rule": "every check here is one shape of the sentence in `access.matrix()`: a member of one organisation can read and change nothing in another",
    }
