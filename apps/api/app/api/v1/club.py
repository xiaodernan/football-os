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

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.v1.club_academy import ROUTE_GUIDE as ACADEMY_ROUTES
from app.core.db import get_db
from app.core.security import current_user, limit
from app.models import User
from app.services.club import announcements as ann
from app.services.club import answers
from app.services.club import matches as mat
from app.services.club import organizations as club
from app.services.club.organizations import ClubRefusal

router = APIRouter(prefix="/club", tags=["club-os"])

#: Which answer each code earns is decided once, in `services/club/answers.py`, over every part of the tier's own
#: sets. A table assembled per router is how §39's door came to answer §42's `no_such_plan` with a 400 while the
#: academy door answered the same code with a 404; `answers.assemble` additionally refuses a code two tiers claim
#: with different statuses, so the ordering of the list cannot settle a disagreement in silence.
_ANSWERS: Final[dict[str, int]] = answers.ANSWERS


def _refusal(error: ClubRefusal) -> HTTPException:
    return answers.refusal(error)


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
    {
        "methods": ["GET", "POST"],
        "path": "/api/v1/club/{ident}/fixtures",
        "purpose": "arrange one fixture against a club in the generated world, and read the tenant's calendar with every figure counted from the rows on the page",
    },
    {
        "methods": ["GET", "DELETE"],
        "path": "/api/v1/club/{ident}/fixtures/{fixture}",
        "purpose": "one arrangement, and the engine's own report once it has been played; erasing it takes the appearance rows and leaves the match the engine played",
    },
    {"methods": ["POST"], "path": "/api/v1/club/{ident}/fixtures/{fixture}/play", "purpose": "play it through the simulation engine and record the eleven that played"},
    {
        "methods": ["GET", "POST"],
        "path": "/api/v1/club/{ident}/announcements",
        "purpose": "read the tenant's notice board with each notice's readership counted from the roster as it stands, or post one notice to an audience",
    },
    {
        "methods": ["GET", "DELETE"],
        "path": "/api/v1/club/{ident}/announcements/{announcement}",
        "purpose": "one notice, its readership and the caller's own receipt; erasing it takes the receipts with it",
    },
    {"methods": ["POST"], "path": "/api/v1/club/{ident}/announcements/{announcement}/read", "purpose": "record that the caller has read it, which is idempotent and answers with the figure it moved"},
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
        "counts": {**club.club_counts(db), **mat.fixture_counts(db, ready=club.club_ready(db)), **ann.announcement_counts(db, ready=club.club_ready(db))},
        "ready": club.club_ready(db),
        "ready_rule": club.READY_RULE,
        "refusal_answers": answers.published(club.REFUSALS),
        "fixture_caps": dict(mat.CAPS),
        "fixture_formulas": dict(mat.FORMULAS),
        "fixture_refusals": answers.published(mat.PUBLISHED),
        "fixture_limitation": mat.LIMITATION,
        "announcement_caps": dict(ann.CAPS),
        "announcement_formulas": dict(ann.FORMULAS),
        "announcement_refusals": answers.published(ann.PUBLISHED),
        "announcement_limitation": ann.LIMITATION,
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


class FixtureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team: str = Field(min_length=1, max_length=64)
    opponent: str = Field(min_length=1, max_length=80)
    scheduled_on: str = Field(min_length=10, max_length=10)
    side: str = Field(default="home", max_length=8)
    # Bounds *above* the published caps, which is §39's own rule for a note: at the cap the schema answers a
    # long value with a bare field error, while the rulebook prints `fixture_caps` and promises the refusal that
    # carries `length`/`max`/`named` figures a page can show.
    competition: str = Field(default="", max_length=mat.COMPETITION_MAX + 64)
    named: list[str] = Field(default_factory=list, max_length=mat.NAMED_MAX + 20)
    note: str = Field(default="", max_length=mat.NOTE_MAX + 64)


class FixturePlayIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # `minutes` is unbounded here on purpose: the engine's own `MINUTES_CHOICES` is the rule, and a schema that
    # restated it would be a second copy of a figure this tier does not own. `minutes_choice` is the service's
    # answer, with the choices printed beside it.
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    minutes: int = Field(default=mat.DEFAULT_MINUTES)


@router.post("/{ident}/fixtures")
def arrange_fixture(payload: FixtureIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Arrange one fixture against a club in the generated world, and name the eleven it will be played with."""
    limit(request, 20, 60, scope="club_write")
    try:
        return mat.create_fixture(
            db, user, ident, team=payload.team, opponent=payload.opponent, scheduled_on=payload.scheduled_on, side=payload.side, competition=payload.competition, named=payload.named, note=payload.note
        )
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/fixtures")
def read_fixtures(
    ident: str, request: Request, team: str | None = None, status: str | None = None, since: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)
) -> dict[str, Any]:
    """The tenant's calendar, newest first, with every figure on it counted from the rows this page names."""
    limit(request, 30, 60, scope="club_read")
    try:
        return mat.list_fixtures(db, user, ident, team=team, status=status, since=since)
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/fixtures/{fixture}")
def read_fixture(ident: str, fixture: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """One fixture, and — once played — the engine's own report read back through the match row it points at."""
    limit(request, 30, 60, scope="club_read")
    try:
        return mat.fixture_detail(db, user, ident, fixture)
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/fixtures/{fixture}/play")
def play_one_fixture(payload: FixturePlayIn, ident: str, fixture: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Play one fixture through the simulation engine, and record the eleven that actually played it."""
    limit(request, 10, 60, scope="club_write")
    try:
        return mat.play_fixture(db, user, ident, fixture, seed=payload.seed, minutes=payload.minutes)
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/fixtures/{fixture}")
def erase_fixture(ident: str, fixture: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Delete an arrangement and the record of who played it, leaving the match the engine played standing."""
    limit(request, 10, 60, scope="club_write")
    try:
        return mat.delete_fixture(db, user, ident, fixture)
    except ClubRefusal as error:
        raise _refusal(error) from None


class AnnouncementIn(BaseModel):
    """A notice: its title, its body and the audience it is posted to. No field here could name a person."""

    model_config = ConfigDict(extra="forbid")

    # Bounds above the published caps for §39's own reason: at the cap the schema would answer a long
    # title with a bare field error, while the rulebook prints `announcement_caps` and promises the
    # refusal that carries the `length` and `max` figures a page needs to show why.
    title: str = Field(default="", max_length=ann.TITLE_MAX + 64)
    body: str = Field(default="", max_length=ann.BODY_MAX + 400)
    audience: str = Field(default="members", max_length=32)
    pinned: bool = Field(default=False)


@router.post("/{ident}/announcements")
def post_announcement(payload: AnnouncementIn, ident: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Post one notice to an audience. The tier stores the words and the predicate, never a recipient."""
    limit(request, 20, 60, scope="club_write")
    try:
        return ann.create_announcement(db, user, ident, title=payload.title, body=payload.body, audience=payload.audience, pinned=payload.pinned)
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/announcements")
def read_announcements(ident: str, request: Request, audience: str | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """The tenant's board, newest first, with each notice's readership counted from the roster as it stands."""
    limit(request, 30, 60, scope="club_read")
    try:
        return ann.list_announcements(db, user, ident, audience=audience)
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.get("/{ident}/announcements/{announcement}")
def read_announcement(ident: str, announcement: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """One notice, its readership, and whether this account is among the audience that selects it."""
    limit(request, 30, 60, scope="club_read")
    try:
        return ann.announcement_detail(db, user, ident, announcement)
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.post("/{ident}/announcements/{announcement}/read")
def mark_announcement_read(ident: str, announcement: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Record that the caller has read it. Reading twice is one row, and the answer says which one it was."""
    limit(request, 30, 60, scope="club_write")
    try:
        return ann.mark_announcement_read(db, user, ident, announcement)
    except ClubRefusal as error:
        raise _refusal(error) from None


@router.delete("/{ident}/announcements/{announcement}")
def erase_announcement(ident: str, announcement: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> dict[str, Any]:
    """Erase a notice and the receipts on it; the roster they were counted over is untouched."""
    limit(request, 10, 60, scope="club_write")
    try:
        return ann.delete_announcement(db, user, ident, announcement)
    except ClubRefusal as error:
        raise _refusal(error) from None
