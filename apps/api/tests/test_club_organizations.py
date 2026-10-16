"""M8 §39/§41 — a tenant, its staff and its sheets, tested against the one sentence they exist for.

The sentence is in `access.matrix()`: *a member of one organisation can read and change nothing in another*.
The tests are arranged so that a breach cannot pass, rather than so that each route's happy path gets a case:

* **the isolation loop is table-driven over every door that names a tenant**, and the table is compared against
  the route table itself, so a nineteenth door added later fails an existing test instead of shipping untested.
  Each door is knocked on twice: by a stranger, and by an account that is a real director of a *different*
  tenant — the second is the interesting one, since that account holds genuine memberships somewhere.
* **the status code is part of the rule, not decoration.** A foreign tenant answered 403 would confirm the slug
  exists, so `no_such_organization`/404 is asserted together with the body's vocabulary, and the refusal is
  checked for the tenant's name, its team names and its staff's addresses.
* **the matrix is proved by walking the door**, for all six roles across all twelve permissions: the set a role
  actually opens must equal the set its published row claims.
* **a sheet stores a pointer and a sentence, and no figures** — proved by moving a player's stored row
  underneath a team and asserting both halves: the sheet moved, the membership row did not. A separate test
  asserts the tables' own column sets, so a figure column cannot be added quietly.
* **`users.organization_id` is watched, not trusted**: it is filled by the first membership, ignored by the
  second, cleared by a departure, and a planted privilege in it still answers 404 while `access_problems()`
  names the divergence.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.main import app
from app.models import ClubTeam, ClubTeamMember, Organization, OrganizationMember, RealPlayer, Team, User
from app.services.club import access, answers
from app.services.club import organizations as club
from app.services.club.organizations import (
    MAX_MEMBERS_PER_ORGANIZATION,
    MAX_ORGANIZATIONS_PER_USER,
    MAX_SQUAD_PER_TEAM,
    MAX_TEAMS_PER_ORGANIZATION,
    NAME_MAX,
    NOTE_MAX,
    REFUSALS,
    TEAM_NAME_MAX,
    ClubRefusal,
)
from app.services.world import sync_world, world_ready

CLUB = "/api/v1/club"
CAPABILITIES = f"{CLUB}/capabilities"
PASSWORD = "strong-pass-1234"

#: Every door whose path names somebody's organisation, as (method, path after `/api/v1/club`, body).
#: `test_the_list_of_doors_is_the_route_table_itself` compares this against the app's own routes.
DOORS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("get", "/{ident}", {}),
    ("patch", "/{ident}", {"name": "Renamed By Somebody Else"}),
    ("delete", "/{ident}", {}),
    ("post", "/{ident}/invites", {"email": "somebody@example.test", "role": "coach"}),
    ("post", "/{ident}/accept", {}),
    ("post", "/{ident}/decline", {}),
    ("patch", "/{ident}/members", {"email": "somebody@example.test", "role": "scout"}),
    ("delete", "/{ident}/members/{email}", {}),
    ("post", "/{ident}/teams", {"name": "A Side They Do Not Run"}),
    ("patch", "/{ident}/teams/{team}", {"age_group": "u18"}),
    ("delete", "/{ident}/teams/{team}", {}),
    ("get", "/{ident}/teams/{team}/players", {}),
    ("post", "/{ident}/teams/{team}/players", {"player": "whoever", "note": ""}),
    ("delete", "/{ident}/teams/{team}/players/{player}", {}),
    # §42's tenant meter is a §39 door — it names a tenant and asks its standing — so the walk reaches it here.
    ("get", "/{ident}/entitlements", {}),
    # §39's Matches doors name a tenant exactly the same way, so the walk has to reach them before any
    # fixture id, team name or opponent slug is looked up at all.
    ("post", "/{ident}/fixtures", {"team": "A Side They Do Not Run", "opponent": "whoever", "scheduled_on": "2020-01-01"}),
    ("get", "/{ident}/fixtures", {}),
    ("get", "/{ident}/fixtures/{fixture}", {}),
    # The play door is the one POST in this list that reads a body, and `_at_door` sends one only where the
    # tuple carries it: an empty dict here would reach the route with no body at all, and the framework's own
    # 422 would arrive before `require()` ever saw the tenant — a green walk that proved nothing about isolation.
    ("post", "/{ident}/fixtures/{fixture}/play", {"minutes": 90}),
    ("delete", "/{ident}/fixtures/{fixture}", {}),
    # §39's Communication doors name a tenant the same way, so the walk reaches them before any notice id,
    # audience or author row is looked up: a board that leaked "that notice belongs to another tenant" would
    # leak the tenant, which is exactly the hole §39's first walk closed at the accept door.
    ("post", "/{ident}/announcements", {"title": "A notice they cannot post"}),
    ("get", "/{ident}/announcements", {}),
    ("get", "/{ident}/announcements/{announcement}", {}),
    ("post", "/{ident}/announcements/{announcement}/read", {}),
    ("delete", "/{ident}/announcements/{announcement}", {}),
    # §40's academy doors name a tenant exactly the same way, so the isolation walk has to reach them too.
    # Every id in them belongs to nobody: the tenant is refused before any of them is looked up, which is the
    # whole point — a plan door that leaked "that plan is in another tenant" would leak the tenant.
    ("get", "/academy/{ident}/curricula", {}),
    ("post", "/academy/{ident}/curricula", {"name": "A Block They Cannot Write"}),
    ("patch", "/academy/{ident}/curricula/{curriculum}", {"weekly_minutes": 30}),
    ("delete", "/academy/{ident}/curricula/{curriculum}", {}),
    ("get", "/academy/{ident}/plans", {}),
    ("post", "/academy/{ident}/plans", {"player": "whoever"}),
    # §41's Sessions doors name a tenant the same way, so the walk reaches them from this list too. A stranger is
    # refused before any session id or team name is looked up, which is the only order in which the answer cannot
    # confirm that some other tenant holds the row they asked for.
    ("get", "/academy/{ident}/sessions", {}),
    ("post", "/academy/{ident}/sessions", {"team": "Under 18s", "scheduled_on": "2020-01-01", "duration_min": 60, "rpe": 5, "attendees": ["whoever"]}),
    ("get", "/academy/{ident}/sessions/{session_ident}", {}),
    ("delete", "/academy/{ident}/sessions/{session_ident}", {}),
    ("get", "/academy/{ident}/reports", {}),
    ("post", "/academy/{ident}/reports", {"kind": "squad_load", "window_from": "2020-01-01", "window_to": "2020-12-31"}),
    ("get", "/academy/{ident}/reports/{report_ident}", {}),
    ("delete", "/academy/{ident}/reports/{report_ident}", {}),
    ("get", "/academy/{ident}/plans/{plan}", {}),
    ("patch", "/academy/{ident}/plans/{plan}", {"status": "paused"}),
    ("delete", "/academy/{ident}/plans/{plan}", {}),
    ("post", "/academy/{ident}/plans/{plan}/assessments", {"assessed_on": "2026-01-09", "ratings": {"technique": 60}}),
    ("post", "/academy/{ident}/plans/{plan}/feedback", {"message": "a line for a child they cannot reach"}),
    ("post", "/academy/{ident}/plans/{plan}/evidence", {"clip": "vid_somebody_elses", "t_start": 1, "t_end": 4}),
    ("delete", "/academy/{ident}/plans/{plan}/evidence/{evidence}", {}),
    ("get", "/academy/{ident}/consents", {}),
    ("post", "/academy/{ident}/consents", {"player": "whoever"}),
    ("delete", "/academy/{ident}/consents/{player}", {}),
    ("get", "/academy/{ident}/players/{player}/data", {}),
    ("delete", "/academy/{ident}/players/{player}/data", {}),
)

#: The concrete values those templates are filled with when a door is knocked on. The academy keys are ids
#: shaped like §40's and belonging to nothing, because a door that reached a row would be a different defect
#: than the one this walk is about.
PROBE = {
    "team": "Under 18s",
    "email": "somebody@example.test",
    "player": "whoever",
    "plan": "idp_nobody_s_plan",
    "curriculum": "acu_nobody_s_block",
    "evidence": "pve_nobody_s_citation",
    "session_ident": "ses_nobody_s_session",
    "report_ident": "rep_nobody_s_report",
    # A notice id belonging to nobody, in the shape the tier mints them.
    "announcement": "ann_somebodyelses0",
}


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """A seeded world, and the rows a club tier has to be able to tell apart."""
    session = SessionLocal()
    try:
        sync_world(session)
        players = list(session.scalars(select(RealPlayer).order_by(RealPlayer.slug)).all())
        assert len(players) > MAX_SQUAD_PER_TEAM + 8 and world_ready(session)
        world_club = session.scalars(select(Team).order_by(Team.slug).limit(1)).one()
        minors = [row for row in players if int(row.age) < 18]
        adults = [row for row in players if int(row.age) >= 18]
        assert minors and adults, "a tier that separates minors from adults needs both in the world it reads"
        other = [row.slug for row in players if row.slug not in {minors[0].slug, adults[0].slug}]
        return {
            "players": len(players),
            "world_team_slug": str(world_club.slug),
            "world_team_name": str(world_club.name),
            "minor": minors[0].slug,
            "minor_age": int(minors[0].age),
            "adult": adults[0].slug,
            "adult_age": int(adults[0].age),
            # A third player, for the test that moves a stored row: mutating the two above would make the
            # minors' count elsewhere in this file depend on the order the tests happened to run in.
            "mutable": other[0],
            "sheet": [row.slug for row in players[:MAX_SQUAD_PER_TEAM]],
            "spare": players[MAX_SQUAD_PER_TEAM].slug,
        }
    finally:
        session.close()


@pytest.fixture()
def session(world: dict[str, Any]) -> Iterator[Session]:
    """A session over the seeded world, so a subset run never reads an empty pool."""
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _account(name: str = "Club Manager") -> TestClient:
    """Its own client with its own account — the only way to prove that two members of the platform differ."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"club-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": name, "role": "coach", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _email_of(client: TestClient) -> str:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    return str(response.json()["email"])


def _read_row(model: Any, *conditions: Any) -> Any:
    session = SessionLocal()
    try:
        row = session.scalar(select(model).where(*conditions))
        assert row is not None, f"no {model.__name__} matches {conditions}"
        session.expunge(row)
        return row
    finally:
        session.close()


def _who(client: TestClient) -> User:
    return _read_row(User, User.email == _email_of(client))


def _organization_row(slug: str) -> Organization:
    return _read_row(Organization, Organization.slug == slug)


def _player_row(slug: str) -> dict[str, Any]:
    session = SessionLocal()
    try:
        row = session.scalar(select(RealPlayer).where(RealPlayer.slug == slug))
        assert row is not None, f"{slug} is not in the world"
        return {"age": int(row.age), "overall": int(row.overall), "potential": int(row.potential), "position": str(row.position), "name": str(row.name)}
    finally:
        session.close()


def _set_pointer(email: str, organization_id: str | None) -> None:
    """Write the legacy column directly: the point of watching it is that nothing in this tier writes it."""
    session = SessionLocal()
    try:
        row = session.scalar(select(User).where(User.email == email))
        assert row is not None
        row.organization_id = organization_id
        session.commit()
    finally:
        session.close()


def _problems_for(email: str) -> dict[str, Any]:
    session = SessionLocal()
    try:
        user = session.scalar(select(User).where(User.email == email))
        assert user is not None
        return club.access_problems(session, user)
    finally:
        session.close()


def _opened(client: TestClient, name: str, **body: Any) -> dict[str, Any]:
    response = client.post(CLUB, json={"name": name, **body})
    assert response.status_code == 200, response.text
    return response.json()


def _slug(client: TestClient, name: str, **body: Any) -> str:
    return str(_opened(client, name, **body)["organization"]["slug"])


def _read(client: TestClient, ident: str) -> dict[str, Any]:
    response = client.get(f"{CLUB}/{ident}")
    assert response.status_code == 200, response.text
    return response.json()


def _team(client: TestClient, ident: str, name: str, **body: Any) -> dict[str, Any]:
    response = client.post(f"{CLUB}/{ident}/teams", json={"name": name, **body})
    assert response.status_code == 200, response.text
    return response.json()["team"]


def _add(client: TestClient, ident: str, team: str, slug: str, note: str = "") -> dict[str, Any]:
    response = client.post(f"{CLUB}/{ident}/teams/{team}/players", json={"player": slug, "note": note})
    assert response.status_code == 200, response.text
    return response.json()


def _invite(client: TestClient, ident: str, email: str, role: str) -> dict[str, Any]:
    response = client.post(f"{CLUB}/{ident}/invites", json={"email": email, "role": role})
    assert response.status_code == 200, response.text
    return response.json()


def _joined(owner: TestClient, ident: str, role: str, name: str = "Staff") -> tuple[TestClient, str]:
    """A second account standing *active* in `ident` at `role` — invited, then accepted by the person named."""
    guest = _account(name)
    email = _email_of(guest)
    _invite(owner, ident, email, role)
    response = guest.post(f"{CLUB}/{ident}/accept")
    assert response.status_code == 200, response.text
    return guest, email


def _person(session: Session, tag: str) -> User:
    """A User row without the register route: the staff cap needs dozens and a name is all they carry."""
    existing = session.scalar(select(User).where(User.email == f"club-{tag}@example.test"))
    if existing is not None:
        return existing
    row = User(id=f"usr_{tag}"[:40], email=f"club-{tag}@example.test", display_name=tag, role="coach", password_hash="not-a-login")
    session.add(row)
    session.commit()
    return row


def _stored_membership(team_id: str, player_slug: str) -> ClubTeamMember:
    session = SessionLocal()
    try:
        player = session.scalar(select(RealPlayer).where(RealPlayer.slug == player_slug))
        row = session.scalar(select(ClubTeamMember).where(ClubTeamMember.team_id == team_id, ClubTeamMember.player_id == (player.id if player else "")))
        assert row is not None, f"{player_slug} is not on {team_id} in storage"
        session.expunge(row)
        return row
    finally:
        session.close()


def _club_tables() -> dict[str, int]:
    """Every table this tier can write, counted at once: the shape a 'this read wrote nothing' test needs."""
    session = SessionLocal()
    try:
        return {
            "organizations": int(session.scalar(select(func.count()).select_from(Organization)) or 0),
            "memberships": int(session.scalar(select(func.count()).select_from(OrganizationMember)) or 0),
            "teams": int(session.scalar(select(func.count()).select_from(ClubTeam)) or 0),
            "squad_rows": int(session.scalar(select(func.count()).select_from(ClubTeamMember)) or 0),
        }
    finally:
        session.close()


def _world_tables() -> dict[str, int]:
    session = SessionLocal()
    try:
        return {
            "players": int(session.scalar(select(func.count()).select_from(RealPlayer)) or 0),
            "world_clubs": int(session.scalar(select(func.count()).select_from(Team)) or 0),
            "accounts": int(session.scalar(select(func.count()).select_from(User)) or 0),
        }
    finally:
        session.close()


def _detail(response: Any) -> dict[str, Any]:
    body = response.json()
    assert isinstance(body.get("detail"), dict), body
    return dict(body["detail"])


def _at_door(client: TestClient, method: str, url: str, body: dict[str, Any]) -> Any:
    """Knock on a door with a body only where it takes one.

    `TestClient.get()` has no `json` keyword, so a helper that handed every method the same arguments died
    before it could read the answer it was meant to compare — and the failure looked like a bug in the test
    rather than in the tier. A door in `DOORS` with an empty body is one the route reads nothing from.
    """
    return getattr(client, method)(url, json=body) if body else getattr(client, method)(url)


def _tenant_naming_doors() -> set[tuple[str, str]]:
    """The route table's own answer to 'which doors name a tenant', so `DOORS` cannot quietly fall behind it."""
    doors: set[tuple[str, str]] = set()
    for route in app.routes:
        path = str(getattr(route, "path", ""))
        if not path.startswith(f"{CLUB}/") or "{ident}" not in path:
            continue
        for method in sorted(getattr(route, "methods", set()) or set()):
            if method not in {"HEAD", "OPTIONS"}:
                doors.add((method.lower(), path[len(CLUB) :]))
    return doors


def _sheet(view: dict[str, Any], name: str) -> dict[str, Any]:
    """A team picked out of a tenant read by its name — `teams` is ordered by name, and a test should not care."""
    rows = {team["name"]: team for team in view["teams"]}
    assert name in rows, sorted(rows)
    return rows[name]


class TestOpeningATenant:
    """A tenant is opened by the account that becomes its owner, in the same transaction as the tenant."""

    def test_the_founder_is_told_what_being_the_founder_holds(self) -> None:
        body = _opened(_account(), "Northgate Academy", kind="academy", country="en")
        organization = body["organization"]
        assert organization["slug"] == "northgate-academy" and organization["name"] == "Northgate Academy"
        assert organization["kind"] == "academy" and organization["country"] == "EN"
        assert organization["data_origin"] == "user" and organization["is_demo_data"] is False
        assert body["members"] == 1 and body["teams"] == 0 and body["room_left"] == MAX_MEMBERS_PER_ORGANIZATION - 1
        grant = body["my_grant"]
        assert (grant["role"], grant["status"], grant["active"], grant["known_role"]) == ("owner", "active", True, True)
        assert grant["permissions"] == list(access.PERMISSIONS)
        assert grant["why"] == access.ROLE_MEANING["owner"]

    def test_the_tenant_appears_for_its_member_and_for_nobody_else(self) -> None:
        owner = _account()
        ident = _slug(owner, "Harbour Rovers")
        listing = owner.get(CLUB).json()
        assert listing["total"] == 1 and listing["limit"] == MAX_ORGANIZATIONS_PER_USER and listing["room_left"] == MAX_ORGANIZATIONS_PER_USER - 1
        item = listing["items"][0]
        assert item["slug"] == ident and item["role"] == "owner" and item["status"] == "active"
        assert item["path"] == f"/club/{ident}" and item["active_members"] == 1 and item["teams"] == 0
        assert item["kind"] == "club", "the default kind is what an account gets for not choosing one"
        elsewhere = _account("Stranger").get(CLUB).json()
        assert elsewhere["items"] == [] and elsewhere["total"] == 0 and elsewhere["room_left"] == MAX_ORGANIZATIONS_PER_USER
        assert listing["rule"].startswith("an organisation is listed for an active member"), "the list means standing, not rows that exist"

    def test_a_name_that_would_make_two_rows_is_refused_with_the_slug_that_collided(self) -> None:
        owner = _account()
        _slug(owner, "Valley School", kind="school")
        response = owner.post(CLUB, json={"name": "  Valley School  "})
        assert response.status_code == 422
        detail = _detail(response)
        assert detail["code"] == "name_required" and detail["slug"] == "valley-school" and detail["name"] == "Valley School"

    def test_every_way_a_body_can_be_wrong_is_answered_with_the_figures_behind_it(self) -> None:
        owner = _account()
        cases = [
            ({"name": "   "}, "name_required", {"length": 0, "max": NAME_MAX}),
            ({"name": "x" * (NAME_MAX + 1)}, "name_required", {"length": NAME_MAX + 1, "max": NAME_MAX}),
            ({"name": "Fine One", "kind": "guild"}, "unknown_kind", {"kind": "guild", "kinds": list(club.KINDS)}),
            ({"name": "Fine Two", "visibility_default": "everyone"}, "unknown_visibility", {"visibility_default": "everyone", "allowed": list(club.VISIBILITY_DEFAULTS)}),
            # A three-letter code used to be cut to two letters and stored, so `eng` became `en` — a country
            # nobody chose. The refusal has to arrive from the service with the length it was given, which
            # means the body schema must be wide enough to let it through; hence `max_length=8` on the field.
            ({"name": "Fine Three", "country": "eng"}, "unknown_country", {"country": "eng", "length": 3}),
            ({"name": "Fine Four", "country": "e1"}, "unknown_country", {"country": "e1"}),
            ({"name": "Fine Five", "country": "england"}, "unknown_country", {"country": "england", "length": 7}),
        ]
        for body, code, figures in cases:
            response = owner.post(CLUB, json=body)
            assert response.status_code == 422, f"{body!r} must be refused with 422, the door answered {response.status_code!r}: {response.text!r}"
            detail = _detail(response)
            assert detail["code"] == code, f"{body!r} refused with {detail!r}, code {code!r} was required"
            for key, value in figures.items():
                assert detail[key] == value, f"{body!r} refused with detail[{key!r}]={detail.get(key)!r}, {value!r} was required"
        assert owner.get(CLUB).json()["total"] == 0, "none of the seven bodies above opened anything"

    def test_a_country_is_either_two_letters_or_blank_and_upper_casing_is_the_only_change_made(self) -> None:
        owner = _account()
        lower = _opened(owner, "Lower Case FC", country="gb")
        assert lower["organization"]["country"] == "GB", "stored upper-cased, because the column is read as a code by anything that groups by it"
        blank = _opened(owner, "No Country FC", country="")
        assert blank["organization"]["country"] == ""
        untouched = _opened(owner, "Unasked FC")
        assert untouched["organization"]["country"] == "", "an absent country stays absent rather than becoming a guess"
        ident = lower["organization"]["slug"]
        response = owner.patch(f"{CLUB}/{ident}", json={"country": "ie"})
        assert response.status_code == 200, response.text
        assert response.json()["organization"]["country"] == "IE" and response.json()["changed"] == {"country": "IE"}
        refused = owner.patch(f"{CLUB}/{ident}", json={"country": "ireland"})
        assert refused.status_code == 422, refused.text
        detail = _detail(refused)
        assert detail["code"] == "unknown_country" and detail["country"] == "ireland" and detail["length"] == 7
        assert _read(owner, ident)["organization"]["country"] == "IE", "the refusal wrote nothing"
        assert club.rules()["country"].startswith("two letters")

    def test_the_cap_counts_tenants_opened_and_not_tenants_joined(self) -> None:
        owner = _account()
        for index in range(MAX_ORGANIZATIONS_PER_USER):
            _slug(owner, f"Sidelined Desk {index}", kind="scout_desk")
            assert owner.get(CLUB).json()["room_left"] == MAX_ORGANIZATIONS_PER_USER - index - 1
        response = owner.post(CLUB, json={"name": "One Desk Too Many"})
        assert response.status_code == 422
        detail = _detail(response)
        assert detail["code"] == "organization_limit" and detail["held"] == MAX_ORGANIZATIONS_PER_USER and detail["limit"] == MAX_ORGANIZATIONS_PER_USER
        # Being invited elsewhere is free, so the cap is not a wall around working for two clubs.
        guest = _account("Hired Analyst")
        _invite(owner, "sidelined-desk-0", _email_of(guest), "analyst")
        assert guest.post(f"{CLUB}/sidelined-desk-0/accept").status_code == 200
        assert guest.get(CLUB).json()["total"] == 1 and guest.get(CLUB).json()["room_left"] == MAX_ORGANIZATIONS_PER_USER - 1

    def test_closing_a_tenant_takes_its_staff_and_sheets_and_leaves_the_world_alone(self, world: dict[str, Any]) -> None:
        owner = _account()
        ident = _slug(owner, "Tornown FC")
        team = _team(owner, ident, "Under 16s", age_group="u16")
        _add(owner, ident, team["id"], world["minor"], note="captain")
        _add(owner, ident, team["id"], world["adult"])
        world_before, club_before = _world_tables(), _club_tables()
        player = _player_row(world["minor"])
        response = owner.delete(f"{CLUB}/{ident}")
        assert response.status_code == 200
        body = response.json()
        assert body["deleted"] is True and body["organization"] == ident
        assert body["members_left"] == 1 and body["teams_left"] == 1 and body["players_left_off"] == 2
        assert owner.get(f"{CLUB}/{ident}").status_code == 404 and owner.get(CLUB).json()["total"] == 0
        assert _world_tables() == world_before, "deleting a tenant must not touch the world's rows or anybody's account"
        assert _player_row(world["minor"]) == player, "a player row survives the tenants that listed him, unchanged"
        after = _club_tables()
        assert (after["organizations"], after["teams"], after["squad_rows"]) == (club_before["organizations"] - 1, club_before["teams"] - 1, club_before["squad_rows"] - 2)
        assert body["rule"].startswith("the cascade takes the memberships")


class TestIsolationAcrossTenants:
    """The one sentence, checked at every door that names a tenant."""

    @pytest.mark.parametrize("method,path,body", DOORS, ids=[f"{door[0]}-{door[1]}" for door in DOORS])
    def test_a_member_of_another_tenant_is_answered_exactly_as_a_stranger(self, method: str, path: str, body: dict[str, Any]) -> None:
        """Both callers get 404 `no_such_organization`: the answer must not depend on whether the slug is real."""
        # One tenant name per door, because a slug is global and this run's database is not emptied between
        # tests: fourteen cases naming one tenant would have thirteen refuse for a collision that says
        # nothing about isolation. The owner's name is carried as `hidden` rather than hardcoded below,
        # because the sentence it is testing — that the refusal prints none of it — has to stay true.
        door = re.sub(r"[^a-z0-9]+", "", f"{method}{path}")
        hidden = f"Closedown {door} Academy"
        owner = _account("Owner Of One")
        ident = _slug(owner, hidden, kind="academy")
        _team(owner, ident, PROBE["team"], age_group="u18")
        boss = _account("Owner Of Two")
        unrelated = _slug(boss, f"Unrelated {door} Sports School", kind="school")
        insider, insider_email = _joined(boss, unrelated, "director", "Insider Elsewhere")
        assert insider.get(CLUB).json()["total"] == 1, "the probe account is a real director of a real tenant"
        answers = []
        for caller in (insider, _account("Nobody At All")):
            response = _at_door(caller, method, f"{CLUB}{path.format(ident=ident, **PROBE)}", body)
            assert response.status_code == 404, f"{method!r} {path!r} answered {response.status_code!r}, 404 was required; body: {response.text!r}"
            assert _detail(response)["code"] == "no_such_organization", f"{method!r} {path!r} refused with {_detail(response)!r}, code no_such_organization was required"
            for secret in (hidden, PROBE["team"], _email_of(owner), insider_email):
                assert secret not in response.text, f"{method!r} {path!r} failed: the refusal named {secret!r}"
            answers.append(response.text)
        # The director of another tenant and a total stranger get the same words, so nothing is confirmed either way.
        assert answers[0].replace(_email_of(insider), "X") == answers[1].replace(_email_of(insider), "X")

    @pytest.mark.parametrize("method,path,body", DOORS, ids=[f"{door[0]}-{door[1]}" for door in DOORS])
    def test_a_tenant_addressed_by_its_opaque_id_leaks_nothing_at_any_door(self, method: str, path: str, body: dict[str, Any]) -> None:
        """The same fourteen doors, knocked on by id: an answer built from the resolved row is a way in.

        The test above addresses by slug, which is the address the caller already holds. A tenant is reachable by
        its opaque id as well, and there the refusal is the only thing that can hand back the readable name — so
        every site that raises `no_such_organization` is in scope here, not just the one the read route happens
        to call. Four sites raise it; a probe that walks one of them proves nothing about the other three.
        """
        door = re.sub(r"[^a-z0-9]+", "", f"{method}{path}")
        name = f"Numbered {door} Academy"
        owner = _account("Owner Behind A Number")
        ident = _slug(owner, name, kind="academy")
        _team(owner, ident, PROBE["team"], age_group="u18")
        organization_id = _organization_row(ident).id
        boss = _account("Owner Of A Different Number")
        unrelated = _slug(boss, f"Elsewhere {door} Sports School", kind="school")
        insider, insider_email = _joined(boss, unrelated, "director", "Insider Standing Elsewhere")
        for caller in (insider, _account("Stranger With A Number")):
            response = _at_door(caller, method, f"{CLUB}{path.format(ident=organization_id, **PROBE)}", body)
            assert response.status_code == 404, f"{method!r} {path!r} answered {response.status_code!r}, 404 was required; body: {response.text!r}"
            assert _detail(response)["code"] == "no_such_organization", f"{method!r} {path!r} refused with {_detail(response)!r}, code no_such_organization was required"
            for secret in (ident, name, PROBE["team"], _email_of(owner), insider_email):
                assert secret not in response.text, f"{method!r} {path!r} failed: the refusal named {secret!r}"

    def test_the_list_of_doors_is_the_route_table_itself(self) -> None:
        declared = {(method, path) for method, path, _ in DOORS}
        living = _tenant_naming_doors()
        assert living == declared, sorted(living ^ declared)
        assert (
            len(declared) == 51
        ), "this class is the isolation proof for every door that names a tenant: §39's twenty-four (fourteen of §41's spine, five fixtures and five notices), §40's eighteen academy doors, §41's eight session and report doors and §42's one tenant-meter door, counted from the route table above rather than remembered"

    def test_an_unaccepted_invitation_and_a_revoked_standing_are_both_not_a_foothold(self) -> None:
        owner = _account("Suspender")
        ident = _slug(owner, "Gate House Academy", kind="academy")
        coach, email = _joined(owner, ident, "coach", "Coach Candidate")
        assert coach.get(f"{CLUB}/{ident}").status_code == 200
        assert owner.delete(f"{CLUB}/{ident}/members/{email}").status_code == 200
        revoked = coach.get(f"{CLUB}/{ident}")
        assert revoked.status_code == 404 and _detail(revoked)["code"] == "no_such_organization"
        second = _account("Never Answered")
        _invite(owner, ident, _email_of(second), "director")
        pending = second.get(f"{CLUB}/{ident}")
        assert pending.status_code == 404, "an invitation that is still an invitation is not a way in"
        assert _detail(pending)["code"] == "no_such_organization"
        assert _detail(pending) == _detail(revoked), "'invited and has not answered' must look like 'never invited'"

    def test_the_refusal_names_the_permission_and_the_tenant_and_no_rows(self) -> None:
        owner = _account("Landlord")
        ident = _slug(owner, "Seaside Scholars", kind="school")
        detail = _detail(_account("Passer By").patch(f"{CLUB}/{ident}", json={"name": "Mine Now"}))
        assert set(detail) == {"code", "message", "ident", "permission"}
        assert detail["ident"] == ident and detail["permission"] == "org.rename"

    def test_a_tenant_is_reachable_by_its_id_as_well_as_by_its_slug_for_its_member_only(self) -> None:
        owner = _account("Addressed By Number")
        ident = _slug(owner, "Two Ways In FC")
        organization_id = _organization_row(ident).id
        assert owner.get(f"{CLUB}/{organization_id}").json()["organization"]["slug"] == ident
        stranger = _account("Wrong Address")
        answer = stranger.get(f"{CLUB}/{organization_id}")
        assert answer.status_code == 404
        detail = _detail(answer)
        assert detail["ident"] == organization_id, "the refusal echoes what the caller typed, never what the row resolved to"
        # A tenant addressable by an opaque id is a tenant somebody can enumerate. If the refusal printed the
        # slug it had just looked up, one probe by id would hand back the readable name of a club that never
        # invited the prober — the same confirmation the 404 exists to withhold.
        for secret in (ident, "Two Ways In FC"):
            assert secret not in answer.text, f"the id probe leaked {secret!r}"

    def test_every_tenant_on_the_list_is_one_the_list_can_open(self) -> None:
        """The listing and the read have to agree, or the page shows a card that 404s when clicked."""
        owner = _account("Lister")
        ident = _slug(owner, "Listed Twice FC")
        guest, _ = _joined(owner, ident, "scout", "Listing Scout")
        assert [item["slug"] for item in guest.get(CLUB).json()["items"]] == [ident]
        for item in guest.get(CLUB).json()["items"]:
            assert guest.get(f"{CLUB}/{item['slug']}").status_code == 200
        owner.delete(f"{CLUB}/{ident}/members/{_email_of(guest)}")
        assert guest.get(CLUB).json()["items"] == [], "a revoked standing leaves the list with the rights it held"


class TestStandingAndTheMatrix:
    """Roles are stored data, what they grant is published code, and the two may never disagree."""

    @pytest.fixture()
    def pair(self, session: Session) -> Iterator[tuple[User, User, str]]:
        """A tenant opened by one plain account, and a second account free to stand in it at any role."""
        founder = _person(session, "matrix-founder")
        person = _person(session, "matrix-staff")
        ident = str(club.create_organization(session, founder, name="Matrix House")["organization"]["slug"])
        yield founder, person, ident
        club.delete_organization(session, founder, ident)
        for row in (founder, person):
            session.delete(session.merge(row))
        session.commit()

    @pytest.mark.parametrize("role", list(access.ROLES))
    def test_what_a_role_opens_is_exactly_what_its_published_row_claims(self, session: Session, pair: tuple[User, User, str], role: str) -> None:
        founder, person, ident = pair
        session.add(OrganizationMember(id=f"orgm_{uuid4().hex[:12]}", organization_id=_organization_row(ident).id, user_id=person.id, role=role, status="active"))
        session.commit()
        opened, refused = set(), set()
        for permission in access.PERMISSIONS:
            try:
                club.require(session, person, ident, permission)
            except ClubRefusal as error:
                assert error.code == "insufficient_role", f"role {role!r} asked for {permission!r} and raised {error.code!r}, insufficient_role was required"
                refused.add(permission)
            else:
                opened.add(permission)
        assert opened == set(access.permissions_of(role)), f"role {role!r} is out of step by {sorted(opened ^ set(access.permissions_of(role)))!r}"
        assert opened | refused == set(access.PERMISSIONS) and not opened & refused
        if role != "owner":
            # `org.rename` is not in this list because the published matrix hands it to `director` too, and the
            # assertion above already proved the row is exactly what it claims. `org.delete` is the one door
            # that must never open for a role below the founder — `opened` is computed from `require()`, so
            # this is a statement about the door, not about the table.
            assert "org.delete" in refused, f"{role} was allowed to delete the tenant"
        assert founder is not None

    def test_a_role_nobody_wrote_grants_nothing_and_stays_reported_until_its_row_goes(self, session: Session, pair: tuple[User, User, str]) -> None:
        founder, person, ident = pair
        grant = access.grant("team_boss", "active")
        assert grant["known_role"] is False and grant["active"] is True and grant["permissions"] == []
        assert "not one of the published roles" in grant["why"]
        membership = OrganizationMember(id="orgm_typo", organization_id=_organization_row(ident).id, user_id=person.id, role="team_boss", status="active")
        session.add(membership)
        session.commit()
        with pytest.raises(ClubRefusal) as raised:
            club.require(session, person, ident, "squad.read")
        # The standing is real — an active membership in this tenant — so this is the tier's one honest 403 and
        # not a 404: answering as an absent organisation would tell a person their own row does not exist. What
        # makes the answer useful is `known_role`, the figure that separates "your role holds less than this"
        # from "the string on your row is not a role this API can even set".
        assert raised.value.code == "insufficient_role", "an active member is never answered as a stranger"
        figures = raised.value.to_dict()
        assert figures["known_role"] is False and figures["role"] == "team_boss" and figures["permissions_held"] == []
        assert "not one of the published roles" in figures["why"]
        assert "team_boss" not in access.ROLES, "the point of the case: a role string the routes refuse to store"
        problems = club.access_problems(session, founder)
        assert problems["clean"] is False and any("team_boss" in problem for problem in problems["problems"])
        club.revoke_member(session, founder, ident, email=person.email)
        assert club.access_problems(session, founder)["clean"] is False, "revoking keeps the row, and the row still names a role the matrix does not have"
        session.delete(session.merge(membership))
        session.commit()
        assert club.access_problems(session, founder)["clean"] is True

    def test_a_member_asking_for_more_than_their_role_is_told_which_right_is_missing(self) -> None:
        owner = _account("Director Boss")
        ident = _slug(owner, "Fringe Fields")
        coach, _ = _joined(owner, ident, "coach", "Only A Coach")
        assert coach.get(f"{CLUB}/{ident}").status_code == 200, "a coach reads the tenant they stand in"
        response = coach.post(f"{CLUB}/{ident}/teams", json={"name": "Promotion Side"})
        assert response.status_code == 403, response.text
        detail = _detail(response)
        assert detail["code"] == "insufficient_role" and detail["permission"] == "team.create"
        assert detail["role"] == "coach" and detail["status"] == "active" and detail["known_role"] is True
        assert detail["why"] == access.ROLE_MEANING["coach"], "the answer says what the role is for, in the tier's own words"
        assert detail["organization"] == ident
        assert set(detail["permissions_held"]) == set(access.permissions_of("coach"))
        assert coach.get(f"{CLUB}/{ident}").json()["my_grant"]["role"] == "coach"

    def test_the_matrix_the_routes_publish_is_the_matrix_the_service_uses(self) -> None:
        rules = TestClient(app).get(CAPABILITIES).json()["matrix"]
        assert rules["roles"] == list(access.ROLES) and rules["permissions"] == list(access.PERMISSIONS)
        assert rules["matrix"] == {role: list(access.permissions_of(role)) for role in access.ROLES}
        assert rules["statuses"] == ["active", "invited", "revoked"]
        assert rules["default"].startswith("deny")
        assert rules["stored"] == "role and status on the membership row"
        assert rules["rule"] == "one rule sits under all of it: a member of one organisation can read and change nothing in another"
        assert rules["meaning"]["parent"].startswith("reads and writes only what a granted consent row")
        # The row is short, not empty. Two of its four rights are scoped by a consent row rather than by the
        # tenant — a `parent` who is nobody's guardian holds them and opens nothing — and the other two name no
        # child at all: the age-band curriculum, and the tenant's notice board, which is addressed to an
        # audience and never to a person.
        assert set(rules["matrix"]["parent"]) == {"curriculum.read", "plan.read_own_child", "consent.grant_own", "announce.read"}
        assert set(rules["matrix"]["parent"]) & set(access.SCOPED_PERMISSIONS) == {"plan.read_own_child", "consent.grant_own"}
        assert "curriculum.read" not in access.SCOPED_PERMISSIONS
        assert all(set(row) <= set(access.PERMISSIONS) for row in rules["matrix"].values())

    def test_a_permission_nobody_holds_would_be_caught_because_the_matrix_covers_its_own_vocabulary(self) -> None:
        held: set[str] = set()
        for role in access.ROLES:
            held |= set(access.permissions_of(role))
        assert held == set(access.PERMISSIONS), sorted(set(access.PERMISSIONS) - held)
        assert access.may("owner", "plan.write") and not access.may("parent", "squad.read")
        assert access.may("scout", "squad.read") and not access.may("scout", "squad.write")
        assert access.permissions_of("OWNER") == access.permissions_of("owner") and access.permissions_of(" owner ") == access.permissions_of("owner")
        assert access.permissions_of("") == ()

    def test_the_refusal_sets_are_closed_and_every_code_has_exactly_one_http_answer(self) -> None:
        from app.api.v1.club import _ANSWERS

        groups = [club.NOT_FOUND_CODES, club.UNPROCESSABLE_CODES, club.CONFLICT_CODES, club.FORBIDDEN_CODES]
        assert set(REFUSALS) == set().union(*groups), "a refusal the route table cannot place would answer 400"
        assert len(REFUSALS) == len(set(REFUSALS)) == sum(len(group) for group in groups)
        for index, first in enumerate(groups):
            for second in groups[index + 1 :]:
                assert not first & second, first & second
        assert club.FORBIDDEN_CODES == frozenset({"insufficient_role"}), "403 is only ever a member over-reaching"
        # `#51` moved the answer table out of this router and into `services/club/answers.py`, where every part of
        # the tier registers its codes — so this door answers §40's, §41's and §42's codes too, and equality with
        # §39's own list would now be false rather than protective. What stays true, and what this asserts: every
        # code this tier can refuse with has an answer here, and the table is the shared object rather than a copy.
        assert _ANSWERS is answers.ANSWERS, "this door assembled its own answer table again"
        assert set(REFUSALS) <= set(_ANSWERS), f"these refusal codes have no entry in the answer table: {sorted(set(REFUSALS) - set(_ANSWERS))!r}"

        assert all(_ANSWERS[code] == 404 for code in club.NOT_FOUND_CODES)
        assert all(_ANSWERS[code] == 422 for code in club.UNPROCESSABLE_CODES)
        assert all(_ANSWERS[code] == 409 for code in club.CONFLICT_CODES)
        assert _ANSWERS["insufficient_role"] == 403
        published = TestClient(app).get(CAPABILITIES).json()["refusal_answers"]
        assert published == {code: _ANSWERS[code] for code in REFUSALS}


class TestStaffing:
    """An invitation is a row that waits, a role change is the only lever, and one owner cannot be stranded."""

    def test_an_invitation_grants_nothing_until_the_person_it_names_says_yes(self) -> None:
        owner = _account("Inviter")
        ident = _slug(owner, "Beechwood Institute", kind="academy")
        guest = _account("Invited Coach")
        email = _email_of(guest)
        invited = _invite(owner, ident, email, "coach")
        assert invited["member"]["status"] == "invited" and invited["member"]["role"] == "coach"
        assert invited["member"]["permissions"] == [] and invited["member"]["active"] is False
        assert "no mail transport" in invited["no_mail_sent"]
        assert invited["members"] == 2 and invited["room_left"] == MAX_MEMBERS_PER_ORGANIZATION - 2
        assert guest.get(CLUB).json()["total"] == 0, "an unaccepted invitation is not a tenant on the member's list"
        mine = guest.get(f"{CLUB}/invitations").json()
        assert mine["total"] == 1 and mine["items"][0]["organization"] == ident and mine["items"][0]["role"] == "coach"
        assert mine["items"][0]["membership"] == invited["member"]["id"]
        taken = guest.post(f"{CLUB}/{ident}/accept").json()
        assert taken["accepted"] is True and taken["my_grant"]["status"] == "active"
        assert set(taken["my_grant"]["permissions"]) == set(access.permissions_of("coach"))
        assert guest.get(f"{CLUB}/invitations").json()["total"] == 0 and guest.get(CLUB).json()["total"] == 1

    def test_an_invitation_is_refused_before_it_names_a_person_or_a_role_that_cannot_be_filled(self) -> None:
        owner = _account("Paperwork")
        ident = _slug(owner, "Ledger Lane")
        missing = owner.post(f"{CLUB}/{ident}/invites", json={"email": "ghost@example.test", "role": "coach"})
        assert missing.status_code == 404 and _detail(missing)["code"] == "no_such_user"
        assert "does not create one" in _detail(missing)["message"]
        bogus = owner.post(f"{CLUB}/{ident}/invites", json={"email": "ghost@example.test", "role": "vice-president"})
        assert bogus.status_code == 422 and _detail(bogus)["code"] == "unknown_role" and _detail(bogus)["roles"] == list(access.ROLES)
        guest, email = _joined(owner, ident, "analyst", "On The Books")
        twice = owner.post(f"{CLUB}/{ident}/invites", json={"email": email, "role": "analyst"})
        assert twice.status_code == 409 and _detail(twice)["code"] == "already_a_member" and _detail(twice)["email"] == email
        assert owner.post(f"{CLUB}/{ident}/invites", json={"email": email.upper(), "role": "scout"}).status_code == 409, "an address is matched without its case"
        assert guest.get(f"{CLUB}/invitations").json()["total"] == 0

    def test_the_two_ways_an_invitation_ends_are_told_apart_from_the_way_it_never_began(self) -> None:
        owner = _account("Careful Boss")
        ident = _slug(owner, "Two Roads FC")
        declining = _account("Declining")
        _invite(owner, ident, _email_of(declining), "scout")
        gone = declining.post(f"{CLUB}/{ident}/decline")
        assert gone.status_code == 200 and gone.json()["declined"] is True
        assert "deleted rather than revoked" in gone.json()["rule"]
        assert declining.get(f"{CLUB}/invitations").json()["total"] == 0
        again = declining.post(f"{CLUB}/{ident}/decline")
        assert again.status_code == 404 and _detail(again)["code"] == "no_such_organization", "a second decline is a stranger asking, and reads like one"
        coach, email = _joined(owner, ident, "coach", "Already Here")
        assert owner.delete(f"{CLUB}/{ident}/members/{email}").status_code == 200
        nothing = coach.post(f"{CLUB}/{ident}/decline")
        assert nothing.status_code == 404 and _detail(nothing)["code"] == "no_such_member", "this caller holds a standing, so the tenant is not absent"
        assert _detail(nothing)["status"] == "revoked"
        refused = coach.post(f"{CLUB}/{ident}/accept")
        assert refused.status_code == 409 and _detail(refused)["code"] == "already_a_member"

    def test_changing_a_role_changes_the_rights_without_touching_who_the_person_is(self) -> None:
        owner = _account("Promoter")
        ident = _slug(owner, "Stepford Athletic")
        guest, email = _joined(owner, ident, "scout", "Watchman")
        assert guest.post(f"{CLUB}/{ident}/accept").status_code == 409, "taking up a standing you already hold is not a thing to do"
        assert guest.post(f"{CLUB}/{ident}/invites", json={"email": "new@example.test", "role": "scout"}).status_code == 403
        response = owner.patch(f"{CLUB}/{ident}/members", json={"email": email, "role": "director"})
        assert response.status_code == 200
        member = response.json()["member"]
        assert member["role"] == "director" and member["status"] == "active" and member["email"] == email
        assert member["display_name"] == "Watchman" and member["account_role"] == "coach"
        assert set(member["permissions"]) == set(access.permissions_of("director"))
        assert "org.delete" not in member["permissions"] and "org.rename" in member["permissions"]
        assert response.json()["rule"].startswith("the role is what changes")
        assert guest.post(f"{CLUB}/{ident}/teams", json={"name": "Director's Side"}).status_code == 200, "the right moved with the title on the request after it"
        assert guest.delete(f"{CLUB}/{ident}").status_code == 403
        unknown = owner.patch(f"{CLUB}/{ident}/members", json={"email": email, "role": "advisor"})
        assert unknown.status_code == 422 and _detail(unknown)["code"] == "unknown_role"
        absent = owner.patch(f"{CLUB}/{ident}/members", json={"email": "who@example.test", "role": "coach"})
        assert absent.status_code == 404 and _detail(absent)["code"] == "no_such_member"

    def test_a_departure_keeps_its_row_loses_its_rights_and_gives_its_seat_back(self) -> None:
        owner = _account("Revoker")
        ident = _slug(owner, "Marlowe Cellar")
        guest, email = _joined(owner, ident, "analyst", "Leaving")
        assert _who(guest).organization_id == _organization_row(ident).id
        response = owner.delete(f"{CLUB}/{ident}/members/{email}")
        assert response.status_code == 200
        member = response.json()["member"]
        assert member["status"] == "revoked" and member["permissions"] == [] and member["active"] is False
        assert member["invited_by"] == _who(owner).id
        assert response.json()["rule"].startswith("the row is kept and marked revoked")
        assert "gives its seat back" in response.json()["seat_freed"]
        assert _who(guest).organization_id is None, "a departure must not leave the legacy pointer naming the tenant they left"
        listed = _read(owner, ident)["members"]
        assert [row["email"] for row in listed if row["status"] == "revoked"] == [email], "who stood where stays answerable after they leave"
        counts = _read(owner, ident)["counts"]
        assert counts["active_members"] == 1 and counts["invited_members"] == 0 and counts["owners"] == 1
        assert counts["member_limit"] == MAX_MEMBERS_PER_ORGANIZATION and counts["team_limit"] == MAX_TEAMS_PER_ORGANIZATION
        again = owner.delete(f"{CLUB}/{ident}/members/{email}")
        assert again.status_code == 404 and _detail(again)["code"] == "no_such_member"

    def test_the_last_owner_cannot_be_stranded_and_a_second_one_frees_the_door(self) -> None:
        owner = _account("Sole Owner")
        ident = _slug(owner, "Single Chair FC")
        my_email = _email_of(owner)
        demote = owner.patch(f"{CLUB}/{ident}/members", json={"email": my_email, "role": "coach"})
        assert demote.status_code == 409 and _detail(demote)["code"] == "last_owner" and _detail(demote)["owners"] == 1
        revoke = owner.delete(f"{CLUB}/{ident}/members/{my_email}")
        assert revoke.status_code == 409 and _detail(revoke)["code"] == "last_owner"
        assert _read(owner, ident)["counts"]["owners"] == 1
        second, _ = _joined(owner, ident, "owner", "Co Owner")
        assert _read(owner, ident)["counts"]["owners"] == 2
        assert owner.patch(f"{CLUB}/{ident}/members", json={"email": my_email, "role": "director"}).status_code == 200
        assert _read(second, ident)["counts"]["owners"] == 1
        assert owner.delete(f"{CLUB}/{ident}").status_code == 403, "a director cannot delete the tenant they handed ownership of"
        assert second.delete(f"{CLUB}/{ident}").status_code == 200

    def test_the_staff_cap_counts_who_stands_here_now_and_frees_the_seat_when_somebody_leaves(self, session: Session) -> None:
        owner = _person(session, "cap-owner")
        ident = str(club.create_organization(session, owner, name="Full House FC")["organization"]["slug"])
        organization = _organization_row(ident)
        crowd = [_person(session, f"cap-staff-{index}") for index in range(MAX_MEMBERS_PER_ORGANIZATION - 1)]
        for person in crowd:
            club.invite_member(session, owner, ident, email=person.email, role="scout")
        assert club.membership_of(session, organization, owner) is not None
        spare = _person(session, "cap-staff-spare")
        with pytest.raises(ClubRefusal) as raised:
            club.invite_member(session, owner, ident, email=spare.email, role="scout")
        assert raised.value.code == "member_limit"
        assert raised.value.figures == {"held": MAX_MEMBERS_PER_ORGANIZATION, "limit": MAX_MEMBERS_PER_ORGANIZATION}
        departed = club.membership_of(session, organization, crowd[0])
        assert departed is not None
        club.revoke_member(session, owner, ident, email=crowd[0].email)
        let_in = club.invite_member(session, owner, ident, email=spare.email, role="scout")
        assert let_in["members"] == MAX_MEMBERS_PER_ORGANIZATION
        assert _read_row(OrganizationMember, OrganizationMember.id == departed.id).status == "revoked"
        with pytest.raises(ClubRefusal) as full_again:
            club.invite_member(session, owner, ident, email=_person(session, "cap-staff-second-spare").email, role="scout")
        assert full_again.value.figures["held"] == MAX_MEMBERS_PER_ORGANIZATION, "the record stays and the seat moves: the cap counts standing, not history"
        club.delete_organization(session, owner, ident)
        for person in [*crowd, spare, _person(session, "cap-staff-second-spare"), owner]:
            session.delete(session.merge(person))
        session.commit()


class TestTeamsAndSheets:
    """A team belongs to one tenant; a sheet is a pointer plus a sentence, and every figure is read live."""

    def test_a_team_is_named_inside_its_tenant_and_can_be_placed_against_the_world(self, world: dict[str, Any]) -> None:
        owner = _account("Builder")
        ident = _slug(owner, "Kestrel Sports School", kind="school")
        team = _team(owner, ident, " Under 15s ", age_group="u15", stage="academy", world_team=world["world_team_slug"])
        assert team["name"] == "Under 15s", "the name is stored stripped, so two staff cannot make two sheets that read the same"
        assert team["age_group"] == "u15" and team["stage"] == "academy"
        assert team["world_team"]["slug"] == world["world_team_slug"] and team["world_team"]["name"] == world["world_team_name"]
        assert team["world_team"]["path"] == f"/team/{world['world_team_slug']}"
        assert team["squad"] == [] and team["squad_size"] == 0 and team["minors_on_sheet"] == 0 and team["room_left"] == MAX_SQUAD_PER_TEAM
        assert team["figures_from"].startswith("`real_players` read on this request")
        renamed = owner.patch(f"{CLUB}/{ident}/teams/{team['id']}", json={"name": "Under 15 (Blue)", "age_group": "u15b"})
        assert renamed.status_code == 200
        body = renamed.json()
        assert body["team"]["name"] == "Under 15 (Blue)" and body["team"]["age_group"] == "u15b"
        assert body["changed"] == {"name": "Under 15 (Blue)", "age_group": "u15b"}
        assert body["rule"].startswith("age_group is what the reporting tier reads")
        # `rules()["addressing"]` promises a team is found by id *or by name* inside its own tenant, and the
        # name keeps its space and parentheses on purpose: a page builds this URL from a squad heading.
        by_name = owner.get(f"{CLUB}/{ident}/teams/Under 15 (Blue)/players")
        assert by_name.status_code == 200, by_name.text
        assert by_name.json()["id"] == team["id"] and by_name.json()["name"] == "Under 15 (Blue)"
        assert by_name.json() == owner.get(f"{CLUB}/{ident}/teams/{team['id']}/players").json(), "two addresses, one sheet"
        assert _sheet(_read(owner, ident), "Under 15 (Blue)")["stage"] == "academy"
        assert _team(owner, ident, "Second Side")["world_team"] is None, "a team with no place in the ladder says so rather than inventing one"

    def test_a_team_that_cannot_be_named_is_refused_with_the_length_it_was_given(self) -> None:
        owner = _account("Naming")
        ident = _slug(owner, "Nameless Row")
        cases = [
            ({"name": "  "}, 422, "name_required", {"length": 0, "max": TEAM_NAME_MAX}),
            ({"name": "t" * (TEAM_NAME_MAX + 1)}, 422, "name_required", {"length": TEAM_NAME_MAX + 1, "max": TEAM_NAME_MAX}),
            ({"name": "Ghost Side", "world_team": "fc-does-not-exist"}, 404, "no_such_world_club", {"world_team": "fc-does-not-exist"}),
        ]
        for body, expected, code, figures in cases:
            response = owner.post(f"{CLUB}/{ident}/teams", json=body)
            assert response.status_code == expected, f"{body!r} answered {response.status_code!r}, {expected!r} was required; body: {response.text!r}"
            detail = _detail(response)
            assert detail["code"] == code, f"{body!r} refused with {detail!r}, code {code!r} was required"
            for key, value in figures.items():
                assert detail[key] == value, f"{body!r} refused with detail[{key!r}]={detail.get(key)!r}, {value!r} was required"
        _team(owner, ident, "First Side")
        twice = owner.post(f"{CLUB}/{ident}/teams", json={"name": "first side"})
        assert twice.status_code == 409 and _detail(twice)["code"] == "team_name_taken" and _detail(twice)["name"] == "first side"
        missing = owner.patch(f"{CLUB}/{ident}/teams/No Such Side", json={"stage": "reserve"})
        assert missing.status_code == 404 and _detail(missing)["code"] == "no_such_team"
        assert _detail(missing)["organization"] == ident
        assert owner.delete(f"{CLUB}/{ident}/teams/First Side").json()["players_left_off"] == 0
        assert owner.get(CLUB).json()["items"][0]["teams"] == 0

    def test_the_team_cap_is_counted_inside_the_tenant_that_asked(self) -> None:
        owner = _account("Overbuilder")
        ident = _slug(owner, "Twelve Sides FC")
        for index in range(MAX_TEAMS_PER_ORGANIZATION):
            _team(owner, ident, f"Side {index}")
        response = owner.post(f"{CLUB}/{ident}/teams", json={"name": "Side Thirteen"})
        assert response.status_code == 422
        detail = _detail(response)
        assert detail["code"] == "team_limit" and detail["held"] == MAX_TEAMS_PER_ORGANIZATION and detail["limit"] == MAX_TEAMS_PER_ORGANIZATION
        assert _read(owner, ident)["counts"]["teams"] == MAX_TEAMS_PER_ORGANIZATION
        other = _slug(owner, "A Second Tenant")
        assert owner.post(f"{CLUB}/{other}/teams", json={"name": "Side Thirteen"}).status_code == 200, "the cap is per tenant, not per account"

    def test_a_sheet_stores_a_pointer_and_a_sentence_and_nothing_that_can_go_stale(self, world: dict[str, Any]) -> None:
        owner = _account("Head Of Academy")
        ident = _slug(owner, "Rowan Valley Academy", kind="academy")
        team = _team(owner, ident, "Under 17s", age_group="u17")
        added = _add(owner, ident, team["id"], world["mutable"], note="left foot only")
        assert added["stored"] == {"team_id": team["id"], "player_id": added["stored"]["player_id"], "note": "left foot only"}
        assert "age, overall, potential" in added["not_stored"]
        row = _player_row(world["mutable"])
        sheet = added["team"]["squad"][0]
        assert (sheet["age"], sheet["overall"], sheet["position"], sheet["name"]) == (row["age"], row["overall"], row["position"], row["name"])
        assert sheet["slug"] == world["mutable"] and sheet["path"] == f"/player/{world['mutable']}"
        assert sheet["is_minor"] is (row["age"] < 18) and sheet["note"] == "left foot only"
        session = SessionLocal()
        try:
            player = session.scalar(select(RealPlayer).where(RealPlayer.slug == world["mutable"]))
            assert player is not None
            player.overall, player.age = row["overall"] + 7, 30
            session.commit()
        finally:
            session.close()
        try:
            moved = _sheet(_read(owner, ident), "Under 17s")
            assert moved["squad"][0]["overall"] == row["overall"] + 7, "the figure on the sheet is the world's, taken now"
            assert moved["squad"][0]["is_minor"] is False and moved["minors_on_sheet"] == 0
            stored = _stored_membership(team["id"], world["mutable"])
            assert stored.note == "left foot only", "the coach's sentence is the only thing this tier wrote about him"
            assert owner.get(f"{CLUB}/{ident}/teams/{team['id']}/players").json()["squad_size"] == 1
        finally:
            session = SessionLocal()
            try:
                player = session.scalar(select(RealPlayer).where(RealPlayer.slug == world["mutable"]))
                assert player is not None
                player.overall, player.age = row["overall"], row["age"]
                session.commit()
            finally:
                session.close()
        assert _sheet(_read(owner, ident), "Under 17s")["squad"][0]["overall"] == row["overall"], "and putting the row back moves the sheet back"

    def test_the_tables_themselves_hold_no_figure_for_a_test_to_have_to_notice(self) -> None:
        assert {column.name for column in ClubTeamMember.__table__.columns} == {"id", "team_id", "player_id", "note", "data_origin", "is_demo_data", "created_at", "updated_at"}
        team_columns = {column.name for column in ClubTeam.__table__.columns}
        assert {"id", "organization_id", "name", "age_group", "stage", "world_team_id"} <= team_columns
        assert not team_columns & {"overall", "age", "wins", "points", "goals_for", "budget"}, "a team row that carried a figure could disagree with the world"

    def test_a_player_is_put_on_a_sheet_once_and_off_it_by_name(self, world: dict[str, Any]) -> None:
        owner = _account("Registrar")
        ident = _slug(owner, "Duplicate Door FC")
        team = _team(owner, ident, "Reserve Side")
        player_before = _player_row(world["adult"])
        _add(owner, ident, team["id"], world["adult"])
        twice = owner.post(f"{CLUB}/{ident}/teams/{team['id']}/players", json={"player": world["adult"], "note": ""})
        assert twice.status_code == 409 and _detail(twice)["code"] == "already_on_team" and _detail(twice)["team"] == "Reserve Side"
        nobody = owner.post(f"{CLUB}/{ident}/teams/{team['id']}/players", json={"player": "not-a-person", "note": ""})
        assert nobody.status_code == 404 and _detail(nobody)["code"] == "no_such_player" and _detail(nobody)["ident"] == "not-a-person"
        verbose = owner.post(f"{CLUB}/{ident}/teams/{team['id']}/players", json={"player": world["mutable"], "note": "n" * (NOTE_MAX + 1)})
        assert verbose.status_code == 422, verbose.text
        detail = _detail(verbose)
        assert detail["code"] == "name_required" and detail["length"] == NOTE_MAX + 1 and detail["max"] == NOTE_MAX, "the service answers a long note, so the figures travel with the refusal"
        dropped = owner.delete(f"{CLUB}/{ident}/teams/{team['id']}/players/{world['adult']}")
        assert dropped.status_code == 200 and dropped.json()["removed"] == world["adult"] and dropped.json()["team"]["squad_size"] == 0
        assert dropped.json()["rule"].startswith("the sheet loses a pointer")
        gone = owner.delete(f"{CLUB}/{ident}/teams/{team['id']}/players/{world['adult']}")
        assert gone.status_code == 404 and _detail(gone)["code"] == "no_such_player"
        assert _player_row(world["adult"]) == player_before, "putting a player on a sheet and taking him off leaves his own row exactly as it was"
        assert _read(owner, ident)["counts"]["players_on_sheets"] == 0

    def test_the_sheet_cap_fires_on_the_side_that_is_full_and_not_on_the_ones_that_are_not(self, world: dict[str, Any]) -> None:
        owner = _account("Selector")
        ident = _slug(owner, "Forty Places FC")
        full = _team(owner, ident, "Full Sheet")
        empty = _team(owner, ident, "Empty Sheet")
        for slug in world["sheet"]:
            _add(owner, ident, full["id"], slug)
        view = _read(owner, ident)
        assert _sheet(view, "Full Sheet")["room_left"] == 0 and _sheet(view, "Empty Sheet")["room_left"] == MAX_SQUAD_PER_TEAM
        assert view["counts"]["players_on_sheets"] == MAX_SQUAD_PER_TEAM
        response = owner.post(f"{CLUB}/{ident}/teams/{full['id']}/players", json={"player": world["spare"], "note": ""})
        assert response.status_code == 422, response.text
        detail = _detail(response)
        assert detail["code"] == "squad_full" and detail["held"] == MAX_SQUAD_PER_TEAM and detail["limit"] == MAX_SQUAD_PER_TEAM
        assert (
            owner.post(f"{CLUB}/{ident}/teams/{empty['id']}/players", json={"player": world["spare"], "note": ""}).status_code == 200
        ), "the cap is per sheet, and one player may stand for two of them"
        assert _sheet(_read(owner, ident), "Empty Sheet")["squad_size"] == 1

    def test_minors_are_counted_from_the_rows_and_not_from_the_team_name(self, world: dict[str, Any]) -> None:
        owner = _account("Welfare Officer")
        ident = _slug(owner, "Small Legs Academy", kind="academy")
        team = _team(owner, ident, "First Team", age_group="open")
        _add(owner, ident, team["id"], world["minor"])
        _add(owner, ident, team["id"], world["adult"])
        sheet = _sheet(_read(owner, ident), "First Team")
        assert sheet["age_group"] == "open" and sheet["squad_size"] == 2 and sheet["minors_on_sheet"] == 1
        printed = {row["slug"]: row["is_minor"] for row in sheet["squad"]}
        assert printed == {world["minor"]: world["minor_age"] < 18, world["adult"]: world["adult_age"] < 18}
        renamed = owner.patch(f"{CLUB}/{ident}/teams/{team['id']}", json={"name": "Under 21s", "age_group": "u21"}).json()
        assert renamed["team"]["minors_on_sheet"] == 1, "renaming a band does not change who is on it"

    def test_reading_a_tenant_writes_nothing(self, world: dict[str, Any]) -> None:
        owner = _account("Reader")
        ident = _slug(owner, "Look But Do Not Touch")
        team = _team(owner, ident, "Quiet Side")
        _add(owner, ident, team["id"], world["adult"], note="captain")
        before = _club_tables()
        for _ in range(3):
            assert owner.get(f"{CLUB}/{ident}").status_code == 200
            assert owner.get(f"{CLUB}/{ident}/teams/{team['id']}/players").status_code == 200
            assert owner.get(CLUB).status_code == 200
            assert owner.get(f"{CLUB}/invitations").status_code == 200
            assert owner.get(CAPABILITIES).status_code == 200
        assert _club_tables() == before, "a read that added a row would make the tenant's own counts lie"


class TestTheOldColumnIsWatchedNotTrusted:
    """`users.organization_id` predates tenants, and must never be the thing that lets somebody in."""

    def test_the_first_membership_fills_it_and_a_second_tenant_leaves_it_alone(self) -> None:
        owner = _account("First Job")
        first = _slug(owner, "Colliery Row FC")
        assert _who(owner).organization_id == _organization_row(first).id
        boss = _account("Second Employer")
        second = _slug(boss, "Quarry Lane Institute", kind="academy")
        guest, email = _joined(boss, second, "coach", "Two Jobs")
        assert _who(guest).organization_id == _organization_row(second).id, "an account that opened nothing is filled by the first tenant it joins"
        third = _slug(boss, "Ash Field Club")
        _invite(boss, third, email, "analyst")
        assert guest.post(f"{CLUB}/{third}/accept").status_code == 200
        assert _who(guest).organization_id == _organization_row(second).id, "the legacy column holds one tenant, so the second does not overwrite the first"
        assert guest.get(CLUB).json()["total"] == 2, "membership rows are the truth, and they carry both"
        assert _problems_for(email)["clean"] is True
        assert boss.delete(f"{CLUB}/{second}").status_code == 200 and boss.delete(f"{CLUB}/{third}").status_code == 200

    def test_a_planted_pointer_grants_nothing_and_is_reported_as_a_divergence(self) -> None:
        owner = _account("Planted Column")
        ident = _slug(owner, "Granta Bridge Academy", kind="academy")
        guest = _account("Guest Star")
        email = _email_of(guest)
        _invite(owner, ident, email, "director")
        _set_pointer(email, _organization_row(ident).id)
        denied = guest.get(f"{CLUB}/{ident}")
        assert denied.status_code == 404 and _detail(denied)["code"] == "no_such_organization", "a tenant pointer is not a membership"
        problems = _problems_for(email)
        assert problems["clean"] is False
        assert any(ident in problem and "not an active member" in problem for problem in problems["problems"]), problems
        assert guest.post(f"{CLUB}/{ident}/accept").status_code == 200
        assert _problems_for(email)["clean"] is True
        assert guest.get(f"{CLUB}/{ident}").status_code == 200

    def test_deleting_a_tenant_leaves_no_account_pointing_at_it(self) -> None:
        owner = _account("Leaving Landlord")
        email = _email_of(owner)
        ident = _slug(owner, "Rent Paid FC")
        assert _who(owner).organization_id == _organization_row(ident).id
        assert owner.delete(f"{CLUB}/{ident}").status_code == 200
        assert _who(owner).organization_id is None, "the pointer is cleared, not left naming a tenant that has gone"
        assert _problems_for(email)["clean"] is True


class TestPublishedSelfDescription:
    """The tier publishes its own rulebook, its own counts, and what it deliberately does not do."""

    def test_the_capabilities_page_is_public_and_answers_the_question_b2b_needs(self) -> None:
        anonymous = TestClient(app).get(CAPABILITIES)
        assert anonymous.status_code == 200, "who can see what is readable before anybody signs in"
        published = anonymous.json()
        assert published["kinds"] == list(club.KINDS)
        assert published["visibility_defaults"] == list(club.VISIBILITY_DEFAULTS)
        assert published["max_organizations_per_user"] == MAX_ORGANIZATIONS_PER_USER
        assert published["max_members_per_organization"] == MAX_MEMBERS_PER_ORGANIZATION
        assert published["max_teams_per_organization"] == MAX_TEAMS_PER_ORGANIZATION
        assert published["max_squad_per_team"] == MAX_SQUAD_PER_TEAM
        assert (published["name_max"], published["team_name_max"], published["note_max"]) == (NAME_MAX, TEAM_NAME_MAX, NOTE_MAX)
        assert published["refusals"] == list(REFUSALS)
        assert set(published["refusal_answers"]) == set(REFUSALS)
        assert published["data_origin"] == "project-authored" and published["is_demo_data"] is False
        assert published["ready_rule"] == club.READY_RULE, "the flag's rule is a published constant, so the page prints this sentence and not one written at the route"
        assert "at least one" in club.READY_RULE, "the rule says what turns the flag true, which is the question a fresh deployment asks"
        assert all(isinstance(limitation, str) and len(limitation) > 40 for limitation in published["limitations"])
        assert all(len(line["purpose"]) > 20 for line in published["routes"]), "a door guide a page prints has to say what the door is for"

    def test_every_door_the_page_is_handed_is_a_door_and_every_door_is_handed_to_the_page(self) -> None:
        """Both directions at once: a published door that does not exist is a broken link, an unlisted one is lost.

        The tier used to publish its doors as prose, and the prose named a `GET /club/{ident}/teams` that was
        never routed. No reading of that sentence could have caught it. As one line per door with its own
        methods, the route table answers.
        """
        published = TestClient(app).get(CAPABILITIES).json()["routes"]
        living: set[tuple[str, str]] = set()
        for route in app.routes:
            path = str(getattr(route, "path", ""))
            if not path.startswith(CLUB):
                continue
            for method in sorted(getattr(route, "methods", set()) or set()):
                if method not in {"HEAD", "OPTIONS"}:
                    living.add((path, method))
        claims = {(line["path"], method) for line in published for method in line["methods"]}
        assert claims <= living, sorted(claims - living)
        assert living <= claims, sorted(living - claims)
        assert len(published) == len({line["path"] for line in published}), "one line per door, or the guide double-books a path"
        assert _tenant_naming_doors() == {(method.lower(), path[len(CLUB) :]) for path, method in living if "{ident}" in path}, "the isolation loop still covers everything this list holds"

    def test_the_rulebook_names_the_two_things_this_tier_deliberately_does_not_have(self) -> None:
        limitations = club.limitations()
        joined = " ".join(limitations)
        assert any(
            "a club fixture is arranged against a club in the generated world" in text for text in limitations
        ), "Matches has landed, so the rulebook has to say what a fixture is played against and where its figures live"
        assert "no match report or message exists in this tier" not in joined, "§39's Matches row exists now, and the sentence that called it missing would be a lie the tenant page prints"
        # §41 landed `club_sessions` and `club_reports`, so the sentence that called a training session missing
        # became false while the tier it describes was being written — and the tenant page prints this list.
        assert "training session or message" not in joined, "a training session exists at /club/academy/{ident}/sessions; the rulebook may not still call it missing"
        assert any("sessions and saved reports are separate services" in text for text in limitations), "the sentence has to say where they went, not just that §39 lacks them"
        assert any("/club/academy" in text for text in limitations), "the sentence has to say where the plans did go, not just that §39 lacks them"
        assert any("not a message" in text for text in limitations), "an invitation that is not an email is stated, not implied"
        assert any("parent" in text and "scoped by a consent row" in text for text in limitations), "a parent's rights are half scoped, and the rulebook says so"
        # §57 gave `parent` a fourth right, and the sentence the tenant page prints had to be re-counted rather
        # than left insisting on three — a limitation that miscounts the matrix is a lie on every club page.
        assert any(
            "four rights" in text and "`curriculum.read` and `announce.read` name no child" in text for text in limitations
        ), "the rulebook counts the row as it is now, and names the two rights that tie to no child"
        assert any("rewrites nothing about a player" in text for text in limitations)
        assert any("give their seat back" in text for text in limitations)
        # The browser walk found this by tripping it: every account it drives connects from one address, so the
        # doors it re-reads share a bucket. An operator meeting a 429 in that shape has to be able to read the
        # rule somewhere other than in the error.
        assert any("per client address" in text and "proxy" in text for text in limitations), "the limiter counts an address, not an account, and the rulebook says which"
        rules = club.rules()
        assert rules["founder"].startswith("the account that opens a tenant")
        assert rules["addressing"].startswith("a tenant is reached by its slug")
        assert rules["invitations"].startswith("a row, not an email")

    def test_an_account_sees_the_integrity_of_only_its_own_tenants(self) -> None:
        owner = _account("Integrity Owner")
        ident = _slug(owner, "Tenant With A Typo")
        assert _read(owner, ident)["integrity"]["clean"] is True
        other = _account("Other Owner")
        other_ident = _slug(other, "The Other Tenant")
        session = SessionLocal()
        try:
            membership = session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == _organization_row(ident).id))
            assert membership is not None
            membership.role = "hall_monitor"
            session.commit()
        finally:
            session.close()
        reported = _read(owner, ident)["integrity"]
        assert reported["clean"] is False and any("hall_monitor" in problem for problem in reported["problems"])
        assert reported["checked"]["organizations"] == 1
        elsewhere = _read(other, other_ident)["integrity"]
        assert elsewhere["clean"] is True and elsewhere["checked"]["organizations"] == 1, "the report is scoped to the caller's tenants, so it says nothing about anybody else's"
        assert _read(owner, ident)["isolation_rule"] == access.matrix()["rule"]
        session = SessionLocal()
        try:
            membership = session.scalar(select(OrganizationMember).where(OrganizationMember.organization_id == _organization_row(ident).id))
            assert membership is not None
            membership.role = "owner"
            session.commit()
        finally:
            session.close()
        assert _read(owner, ident)["integrity"]["clean"] is True

    def test_the_counts_the_page_publishes_move_with_the_work(self, world: dict[str, Any]) -> None:
        before = TestClient(app).get(CAPABILITIES).json()["counts"]
        owner = _account("Counter")
        ident = _slug(owner, "Counted Club")
        team = _team(owner, ident, "Counted Side")
        _add(owner, ident, team["id"], world["adult"])
        after = TestClient(app).get(CAPABILITIES).json()["counts"]
        assert after["organizations"] == before["organizations"] + 1
        assert after["teams"] == before["teams"] + 1
        assert after["squad_rows"] == before["squad_rows"] + 1
        assert after["active_memberships"] == before["active_memberships"] + 1
        assert after["memberships"] >= after["active_memberships"]
        assert after["rule"].startswith("counts of tenants and standing only")
        assert TestClient(app).get(CAPABILITIES).json()["ready"] is True


class TestTheUnmigratedDatabase:
    """A database without the tenant tables reports an empty working surface rather than a 500."""

    def test_the_gate_is_the_tables_and_not_a_try_block(self, session: Session) -> None:
        assert club.club_tables_present(session) is True and club.club_ready(session) is True
        counts = club.club_counts(session)
        assert set(counts) == {"organizations", "memberships", "active_memberships", "teams", "squad_rows", "rule"}
        assert all(isinstance(counts[key], int) for key in counts if key != "rule")

    def test_a_missing_migration_is_described_rather_than_crashed(self, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(club, "club_tables_present", lambda row: False)
        counts = club.club_counts(session)
        assert counts["organizations"] == 0 and counts["memberships"] == 0 and counts["squad_rows"] == 0
        assert counts["rule"] == "the tenant tables are not in this database yet; nothing here is counted because nothing here exists"
        assert club.club_ready(session) is False
        problems = club.access_problems(session, _person(session, "un-migrated-reader"))
        assert problems["clean"] is False and problems["problems"] == ["the tenant tables are not in this database"]
        assert problems["checked"] == {"organizations": 0, "memberships": 0, "teams": 0}
        assert problems["rule"].startswith("an un-migrated database is reported")


# The walk formats every placeholder in a door's path from `PROBE`, and §39's fixture doors name a fixture
# as well as a team and an email. The id belongs to nobody: a stranger is refused before it is looked up,
# which is the only order in which the answer cannot confirm that another tenant holds the row.
assert isinstance(PROBE, dict), "the door walk's placeholders are no longer a mapping, so the fixture doors are not being probed"
PROBE.setdefault("fixture", "cfx-nobody-probed")
