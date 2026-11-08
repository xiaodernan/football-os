"""M8 §39/§40 — the club tier's list reads ask each table once, not once per row.

The defect this pins is not a wrong answer: every figure these five reads publish was already correct. It is
that the *cost* of the answer followed the tenant's size. A two-team tenant with twenty-one players on its
sheets and six plans with two reviews each cost the tenant read **32 SQL statements** and the plan listing
**22**, because each loop asked the database per row (one read per player, one per sheet row's player, one
per team's world club, one per plan's player, and two per plan's reviews — a count and a progress pass).

The reads now resolve their rows with grouped queries and hand them to the same row builders, so the count of
statements follows the *tables* the answer touches, not its people. The payloads are unchanged; the tests
around `test_club_organizations.py` and `test_club_academy.py` are the behaviour control, and the assertions
below pin the shape of the saving: at most one read of `real_players`, one of `users`, one of
`club_team_members`, one of `plan_assessments`, one of `guardian_consents` — whatever the tenant holds.

The identity map is the trap these tests have to avoid. A session that already holds a player row answers
`session.get(RealPlayer, …)` without a SQL statement, which would hide exactly the per-row read the test is
counting. So every measurement runs on a **fresh session** whose identity map is emptied after it is handed
the organisation and the account the route itself would pass in.
"""

from __future__ import annotations

import datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.main import app
from app.models import Organization, RealPlayer, User
from app.services.club import academy as edu
from app.services.club import organizations as club
from app.services.world import sync_world

CLUB = "/api/v1/club"
ACADEMY = f"{CLUB}/academy"
PASSWORD = "strong-pass-1234"
FULL_RATINGS = {"technique": 61, "tactics": 40, "physical": 55, "mental": 70, "competition_readiness": 33}
TODAY = datetime.datetime.now(datetime.UTC).date()

#: The tables a batched read may name once per call, and the ceiling on total statements. Both are budgets
#: rather than exact figures for the whole call: a future read that adds one more grouped query still passes,
#: while a return to asking per row cannot — twenty-one sheet rows push `real_players` far past 1.
ONE_READ = ("real_players", "users", "club_team_members", "club_teams", "plan_assessments", "guardian_consents", "development_plans")
TOTAL_CEILING = 10


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    session = SessionLocal()
    try:
        sync_world(session)
        players = list(session.scalars(select(RealPlayer).order_by(RealPlayer.slug)).all())
        adults = [str(row.slug) for row in players if int(row.age) >= 20]
        minors = [str(row.slug) for row in players if int(row.age) < edu.MINOR_AGE]
        assert len(adults) > 20 and len(minors) >= 2
        return {"adults": adults, "minors": minors}
    finally:
        session.close()


def _account(name: str) -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"club-reads-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": name, "role": "coach", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _email_of(client: TestClient) -> str:
    return str(client.get("/api/v1/auth/me").json()["email"])


@pytest.fixture(scope="module")
def tenant(world: dict[str, Any]) -> dict[str, Any]:
    """One tenant read back by five listings: two teams, twenty-one sheet rows, six reviewed plans, two children.

    Built once because the reads are what is under test; each measurement then opens its own session. The
    invitee is invited and does not accept, because an invitation is what `my_invitations` answers.
    """
    owner = _account("Reads Owner")
    opened = owner.post(CLUB, json={"name": "Reads Athletic", "kind": "club", "country": "en"})
    assert opened.status_code == 200, opened.text
    ident = str(opened.json()["organization"]["slug"])
    for index, name in enumerate(("Senior XI", "Reserves")):
        created = owner.post(f"{CLUB}/{ident}/teams", json={"name": name, "age_group": "open", "stage": "senior"})
        assert created.status_code == 200, created.text
        team_id = str(created.json()["team"]["id"])
        for slug in world["adults"][index * 10 : index * 10 + 10]:
            sheet = owner.post(f"{CLUB}/{ident}/teams/{team_id}/players", json={"player": slug, "note": ""})
            assert sheet.status_code == 200, sheet.text
    plan_ids = []
    for index in range(6):
        plan = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": world["adults"][index]})
        assert plan.status_code == 200, plan.text
        plan_ids.append(str(plan.json()["plan"]["id"]))
        for days in (60, 30):
            day = (TODAY - datetime.timedelta(days=days)).isoformat()
            review = owner.post(f"{ACADEMY}/{ident}/plans/{plan_ids[-1]}/assessments", json={"assessed_on": day, "ratings": FULL_RATINGS})
            assert review.status_code == 200, review.text
    guardian = _account("Reads Guardian")
    assert owner.post(f"{CLUB}/{ident}/invites", json={"email": _email_of(guardian), "role": "parent"}).status_code == 200
    assert guardian.post(f"{CLUB}/{ident}/accept").status_code == 200
    children = world["minors"][:2]
    senior = str(owner.post(f"{CLUB}/{ident}/teams", json={"name": "Under 18s", "age_group": "u18", "stage": "youth"}).json()["team"]["id"])
    for child in children:
        assert owner.post(f"{CLUB}/{ident}/teams/{senior}/players", json={"player": child, "note": ""}).status_code == 200
        assert guardian.post(f"{ACADEMY}/{ident}/consents", json={"player": child}).status_code == 200
    # One child has a plan and one does not, so the consent listing's `plans_for_this_child` is proved to be
    # the child's own count rather than the tenant's total.
    child_plan = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": children[0]})
    assert child_plan.status_code == 200, child_plan.text
    invitee = _account("Reads Invitee")
    assert owner.post(f"{CLUB}/{ident}/invites", json={"email": _email_of(invitee), "role": "analyst"}).status_code == 200
    # A second tenant invites the same account, so the invitation listing has two rows to resolve and a
    # per-row read would show up as a third statement rather than hide behind the ceiling.
    second = guardian.post(CLUB, json={"name": "Reads Second XI", "kind": "club", "country": "en"})
    assert second.status_code == 200, second.text
    second_ident = str(second.json()["organization"]["slug"])
    assert guardian.post(f"{CLUB}/{second_ident}/invites", json={"email": _email_of(invitee), "role": "scout"}).status_code == 200
    return {
        "owner": owner,
        "ident": ident,
        "invitee": invitee,
        "guardian": guardian,
        "second_ident": second_ident,
        "plans": plan_ids,
        "children": children,
        "teams": ("Senior XI", "Reserves", "Under 18s"),
    }


def _user_of(session: Session, client: TestClient) -> User:
    row = session.scalar(select(User).where(User.email == _email_of(client)))
    assert row is not None
    return row


def _reads(statements: list[str], table: str) -> int:
    return sum(1 for statement in statements if table in statement)


def _budget(statements: list[str]) -> None:
    assert len(statements) <= TOTAL_CEILING, " | ".join(statements)
    for table in ONE_READ:
        assert _reads(statements, table) <= 1, f"{table} was read {_reads(statements, table)} times: " + " | ".join(statements)


def _call(tenant: dict[str, Any], client: TestClient, fn: Any) -> tuple[Any, list[str]]:
    session = SessionLocal()
    try:
        organization = session.scalar(select(Organization).where(Organization.slug == tenant["ident"]))
        assert organization is not None
        person = _user_of(session, client)
        session.expunge_all()
        statements: list[str] = []

        def before(conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: Any) -> None:
            statements.append(" ".join(statement.split()))

        bind = session.get_bind()
        event.listen(bind, "before_cursor_execute", before)
        try:
            payload = fn(session, organization, person)
        finally:
            event.remove(bind, "before_cursor_execute", before)
        return payload, statements
    finally:
        session.close()


def test_the_tenant_read_asks_each_table_once(tenant: dict[str, Any]) -> None:
    payload, statements = _call(tenant, tenant["owner"], lambda session, organization, person: club.organization_view(session, organization, person, ident=tenant["ident"]))
    _budget(statements)
    assert _reads(statements, "organization_members") == 2, "one standing lookup and one staff list — not one per member"
    assert payload["counts"] == {
        "active_members": 2,
        "invited_members": 1,
        "owners": 1,
        "teams": 3,
        "players_on_sheets": 22,
        "member_limit": 40,
        "team_limit": 12,
    }
    sheets = {team["name"]: team["squad_size"] for team in payload["teams"]}
    assert sheets == {"Senior XI": 10, "Reserves": 10, "Under 18s": 2}
    assert sum(row["is_minor"] for team in payload["teams"] for row in team["squad"]) == 2
    assert {(member["email"], member["status"]) for member in payload["members"]} == {
        (_email_of(tenant["owner"]), "active"),
        (_email_of(tenant["guardian"]), "active"),
        (_email_of(tenant["invitee"]), "invited"),
    }


def test_the_plan_listing_reads_the_reviews_once(tenant: dict[str, Any]) -> None:
    payload, statements = _call(tenant, tenant["owner"], lambda session, organization, person: edu.list_plans(session, person, tenant["ident"]))
    _budget(statements)
    assert payload["total"] == 7, "six adult plans plus the child's plan"
    assert all(item["assessments"] == 2 for item in payload["items"] if item["id"] in tenant["plans"])
    assert all(item["progress"] == 0 for item in payload["items"] if item["id"] in tenant["plans"]), "both reviews copy the same world rating, so the direction is flat"
    # The listing's `progress` and `assessments` are the same figures the plan read publishes: one figure,
    # two doors, and the arithmetic is the reviews' own.
    detail = tenant["owner"].get(f"{ACADEMY}/{tenant['ident']}/plans/{tenant['plans'][0]}")
    assert detail.status_code == 200, detail.text
    item = next(row for row in payload["items"] if row["id"] == tenant["plans"][0])
    assert item["assessments"] == detail.json()["progress"]["assessments"] == 2
    assert item["progress"] == detail.json()["progress"]["overall_change"] == 0
    assert item["player"]["slug"] == detail.json()["player"]["slug"]


def test_the_consent_listing_reads_the_family_once(tenant: dict[str, Any]) -> None:
    payload, statements = _call(tenant, tenant["owner"], lambda session, organization, person: edu.list_consents(session, person, tenant["ident"]))
    _budget(statements)
    assert payload["total"] == payload["under_18"] == 2
    counts = {item["player"]["slug"]: item["plans_for_this_child"] for item in payload["items"]}
    assert counts == {tenant["children"][0]: 1, tenant["children"][1]: 0}, "each child's own plan count, not the tenant's"


def test_the_index_lists_in_three_reads(tenant: dict[str, Any]) -> None:
    payload, statements = _call(tenant, tenant["owner"], lambda session, organization, person: club.my_organizations(session, person))
    assert len(statements) <= 3, " | ".join(statements)
    assert payload["total"] == 1
    card = payload["items"][0]
    assert (card["active_members"], card["teams"]) == (2, 3)
    assert card["role"] == "owner" and card["status"] == "active" and card["slug"] == tenant["ident"]


def test_the_invitation_listing_reads_the_tenants_once(tenant: dict[str, Any]) -> None:
    payload, statements = _call(tenant, tenant["invitee"], lambda session, organization, person: club.my_invitations(session, person))
    assert len(statements) <= 2, " | ".join(statements)
    assert payload["total"] == 2
    assert {item["organization"] for item in payload["items"]} == {tenant["ident"], tenant["second_ident"]}
    assert sorted(item["role"] for item in payload["items"]) == ["analyst", "scout"]


def test_the_wire_publishes_the_batched_figures(tenant: dict[str, Any]) -> None:
    """The batched builders and the route publish one payload: the service figure is what the wire says."""
    view, _ = _call(tenant, tenant["owner"], lambda session, organization, person: club.organization_view(session, organization, person, ident=tenant["ident"]))
    response = tenant["owner"].get(f"{CLUB}/{tenant['ident']}")
    assert response.status_code == 200, response.text
    wire = response.json()
    assert wire["counts"] == view["counts"]
    assert [(team["name"], team["squad_size"]) for team in wire["teams"]] == [(team["name"], team["squad_size"]) for team in view["teams"]]
    listing = tenant["owner"].get(f"{ACADEMY}/{tenant['ident']}/plans")
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 7
