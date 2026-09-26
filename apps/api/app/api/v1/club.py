"""Club OS endpoints (M8, spec §39 and §41): a tenant, its staff, its teams, and what your role allows.

Every door here except two belongs to an account, and the two that are public say only what the tier's rules
are: `GET /club/capabilities` publishes the role→permission matrix and the counts of tenants on the platform.
That is the whole public surface, because the question §41's B2B model has to answer out loud is *who can see
what* — and a page cannot show a member their own rights without the matrix being readable first.

The isolation rule (§39's one sentence) is not implemented per route. Each door below calls
`organizations.require(session, user, ident, permission)`, which resolves the tenant, checks that the caller
has a membership at all, and then checks what that membership's role grants. Two consequences are visible in
the answers:

* a tenant that is not yours answers `no_such_organization` with a 404, never a 403 — an endpoint that said
  "not allowed" would confirm that the slug exists, and which academies have signed up is not this tier's to
  publish;
* a 403 exists only for a member asking for more than their role holds, at which point the tenant is already
  theirs and naming the permission, the role and the rights it does hold answers a real question.

The literal paths (`/capabilities`, `/invitations`) are declared before `/club/{ident}` so a tenant cannot be
shadowed by a slug that happens to be spelled `invitations`.

This module also publishes §40's door guide. The academy's doors are routed in `club_academy.py` under
`/club/academy/…`, and `GET /club/capabilities` prints both lists as one `routes` array, because §39's test
holds that array against the whole `/api/v1/club` route table — and a guide that covered only the tier writing
it would pass that test while a page still could not find the plans doors.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.club_academy import ROUTE_GUIDE as ACADEMY_ROUTES
from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import User
from app.services.club import organizations as club
from app.services.club.organizations import ClubRefusal

router = APIRouter(prefix="/club", tags=["club-os"])

#: The refusal's code decides the answer, and the sets are the service's own — a code the route had to guess at
#: would be a second policy, and the suite asserts the sets are closed instead.
#: Which answer each code deserves, assembled from the service's own four sets: a route that mapped codes by
#: hand would be a second policy, and the suite below asserts the sets are closed rather than trusting this.
_ANSWERS: dict[str, int] = {
    **dict.fromkeys(club.NOT_FOUND_CODES, status.HTTP_404_NOT_FOUND),
    **dict.fromkeys(club.UNPROCESSABLE_CODES, status.HTTP_422_UNPROCESSABLE_ENTITY),
    **dict.fromkeys(club.CONFLICT_CODES, status.HTTP_409_CONFLICT),
    **dict.fromkeys(club.FORBIDDEN_CODES, status.HTTP_403_FORBIDDEN),
}


def _refusal(error: ClubRefusal) -> HTTPException:
    code = _ANSWERS.get(error.code, status.HTTP_400_BAD_REQUEST)
    return HTTPException(code, detail=error.to_dict())


class OrganizationIn(BaseModel):
    """A tenant's identity. The slug is derived from the name here and never accepted from a caller.

    `max_length` here is a body guard, not the rule: the published cap is `rules()["name_max"]`, and the
    service answers an over-long name with `name_required` *and the two figures* (`length`, `max`) that a
    page needs to show why. A request validator one character earlier would answer with a schema error that
    carries neither, so the guard sits well above the cap the API advertises.
    """

    name: str = Field(default="", max_length=club.NAME_MAX + 64)
    kind: str = Field(default="club", max_length=32)
    # The schema holds eight characters so a three-letter code reaches the service, which answers it
    # with `unknown_country` and the length it was given; bound at two, the schema would answer first and carry neither.
    country: str = Field(default="", max_length=8)
    visibility_default: str = Field(default="members", max_length=16)


class OrganizationPatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=club.NAME_MAX + 64)
    kind: str | None = Field(default=None, max_length=32)
    country: str | None = Field(default=None, max_length=8)
    visibility_default: str | None = Field(default=None, max_length=16)


class InviteIn(BaseModel):
    email: str = Field(default="", max_length=320)
    role: str = Field(default="coach", max_length=24)


class RoleIn(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    role: str = Field(min_length=1, max_length=24)


class TeamIn(BaseModel):
    # Same reason as `OrganizationIn.name`: the schema bounds the body, the service states the rule.
    name: str = Field(default="", max_length=club.TEAM_NAME_MAX + 64)
    age_group: str = Field(default="open", max_length=24)
    stage: str = Field(default="youth", max_length=16)
    world_team: str | None = Field(default=None, max_length=96)


class TeamPatchIn(BaseModel):
    name: str | None = Field(default=None, max_length=club.TEAM_NAME_MAX + 64)
    age_group: str | None = Field(default=None, max_length=24)
    stage: str | None = Field(default=None, max_length=16)


class SquadIn(BaseModel):
    player: str = Field(min_length=1, max_length=160)
    # Bound above the published cap, not at it: at `NOTE_MAX` the schema answered a long note with a bare
    # validation error, while `rules()["note_max"]` promises the refusal that carries `length` and `max`.
    note: str = Field(default="", max_length=club.NOTE_MAX + 64)


#: The door guide `GET /club/capabilities` publishes for a page to print: one line per door with its own methods
#: and its full path, rather than prose, so the suite can hold every line against the route table in both
#: directions. A published door the API does not have is a broken link on a page, and an unlisted door is a
#: right nobody can find — and neither mistake shows up in a sentence.
ROUTE_GUIDE: Final = (
    {"methods": ["GET", "POST"], "path": "/api/v1/club", "purpose": "the tenants this account stands in, and opening one"},
    {"methods": ["GET"], "path": "/api/v1/club/capabilities", "purpose": "the published rulebook, readable before anybody signs in"},
    {"methods": ["GET"], "path": "/api/v1/club/invitations", "purpose": "the invitations addressed to this account, which grant nothing until accepted"},
    {"methods": ["GET", "PATCH", "DELETE"], "path": "/api/v1/club/{ident}", "purpose": "one tenant: its standing, its staff, its teams and its sheets"},
    {"methods": ["GET"], "path": "/api/v1/club/{ident}/entitlements", "purpose": "the tenant's own ceilings and what it has spent this period — a standing reads them, they are not a staff right"},
    {"methods": ["POST"], "path": "/api/v1/club/{ident}/invites", "purpose": "offer a standing to an existing account; nothing is emailed"},
    {"methods": ["POST"], "path": "/api/v1/club/{ident}/accept", "purpose": "take up an invitation addressed to you"},
    {"methods": ["POST"], "path": "/api/v1/club/{ident}/decline", "purpose": "turn an invitation down, which deletes the row rather than revoking it"},
    {"methods": ["PATCH"], "path": "/api/v1/club/{ident}/members", "purpose": "change a member's role, the only way their rights change"},
    {"methods": ["DELETE"], "path": "/api/v1/club/{ident}/members/{email}", "purpose": "revoke a membership; the row stays and grants nothing"},
    {"methods": ["POST"], "path": "/api/v1/club/{ident}/teams", "purpose": "name a team of the tenant"},
    {"methods": ["PATCH", "DELETE"], "path": "/api/v1/club/{ident}/teams/{team}", "purpose": "change or remove a team; the tenant's own read prints its sheets, so there is no list route"},
    {"methods": ["GET", "POST"], "path": "/api/v1/club/{ident}/teams/{team}/players", "purpose": "read one sheet, or put a player on it"},
    {"methods": ["DELETE"], "path": "/api/v1/club/{ident}/teams/{team}/players/{player}", "purpose": "take a player off one sheet"},
)


@router.get("/capabilities")
def read_capabilities(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    """The published rulebook: which roles exist, what each holds, and how many tenants are on the platform.

    `routes` is the door guide of the whole `/api/v1/club` surface, §40's academy doors included. A page handed
    half a list cannot tell the difference between a door it was not told about and one that does not exist, and
    §39's own test holds this list against the route table in both directions — so the guide has to be the union
    or the test is measuring half the tier.
    """
    limit(request, 60, 60, scope="club_capabilities")
    return {
        **club.rules(),
        "counts": club.club_counts(db),
        "ready": club.club_ready(db),
        "ready_rule": club.READY_RULE,
        "refusal_answers": {code: _ANSWERS[code] for code in club.REFUSALS},
        "limitations": club.limitations(),
        "data_origin": "project-authored",
        "is_demo_data": False,
        "demo_data": False,
        "routes": [dict(line) for line in (*ROUTE_GUIDE, *ACADEMY_ROUTES)],
    }


@router.get("/invitations")
def read_invitations(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Invitations addressed to this account. They grant nothing until accepted here, which is the point of `invited`."""
    limit(request, 30, 60, scope="club_invitations")
    return {**club.my_invitations(db, user), "demo_data": False}


@router.get("")
def read_my_organizations(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The tenants this account stands in, with the role it holds in each."""
    limit(request, 30, 60, scope="club_read")
    return {**club.my_organizations(db, user), "demo_data": False}


@router.post("")
def open_organization(payload: OrganizationIn, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Open a tenant. The account that opens it is its owner, in the same transaction as the tenant itself."""
    limit(request, 10, 60, scope="club_write")
    try:
        return {**club.create_organization(db, user, name=payload.name, kind=payload.kind, country=payload.country, visibility_default=payload.visibility_default), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}")
def read_organization(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """One tenant as its member sees it: standing, staff, teams and sheets, with the matrix beside it."""
    limit(request, 30, 60, scope="club_read")
    try:
        return {**club.organization_by_identifier(db, user, ident), "integrity": club.access_problems(db, user), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/entitlements")
def read_organization_entitlements(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """What this tenant is entitled to and what it has spent — §42's ceiling read on §39's standing.

    Gated the way `GET /club/{ident}` is, because a ceiling is not a staff right: a member who cannot see the
    number their own write will be measured against is left to discover it as a refusal.
    """
    limit(request, 30, 60, scope="club_read")
    try:
        return {**club.organization_entitlements(db, user, ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.patch("/{ident}")
def rename_organization(payload: OrganizationPatchIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Change a tenant's name, kind, country or report default. Its slug stays: that is how others address it."""
    limit(request, 10, 60, scope="club_write")
    try:
        return {**club.rename_organization(db, user, ident, name=payload.name, kind=payload.kind, country=payload.country, visibility_default=payload.visibility_default), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}")
def close_organization(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Delete a tenant. Its memberships and sheets go with it; the players it listed belong to the world and stay."""
    limit(request, 10, 60, scope="club_write")
    try:
        return {**club.delete_organization(db, user, ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/invites")
def invite_to_organization(payload: InviteIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Offer a standing to an existing account. Nothing is emailed: an invitation is a row that waits."""
    limit(request, 20, 60, scope="club_write")
    try:
        return {**club.invite_member(db, user, ident, email=payload.email, role=payload.role), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/accept")
def accept_invitation(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Take up an invitation addressed to you, and hold the rights of the role it names from now on."""
    limit(request, 20, 60, scope="club_write")
    try:
        return {**club.accept_invitation(db, user, ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/decline")
def decline_invitation(ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Turn an invitation down. The row is deleted rather than revoked, because nothing was ever granted."""
    limit(request, 20, 60, scope="club_write")
    try:
        return {**club.decline_invitation(db, user, ident), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.patch("/{ident}/members")
def set_member_role(payload: RoleIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Change a member's role, which is the only way their rights change."""
    limit(request, 20, 60, scope="club_write")
    try:
        return {**club.set_member_role(db, user, ident, email=payload.email, role=payload.role), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/members/{email}")
def revoke_membership(ident: str, email: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Revoke a membership. The row stays and grants nothing, so who stood where remains answerable later."""
    limit(request, 20, 60, scope="club_write")
    try:
        return {**club.revoke_member(db, user, ident, email=email), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/teams")
def create_team(payload: TeamIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Name a team of the tenant, optionally placing it against a club in the generated world's ladder."""
    limit(request, 20, 60, scope="club_write")
    try:
        return {**club.create_team(db, user, ident, name=payload.name, age_group=payload.age_group, stage=payload.stage, world_team=payload.world_team), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.patch("/{ident}/teams/{team}")
def edit_team(payload: TeamPatchIn, ident: str, team: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Change a team's name, age band or stage. `age_group` is what later tiers read to decide minors are involved."""
    limit(request, 20, 60, scope="club_write")
    try:
        return {**club.update_team(db, user, ident, team, name=payload.name, age_group=payload.age_group, stage=payload.stage), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/teams/{team}")
def remove_team(ident: str, team: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Delete a team sheet. The players on it are untouched rows of the generated world."""
    limit(request, 20, 60, scope="club_write")
    try:
        return {**club.delete_team(db, user, ident, team), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/teams/{team}/players")
def read_squad(ident: str, team: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """One sheet, read live: every figure on it comes from the player's row on this request."""
    limit(request, 30, 60, scope="club_read")
    try:
        return {**club.squad_view(db, user, ident, team), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/teams/{team}/players")
def add_player_to_squad(payload: SquadIn, ident: str, team: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Put a player on a sheet — a pointer to the world's row, and the coach's own note, and nothing else."""
    limit(request, 30, 60, scope="club_write")
    try:
        return {**club.add_to_squad(db, user, ident, team, player=payload.player, note=payload.note), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/teams/{team}/players/{player}")
def drop_player_from_squad(ident: str, team: str, player: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Take a player off a sheet. His other sheets, and every other tenant's, are unaffected."""
    limit(request, 30, 60, scope="club_write")
    try:
        return {**club.remove_from_squad(db, user, ident, team, player=player), "demo_data": False}
    except ClubRefusal as error:
        raise _refusal(error) from None
