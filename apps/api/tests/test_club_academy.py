"""M8 §40 — a youth academy's development work, and the consent that has to stand under all of it.

§40's sentence is stronger than §39's: *a child's plan exists only while a guardian's consent says it may*.
Four arrangements make that checkable rather than aspirational, and each is a class here.

* **the consent row is four things at once** — the gate on a write, the access control on a read, the ceiling on
  which purposes may be recorded, and the anchor erasure removes from. The tests therefore knock on the same
  row from both sides: a scope not ticked must stop the *coach's* write and the *parent's* read, and a
  withdrawal must stop new writes while leaving the rows already written countable.
* **minimisation is the column list.** `STORED_FIELDS` is compared against the live tables in both directions,
  every body is `extra="forbid"`, and one test posts a home address and asserts the words never come back —
  not in the row, and not in the refusal either.
* **progress is arithmetic over the plan's own reviews.** No test can find a `progress` column, and the figures
  move when a review is deleted underneath the plan, which is the only proof that nothing is stored.
* **the code sets are the HTTP contract.** Every refusal code appears in exactly one answer set, the two tiers'
  sets are disjoint, and the published door guide is compared with `app.routes` in both directions — so a
  twentieth academy door cannot ship unlisted.

Role expectations are read from §39's matrix rather than repeated here: a `coach` writes plans but cannot erase
them, a `director` may erase but not write, an `analyst` reads everything and writes no curriculum, a `scout`
sees no plan at all, and a `parent` holds rights that mean nothing without a consent row naming one child.
"""

from __future__ import annotations

import datetime
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import new_public_id
from app.main import app
from app.models import (
    ClubTeam,
    ClubTeamMember,
    DevelopmentPlan,
    GuardianConsent,
    Organization,
    PlanAssessment,
    PlanVideoEvidence,
    RealPlayer,
    User,
    VideoAsset,
)
from app.services.club import academy as edu
from app.services.club import access
from app.services.club import organizations as club
from app.services.world import sync_world, world_ready

CLUB = "/api/v1/club"
ACADEMY = f"{CLUB}/academy"
CAPABILITIES = f"{ACADEMY}/capabilities"
PASSWORD = "strong-pass-1234"
TODAY = datetime.datetime.now(datetime.UTC).date()  # the service reads `datetime.now(UTC).date()`; a local `date.today()` on a UTC+8 host is a day off
#: Dates inside the season a test writes about, all of them in the past so `date_in_future` cannot fire by accident.
PAST = [(TODAY - datetime.timedelta(days=days)).isoformat() for days in (120, 90, 60, 30, 7)]
FULL_RATINGS = {"technique": 61, "tactics": 40, "physical": 55, "mental": 70, "competition_readiness": 33}


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """A seeded world with enough sheets to fill the caps this tier publishes."""
    session = SessionLocal()
    try:
        sync_world(session)
        players = list(session.scalars(select(RealPlayer).order_by(RealPlayer.slug)).all())
        assert len(players) > edu.MAX_PLANS_PER_ORGANIZATION + 10 and world_ready(session)
        minors = [row.slug for row in players if int(row.age) < edu.MINOR_AGE]
        adults = [row.slug for row in players if int(row.age) >= edu.MINOR_AGE]
        assert len(minors) >= 4 and len(adults) > edu.MAX_PLANS_PER_ORGANIZATION
        return {
            "players": len(players),
            "minors": minors,
            "adults": adults,
            # A child nobody has added to a sheet: the plan door has to refuse them by name.
            "off_sheet": adults[-1],
        }
    finally:
        session.close()


@pytest.fixture()
def session(world: dict[str, Any]) -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _account(name: str = "Academy Coach") -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"academy-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": name, "role": "coach", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _email_of(client: TestClient) -> str:
    return str(client.get("/api/v1/auth/me").json()["email"])


def _detail(response: Any) -> dict[str, Any]:
    """A service refusal. The framework's own 422 arrives under `error` instead — see `_validation`."""
    body = response.json()
    assert "detail" in body, body
    return dict(body["detail"])


def _validation(response: Any) -> dict[str, Any]:
    body = response.json()
    assert "error" in body, body
    return dict(body["error"])


def _opened(client: TestClient, name: str, **body: Any) -> dict[str, Any]:
    response = client.post(CLUB, json={"name": name, **body})
    assert response.status_code == 200, response.text
    return response.json()


def _tenant(name: str = "Riverside Academy", owner: str = "Head Of Coaching") -> tuple[TestClient, str]:
    owner_client = _account(owner)
    return owner_client, str(_opened(owner_client, name, kind="academy", country="en")["organization"]["slug"])


def _joined(owner: TestClient, ident: str, role: str, name: str) -> TestClient:
    guest = _account(name)
    assert owner.post(f"{CLUB}/{ident}/invites", json={"email": _email_of(guest), "role": role}).status_code == 200
    assert guest.post(f"{CLUB}/{ident}/accept").status_code == 200
    return guest


def _team(owner: TestClient, ident: str, name: str) -> dict[str, Any]:
    response = owner.post(f"{CLUB}/{ident}/teams", json={"name": name, "age_group": "u16", "stage": "youth"})
    assert response.status_code == 200, response.text
    return response.json()["team"]


def _sheet(owner: TestClient, ident: str, team: str, *slugs: str) -> None:
    for slug in slugs:
        response = owner.post(f"{CLUB}/{ident}/teams/{team}/players", json={"player": slug, "note": ""})
        assert response.status_code == 200, response.text


def _grant(guardian: TestClient, ident: str, slug: str, scopes: list[str] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"player": slug}
    if scopes is not None:
        body["scopes"] = scopes
    response = guardian.post(f"{ACADEMY}/{ident}/consents", json=body)
    assert response.status_code == 200, response.text
    return response.json()["consent"]


def _plan(client: TestClient, ident: str, slug: str, **body: Any) -> dict[str, Any]:
    response = client.post(f"{ACADEMY}/{ident}/plans", json={"player": slug, **body})
    assert response.status_code == 200, response.text
    return response.json()["plan"]


def _read(client: TestClient, ident: str, plan_id: str) -> dict[str, Any]:
    response = client.get(f"{ACADEMY}/{ident}/plans/{plan_id}")
    assert response.status_code == 200, response.text
    return response.json()


def _review(client: TestClient, ident: str, plan_id: str, day: str, ratings: dict[str, int] | None = None, **body: Any) -> dict[str, Any]:
    response = client.post(f"{ACADEMY}/{ident}/plans/{plan_id}/assessments", json={"assessed_on": day, "ratings": ratings or FULL_RATINGS, **body})
    assert response.status_code == 200, response.text
    return response.json()["assessment"]


def _curriculum(client: TestClient, ident: str, name: str, **body: Any) -> dict[str, Any]:
    response = client.post(f"{ACADEMY}/{ident}/curricula", json={"name": name, **body})
    assert response.status_code == 200, response.text
    return response.json()["curriculum"]


def _clip_of(client: TestClient, session: Session, duration: float = 40.0) -> dict[str, Any]:
    """An M5 upload owned by this account: §40 cites footage, it does not take one."""
    owner = session.scalar(select(User).where(User.email == _email_of(client)))
    assert owner is not None
    now = datetime.datetime.now(datetime.UTC)
    asset = VideoAsset(
        id=new_public_id("vid"),
        owner_id=owner.id,
        title="u16 pressing drill",
        filename="clip.mp4",
        storage_key=f"academy-probe/{uuid4().hex}.mp4",
        content_type="video/mp4",
        size_bytes=4096,
        duration_s=duration,
        width=1280,
        height=720,
        fps=25.0,
        codec="h264",
        created_at=now,
        updated_at=now,
    )
    session.add(asset)
    session.commit()
    return {"id": asset.id, "duration_s": duration}


def _organization_id(session: Session, slug: str) -> str:
    row = session.scalar(select(Organization).where(Organization.slug == slug))
    assert row is not None
    return str(row.id)


def _player_id(session: Session, slug: str) -> str:
    row = session.scalar(select(RealPlayer).where(RealPlayer.slug == slug))
    assert row is not None
    return str(row.id)


def _plan_id(session: Session, ident: str) -> str:
    row = session.scalar(select(DevelopmentPlan).join(Organization, Organization.id == DevelopmentPlan.organization_id).where(Organization.slug == ident))
    assert row is not None
    return str(row.id)


def _live_column_names(session: Session, table: str) -> set[str]:
    return {str(column["name"]) for column in inspect(session.get_bind()).get_columns(table)}


class TestThePublishedRulebook:
    """A guardian has to be able to read the rules before agreeing to them, so the door is open."""

    def test_the_rulebook_is_readable_without_an_account(self) -> None:
        response = TestClient(app).get(CAPABILITIES)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["axes"] == list(edu.AXES)
        assert body["scopes"] == list(edu.SCOPES)
        # The one figure in this file that a parent's decision actually turns on.
        assert body["default_scopes"] == ["plan", "assessment", "feedback"]
        assert "video" not in body["default_scopes"], "consenting to a plan must not consent to footage of a child"
        assert body["minor_age"] == 18 and body["rating_range"] == [0, 100]
        assert body["review_weeks_range"] == [edu.REVIEW_WEEKS_MIN, edu.REVIEW_WEEKS_MAX]
        assert body["never_stored"] == list(edu.RESTRICTED_FIELDS)
        assert sorted(body["stored_fields"]) == sorted(edu.STORED_FIELDS)
        assert body["refusals"] == list(edu.REFUSALS)
        assert body["refusals_shared_with_club_tier"] == list(edu.SHARED_REFUSALS)
        assert body["ready_rule"] == club.READY_RULE, "one flag means one thing at both doors, so the sentence is the same object rather than two that a reader must trust"
        assert isinstance(body["ready"], bool), "the flag is a measurement of this database, never a claim the deployment configures"

    def test_the_rulebook_names_the_two_things_consent_cannot_do(self) -> None:
        body = TestClient(app).get(CAPABILITIES).json()
        assert "self-declared" in body["guardianship"]
        assert "under 18" in body["consent"] and "adult" in body["consent"]
        joined = " ".join(str(line) for line in body["limitations"])
        for needle in ("guardian", "regenerat", "medical", "free text"):
            assert needle in joined, f"`limitations()` never admits {needle!r}"

    def test_every_refusal_code_has_exactly_one_http_answer(self) -> None:
        answers = TestClient(app).get(CAPABILITIES).json()["refusal_answers"]
        own = set(edu.REFUSALS)
        assert own == edu.NOT_FOUND_CODES | edu.UNPROCESSABLE_CODES | edu.CONFLICT_CODES | edu.FORBIDDEN_CODES
        assert not (edu.NOT_FOUND_CODES & edu.UNPROCESSABLE_CODES)
        assert not (edu.CONFLICT_CODES & (edu.NOT_FOUND_CODES | edu.UNPROCESSABLE_CODES))
        assert not (edu.FORBIDDEN_CODES), "§40 adds no 403 of its own — every refusal here is a missing row, a missing figure or a missing consent"
        assert len(own) == len(answers) - len(edu.SHARED_REFUSALS)
        assert {answers[code] for code in own} == {404, 422, 409}
        assert answers["insufficient_role"] == 403 and answers["no_such_organization"] == 404

    def test_the_two_tiers_share_no_refusal_code(self) -> None:
        # A code that meant two things would answer with two status codes, and the page could not tell a
        # guardian why nothing was written.
        assert not set(edu.REFUSALS) & set(club.REFUSALS)
        assert set(edu.SHARED_REFUSALS) <= set(club.REFUSALS)

    def test_the_door_guide_is_the_academy_route_table(self) -> None:
        living: set[tuple[str, str]] = set()
        for route in app.routes:
            path = str(getattr(route, "path", ""))
            if not path.startswith(f"{ACADEMY}"):
                continue
            for method in sorted(getattr(route, "methods", set()) or set()):
                if method not in {"HEAD", "OPTIONS"}:
                    living.add((method.lower(), path))
        declared = {(str(method).lower(), line["path"]) for line in edu_guide() for method in line["methods"]}
        assert declared == living, sorted(declared ^ living)
        for line in edu_guide():
            assert len(line["purpose"]) > 20, line
            # §39 routes `GET /club/{ident}`, so an academy door one segment below `/club` would be a tenant.
            assert line["path"].startswith("/api/v1/club/academy/") and line["path"].count("/") >= 5, line

    def test_the_academy_publishes_its_own_readiness_and_counts(self, monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
        _account("Somebody Who Can Own A Tenant")
        counts = edu.academy_counts(session)
        assert counts["rule"].startswith("row counts") and "child" in counts["rule"]
        assert set(counts) >= {
            "curricula",
            "plans",
            "plans_of_minors",
            "closed_plans",
            "assessments",
            "coach_feedback",
            "feedback_held_from_guardian",
            "video_citations",
            "citations_without_clip",
            "consents_granted",
            "consents_withdrawn",
        }
        assert edu.academy_tables_present(session) is True and edu.academy_ready(session) is True
        # An unmigrated database must report an empty working surface, not a 500: these counts are read on
        # a page load, and `0016` and `0017` land on different days in the wild.
        monkeypatch.setattr(edu, "academy_tables_present", lambda row: False)
        assert edu.academy_ready(session) is False
        empty = edu.academy_counts(session)
        assert empty["plans"] == 0 and "not in this database yet" in empty["rule"]
        assert set(empty) < set(counts), "the unmigrated answer is a subset, so a reader cannot mistake it for a quiet academy"


def edu_guide() -> list[dict[str, Any]]:
    from app.api.v1.club_academy import ROUTE_GUIDE

    return list(ROUTE_GUIDE)


class TestACurriculum:
    """A curriculum names no child, which is why it is the one academy row every standing may read."""

    def test_a_week_that_schedules_less_than_it_claims_says_so(self) -> None:
        owner, ident = _tenant("Kingsmeadow Youth")
        _team(owner, ident, "Under 16s")
        row = _curriculum(
            owner,
            ident,
            "U16 pressing block",
            age_group="u16",
            weekly_minutes=240,
            phases=[{"label": "warm-up", "focus": "mobility", "minutes": 30}, {"label": "pressing", "focus": "first touch", "minutes": 90}],
        )
        assert row["phase_count"] == 2 and row["phase_minutes"] == 120
        assert row["unassigned_minutes"] == 120
        assert row["plans_using_it"] == 0
        assert "240" in row["formulas"]["unassigned_minutes"]
        assert row["data_origin"] == "user" and row["is_demo_data"] is False

    def test_a_phases_minutes_can_be_the_whole_week_or_none_of_it(self) -> None:
        owner, ident = _tenant("Exact Hours Academy")
        assert _curriculum(owner, ident, "Full week", weekly_minutes=60, phases=[{"label": "games", "focus": "playing", "minutes": 60}])["unassigned_minutes"] == 0
        assert _curriculum(owner, ident, "Nothing scheduled", weekly_minutes=60)["unassigned_minutes"] == 60

    def test_a_curriculum_needs_a_name_and_a_tenant_cannot_have_two_of_the_same(self) -> None:
        owner, ident = _tenant("Name Test Academy")
        refused = owner.post(f"{ACADEMY}/{ident}/curricula", json={"name": "   "})
        assert refused.status_code == 422 and _detail(refused)["code"] == "name_required"
        _curriculum(owner, ident, "U14 Foundation")
        again = owner.post(f"{ACADEMY}/{ident}/curricula", json={"name": "u14 foundation"})
        assert again.status_code == 409 and _detail(again)["code"] == "curriculum_name_taken", "case must not be a way to get two curricula with one name"

    def test_the_week_and_the_phase_count_are_measured_from_both_sides(self) -> None:
        owner, ident = _tenant("Boundary Academy")
        over = owner.post(f"{ACADEMY}/{ident}/curricula", json={"name": "Too long a week", "weekly_minutes": edu.WEEKLY_MINUTES_MAX + 1})
        assert over.status_code == 422 and _detail(over)["code"] == "weekly_minutes_range"
        assert _detail(over)["high"] == edu.WEEKLY_MINUTES_MAX
        assert _curriculum(owner, ident, "The longest legal week", weekly_minutes=edu.WEEKLY_MINUTES_MAX)["weekly_minutes"] == edu.WEEKLY_MINUTES_MAX
        negative = owner.post(f"{ACADEMY}/{ident}/curricula", json={"name": "Negative hours", "weekly_minutes": -1})
        assert _detail(negative)["code"] == "weekly_minutes_range" and _detail(negative)["low"] == 0
        blocked = [{"label": f"block {index}", "focus": "work", "minutes": 5} for index in range(edu.MAX_PHASES_PER_CURRICULUM)]
        assert _curriculum(owner, ident, "As many phases as allowed", phases=blocked)["phase_count"] == edu.MAX_PHASES_PER_CURRICULUM
        blocked.append({"label": "one too many", "focus": "work", "minutes": 5})
        refused = owner.post(f"{ACADEMY}/{ident}/curricula", json={"name": "One phase too many", "phases": blocked})
        assert refused.status_code == 422 and _detail(refused)["code"] == "phase_limit"
        assert _detail(refused)["held"] == edu.MAX_PHASES_PER_CURRICULUM + 1

    def test_a_phase_has_three_keys_because_a_fourth_is_a_drill_the_tier_cannot_check(self) -> None:
        owner, ident = _tenant("Phase Shape Academy")
        refused = owner.post(f"{ACADEMY}/{ident}/curricula", json={"name": "A phase with a drill id", "phases": [{"label": "pressing", "focus": "first touch", "minutes": 20, "drill": "c1-pressure"}]})
        assert refused.status_code == 422 and _validation(refused)["code"] == "validation_error"
        # The door's schema answers first, so the value never reaches a column — and never reaches the page either.
        assert "c1-pressure" not in refused.text
        session = SessionLocal()
        try:
            with pytest.raises(edu.ClubRefusal) as caught:
                edu._phases([{"label": "pressing", "minutes": 20, "drill": "c1-pressure"}])
            assert caught.value.code == "phase_shape"
        finally:
            session.close()

    def test_the_curriculum_cap_is_one_write_away_from_the_refusal(self) -> None:
        owner, ident = _tenant("Twelve Blocks Academy")
        for index in range(edu.MAX_CURRICULA_PER_ORGANIZATION):
            _curriculum(owner, ident, f"Block {index}")
        listing = owner.get(f"{ACADEMY}/{ident}/curricula").json()
        assert listing["total"] == edu.MAX_CURRICULA_PER_ORGANIZATION and listing["room_left"] == 0
        assert listing["limit"] == edu.MAX_CURRICULA_PER_ORGANIZATION
        refused = owner.post(f"{ACADEMY}/{ident}/curricula", json={"name": "One block too many"})
        assert refused.status_code == 422 and _detail(refused)["code"] == "curriculum_limit"
        assert _detail(refused)["held"] == edu.MAX_CURRICULA_PER_ORGANIZATION

    def test_every_standing_may_read_a_curriculum_but_only_two_stands_may_write_one(self) -> None:
        owner, ident = _tenant("Open Curriculum Academy")
        _curriculum(owner, ident, "U16 Foundation")
        for role, writable in [("coach", True), ("analyst", False), ("scout", False), ("parent", False), ("director", True)]:
            member = _joined(owner, ident, role, f"Reader {role}")
            assert member.get(f"{ACADEMY}/{ident}/curricula").status_code == 200, role
            refused = member.post(f"{ACADEMY}/{ident}/curricula", json={"name": f"A {role} writes one"})
            if writable:
                assert refused.status_code == 200, (role, refused.text)
            else:
                assert refused.status_code == 403 and _detail(refused)["permission"] == "curriculum.write", role

    def test_deleting_a_curriculum_repoints_the_plans_rather_than_deleting_them(self) -> None:
        owner, ident = _tenant("Repoint Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        _grant(_joined(owner, ident, "parent", "A Guardian"), ident, child)
        row = _curriculum(owner, ident, "U16 block", weekly_minutes=120)
        plan = _plan(owner, ident, child, **{"focus": ["first touch"], "curriculum": row["id"]})
        assert _read(owner, ident, plan["id"])["curriculum"]["id"] == row["id"]
        response = owner.delete(f"{ACADEMY}/{ident}/curricula/{row['id']}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["deleted"] is True and body["plans_repointed"] == 1
        after = _read(owner, ident, plan["id"])
        assert after["curriculum"] is None, "the curriculum was the tenant's; the plan is the child's"
        assert after["plan"]["focus"] == ["first touch"]

    def test_editing_reports_only_what_moved(self) -> None:
        owner, ident = _tenant("Patch Curriculum Academy")
        row = _curriculum(owner, ident, "First name", weekly_minutes=60)
        response = owner.patch(f"{ACADEMY}/{ident}/curricula/{row['id']}", json={"weekly_minutes": 90})
        assert response.status_code == 200, response.text
        assert response.json()["changed"] == {"weekly_minutes": 90}
        assert response.json()["curriculum"]["unassigned_minutes"] == 90
        untouched = owner.patch(f"{ACADEMY}/{ident}/curricula/{row['id']}", json={})
        assert untouched.json()["changed"] == {}


def world_child(ident: str, owner: TestClient, team: str, index: int) -> str:
    """One of the world's minors, put on this tenant's sheet."""
    session = SessionLocal()
    try:
        slug = str(session.scalars(select(RealPlayer).where(RealPlayer.age < edu.MINOR_AGE).order_by(RealPlayer.slug)).all()[index].slug)
    finally:
        session.close()
    _sheet(owner, ident, team, slug)
    return slug


class TestOnePlanPerChild:
    """The rule that makes the rest of §40 possible: one child, one live plan, and a yes before either."""

    def test_a_minor_cannot_be_planned_for_until_somebody_answers_for_them(self) -> None:
        owner, ident = _tenant("No Consent Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        refused = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": child, "focus": ["left foot"]})
        assert refused.status_code == 422
        detail = _detail(refused)
        assert detail["code"] == "consent_required"
        session = SessionLocal()
        try:
            assert detail["age"] == int(session.scalar(select(RealPlayer.age).where(RealPlayer.slug == child)))
        finally:
            session.close()
        assert detail["threshold"] == edu.MINOR_AGE and detail["scope"] == "plan"
        assert detail["consent_rows"] == 0

    def test_an_adult_needs_no_one_to_answer_for_them(self) -> None:
        owner, ident = _tenant("Overage Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(0))
        plan = _plan(owner, ident, _adult(0), **{"focus": ["set pieces"]})
        assert plan["minor_at_open"] is False and plan["age_at_open"] >= edu.MINOR_AGE
        assert plan["status"] == "active"

    def test_the_consent_that_lets_a_plan_open_is_named_in_the_answer(self) -> None:
        owner, ident = _tenant("Consented Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        guardian = _joined(owner, ident, "parent", "The Guardian")
        consent = _grant(guardian, ident, child)
        body = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": child, "focus": ["left foot"]}).json()
        assert body["consented_by"]["consent"] == consent["id"] and body["consented_by"]["scopes"] == list(edu.DEFAULT_SCOPES)
        session = SessionLocal()
        try:
            # The gate is named by opaque id rather than by address: the answer has to say *which* row let this
            # plan open, and a guardian's email is not a fact a plan page publishes to every staff standing.
            assert body["consented_by"]["guardian"] == str(session.scalar(select(User.id).where(User.email == _email_of(guardian))))
        finally:
            session.close()
        assert _email_of(guardian) not in parent_view_text(body), "the plan answer carries the consent's id, not its owner's address"
        assert "home address" in body["not_stored"] and "precise location" in body["not_stored"]

    def test_a_child_has_one_live_plan_and_a_closed_one_frees_the_seat(self) -> None:
        owner, ident = _tenant("One Plan Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        _grant(_joined(owner, ident, "parent", "Guardian One"), ident, child)
        plan = _plan(owner, ident, child, **{"focus": ["left foot"]})
        again = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": child})
        assert again.status_code == 409 and _detail(again)["code"] == "plan_already_open"
        assert _detail(again)["plan"] == plan["id"]
        assert owner.patch(f"{ACADEMY}/{ident}/plans/{plan['id']}", json={"status": "closed"}).status_code == 200
        reopened = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": child, "focus": ["pressing"]})
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["plan"]["id"] != plan["id"]
        assert _detail(again)["player"] == child

    def test_a_player_who_does_not_train_here_is_refused_by_name_and_count(self) -> None:
        owner, ident = _tenant("Wrong Child Academy")
        _team(owner, ident, "Under 16s")
        stranger = _off_sheet()
        refused = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": stranger})
        assert refused.status_code == 422 and _detail(refused)["code"] == "not_on_sheet"
        assert _detail(refused)["teams"] == 1 and _detail(refused)["player"] == stranger
        absent = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": "nobody-at-all"})
        assert absent.status_code == 404 and _detail(absent)["code"] == "no_such_player", "a slug that resolves to no row anywhere is the 404 every other door in the API gives for it"

    def test_an_unknown_status_and_an_impossible_cadence_are_both_refused_with_their_figures(self) -> None:
        owner, ident = _tenant("Status Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(1))
        plan = _plan(owner, ident, _adult(1))
        refused = owner.patch(f"{ACADEMY}/{ident}/plans/{plan['id']}", json={"status": "on-loan"})
        assert refused.status_code == 422 and _detail(refused)["code"] == "unknown_status"
        assert _detail(refused)["statuses"] == list(edu.PLAN_STATUSES)
        for weeks in (0, edu.REVIEW_WEEKS_MAX + 1):
            bad = owner.patch(f"{ACADEMY}/{ident}/plans/{plan['id']}", json={"review_weeks": weeks})
            assert _detail(bad)["code"] == "review_weeks_range" and _detail(bad)["value"] == weeks
        assert owner.patch(f"{ACADEMY}/{ident}/plans/{plan['id']}", json={"review_weeks": edu.REVIEW_WEEKS_MAX}).status_code == 200

    def test_a_goal_that_carries_a_fourth_key_has_nowhere_to_be_stored(self) -> None:
        owner, ident = _tenant("Goal Shape Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(2))
        refused = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": _adult(2), "goals": [{"title": "be faster", "measure": "sprints", "by": "2026-12-31", "gps_data": "0192"}]})
        assert refused.status_code == 422
        # `loc` is the schema talking about the schema, so the key comes back; the tracking number does not.
        assert "gps_data" in refused.text and "0192" not in refused.text
        titled = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": _adult(2), "goals": [{"measure": "sprints"}]})
        assert titled.status_code == 422 and _detail(titled)["code"] == "goal_shape"
        assert f"{edu.GOAL_TITLE_MAX}" in _detail(titled)["message"]
        plan = _plan(owner, ident, _adult(2), **{"goals": [{"title": "be faster", "by": PAST[4]}]})
        assert plan["goals"] == [{"title": "be faster", "by": PAST[4]}], "an optional measure stays out rather than stored empty"

    def test_a_plan_names_a_handful_of_focus_areas_and_no_more(self) -> None:
        owner, ident = _tenant("Focus Cap Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(3), _adult(21))
        plan = _plan(owner, ident, _adult(3), **{"focus": [f"area {index}" for index in range(edu.FOCUS_ITEMS_MAX)]})
        assert len(plan["focus"]) == edu.FOCUS_ITEMS_MAX
        # A second child asks for the over-long list: the door that refuses a duplicate plan answers before the
        # focus list is read, so aiming both requests at one player would test the duplicate rule instead.
        refused = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": _adult(21), "focus": [f"area {index}" for index in range(edu.FOCUS_ITEMS_MAX + 1)]})
        assert _detail(refused)["code"] == "focus_limit" and _detail(refused)["max"] == edu.FOCUS_ITEMS_MAX

    def test_the_plan_cap_is_reached_one_child_at_a_time(self) -> None:
        owner, ident = _tenant("Full Book Academy")
        # `MAX_SQUAD_PER_TEAM` sits below `MAX_PLANS_PER_ORGANIZATION`, so the book is filled across several
        # sheets: a refusal that arrived from the squad cap would prove nothing about the plan cap.
        adults = _adults()[: edu.MAX_PLANS_PER_ORGANIZATION + 1]
        assert len(adults) == edu.MAX_PLANS_PER_ORGANIZATION + 1
        step = club.MAX_SQUAD_PER_TEAM
        for index in range(0, len(adults), step):
            team = _team(owner, ident, f"Squad {index // step + 1}")
            _sheet(owner, ident, team["name"], *adults[index : index + step])
        for slug in adults[:-1]:
            _plan(owner, ident, slug)
        listing = owner.get(f"{ACADEMY}/{ident}/plans").json()
        assert listing["total"] == edu.MAX_PLANS_PER_ORGANIZATION and listing["limit"] == edu.MAX_PLANS_PER_ORGANIZATION
        refused = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": adults[-1]})
        assert refused.status_code == 422 and _detail(refused)["code"] == "plan_limit"
        assert _detail(refused)["held"] == edu.MAX_PLANS_PER_ORGANIZATION

    def test_a_closed_plan_refuses_to_be_written_into(self) -> None:
        owner, ident = _tenant("Closed Season Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(4))
        plan = _plan(owner, ident, _adult(4))
        owner.patch(f"{ACADEMY}/{ident}/plans/{plan['id']}", json={"status": "closed"})
        edit = owner.patch(f"{ACADEMY}/{ident}/plans/{plan['id']}", json={"focus": ["pressing"]})
        assert edit.status_code == 409 and _detail(edit)["code"] == "plan_is_closed"
        review = owner.post(f"{ACADEMY}/{ident}/plans/{plan['id']}/assessments", json={"assessed_on": PAST[4], "ratings": FULL_RATINGS})
        assert review.status_code == 409, review.text

    def test_the_role_that_may_read_a_plan_is_the_role_that_may_write_one_except_once(self) -> None:
        owner, ident = _tenant("Role Plan Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        _grant(_joined(owner, ident, "parent", "Guardian Two"), ident, child)
        plan = _plan(owner, ident, child)
        coach = _joined(owner, ident, "coach", "Assistant Coach")
        assert coach.get(f"{ACADEMY}/{ident}/plans/{plan['id']}").status_code == 200
        assert coach.post(f"{ACADEMY}/{ident}/plans/{plan['id']}/feedback", json={"message": "good week"}).status_code == 200
        analyst = _joined(owner, ident, "analyst", "Analyst")
        assert analyst.get(f"{ACADEMY}/{ident}/plans/{plan['id']}").status_code == 200
        assert analyst.post(f"{ACADEMY}/{ident}/curricula", json={"name": "An analyst writes a curriculum"}).status_code == 403
        scout = _joined(owner, ident, "scout", "Opposition Scout")
        refused = scout.get(f"{ACADEMY}/{ident}/plans")
        assert refused.status_code == 403 and _detail(refused)["permission"] == "plan.read_all"
        assert scout.get(f"{ACADEMY}/{ident}/plans/{plan['id']}").status_code == 403
        director = _joined(owner, ident, "director", "A Director")
        assert director.delete(f"{ACADEMY}/{ident}/plans/{plan['id']}").status_code == 422, "erase is a dry door until confirm arrives"
        assert director.post(f"{ACADEMY}/{ident}/plans", json={"player": child}).status_code == 403, "a director reads and erases plans but does not write them"


def _adults() -> list[str]:
    session = SessionLocal()
    try:
        return [str(row.slug) for row in session.scalars(select(RealPlayer).where(RealPlayer.age >= 20).order_by(RealPlayer.slug)).all()]
    finally:
        session.close()


def _adult(index: int) -> str:
    return _adults()[index]


def _off_sheet() -> str:
    return _adults()[-1]


class TestTheConsentRow:
    """One row is the gate, the ceiling, the record and the erasure anchor. All four are tested here."""

    def test_only_a_parent_standing_in_the_tenant_may_answer_for_a_child(self) -> None:
        owner, ident = _tenant("Who Consents Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        assert owner.post(f"{ACADEMY}/{ident}/consents", json={"player": child}).status_code == 403
        assert _owner_of_elsewhere(ident).post(f"{ACADEMY}/{ident}/consents", json={"player": child}).status_code == 404
        member = _joined(owner, ident, "parent", "Consenter")
        assert member.post(f"{ACADEMY}/{ident}/consents", json={"player": child}).status_code == 200

    def test_a_guardian_claims_only_a_child_this_tenant_trains(self) -> None:
        owner, ident = _tenant("Claim Scope Academy")
        _team(owner, ident, "Under 16s")
        stranger = _off_sheet()
        member = _joined(owner, ident, "parent", "Claiming Guardian")
        refused = member.post(f"{ACADEMY}/{ident}/consents", json={"player": stranger})
        assert refused.status_code == 422 and _detail(refused)["code"] == "not_on_sheet"

    def test_a_scope_nobody_ticked_is_refused_and_names_the_ones_that_were(self) -> None:
        owner, ident = _tenant("Scope Ceiling Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        guardian = _joined(owner, ident, "parent", "Narrow Guardian")
        _grant(guardian, ident, child, ["plan"])
        plan = _plan(owner, ident, child)["id"]
        review = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[4], "ratings": FULL_RATINGS})
        assert review.status_code == 422
        detail = _detail(review)
        assert detail["code"] == "scope_not_consented" and detail["scope"] == "assessment"
        assert list(detail["scopes_present"]) == ["plan"], "the useful next action is a guardian ticking one more box"
        assert _grant(guardian, ident, child, ["plan", "assessment"])["scopes"] == ["plan", "assessment"]
        assert owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[4], "ratings": FULL_RATINGS}).status_code == 200

    def test_a_scope_name_that_is_not_a_purpose_is_refused_by_the_list(self) -> None:
        owner, ident = _tenant("Bad Scope Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        guardian = _joined(owner, ident, "parent", "Broad Guardian")
        refused = guardian.post(f"{ACADEMY}/{ident}/consents", json={"player": child, "scopes": ["plan", "sell_data"]})
        assert refused.status_code == 422 and _detail(refused)["code"] == "unknown_scope"
        assert _detail(refused)["unknown"] == ["sell_data"] and _detail(refused)["scopes"] == list(edu.SCOPES)

    def test_an_empty_scope_list_is_not_a_default(self) -> None:
        owner, ident = _tenant("Empty Consent Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        guardian = _joined(owner, ident, "parent", "Blank Guardian")
        refused = guardian.post(f"{ACADEMY}/{ident}/consents", json={"player": child, "scopes": []})
        assert refused.status_code == 422 and _detail(refused)["code"] == "unknown_scope"
        # Leaving the field out is the default; ticking nothing is a refusal. Only one of the two grants feedback rights.
        assert _grant(guardian, ident, child)["scopes"] == list(edu.DEFAULT_SCOPES)
        assert "feedback" in _grant(guardian, ident, child)["scopes"]

    def test_re_granting_widens_the_same_row_instead_of_stacking_a_second_yes(self) -> None:
        owner, ident = _tenant("Rewidened Consent Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        guardian = _joined(owner, ident, "parent", "Widening Guardian")
        first = _grant(guardian, ident, child, ["plan"])
        second = _grant(guardian, ident, child, ["plan", "video"])
        assert second["id"] == first["id"]
        listing = guardian.get(f"{ACADEMY}/{ident}/consents").json()
        assert listing["total"] == 1 and listing["items"][0]["scopes"] == ["plan", "video"]
        assert listing["seen_as"] == "own_child" and listing["under_18"] == 1

    def test_a_withdrawal_stops_new_writes_and_touches_nothing_already_written(self) -> None:
        owner, ident = _tenant("Withdrawal Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        guardian = _joined(owner, ident, "parent", "Withdrawing Guardian")
        _grant(guardian, ident, child)
        plan = _plan(owner, ident, child)["id"]
        _review(owner, ident, plan, PAST[3])
        _review(owner, ident, plan, PAST[4], {"technique": 70, "tactics": 50, "physical": 60, "mental": 70, "competition_readiness": 45})
        response = guardian.delete(f"{ACADEMY}/{ident}/consents/{child}")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["withdrawn"] is True and body["consent"]["state"] == "withdrawn"
        assert body["plans_left_open"] == 1
        refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[4], "ratings": FULL_RATINGS})
        assert refused.status_code == 422 and _detail(refused)["code"] == "consent_required"
        edit = owner.patch(f"{ACADEMY}/{ident}/plans/{plan['id'] if isinstance(plan, dict) else plan}", json={"focus": ["pressing"]})
        assert edit.status_code == 422 and _detail(edit)["code"] == "consent_required", "editing a plan re-asks the consent that let it open"
        inventory = owner.get(f"{ACADEMY}/{ident}/players/{child}/data").json()["held_by_this_tenant"]
        assert inventory["plan_assessments"] == 2 and inventory["guardian_consents"] == 1, "a withdrawn consent is still a consent that was in force"
        session = SessionLocal()
        try:
            row = session.scalar(select(GuardianConsent).where(GuardianConsent.player_id == _player_id(session, child), GuardianConsent.organization_id == _organization_id(session, ident)))
            assert row is not None and row.state == "withdrawn", "this child is on other tenants' sheets too; the door changes one row, not every claim about the same name"
        finally:
            session.close()
        assert _grant(guardian, ident, child)["state"] == "granted"

    def test_a_guardian_claims_a_handful_of_children_and_no_more(self) -> None:
        owner, ident = _tenant("Many Children Academy")
        team = _team(owner, ident, "Under 16s")
        guardian = _joined(owner, ident, "parent", "Guardian Of Many")
        minors = [str(row.slug) for row in _minors_rows()[: edu.MAX_CONSENTS_PER_GUARDIAN + 1]]
        _sheet(owner, ident, team["name"], *minors)
        for slug in minors[: edu.MAX_CONSENTS_PER_GUARDIAN]:
            assert _grant(guardian, ident, slug)["player"]["slug"] == slug
        refused = guardian.post(f"{ACADEMY}/{ident}/consents", json={"player": minors[edu.MAX_CONSENTS_PER_GUARDIAN]})
        assert refused.status_code == 422 and _detail(refused)["code"] == "consent_limit"
        assert _detail(refused)["limit"] == edu.MAX_CONSENTS_PER_GUARDIAN

    def test_the_tenant_sees_every_consent_and_a_guardian_sees_only_their_own(self) -> None:
        owner, ident = _tenant("Two Guardians Academy")
        team = _team(owner, ident, "Under 16s")
        first, second = world_child(ident, owner, team["name"], 0), world_child(ident, owner, team["name"], 1)
        one = _joined(owner, ident, "parent", "Guardian One")
        two = _joined(owner, ident, "parent", "Guardian Two")
        _grant(one, ident, first)
        _grant(two, ident, second)
        staff_view = owner.get(f"{ACADEMY}/{ident}/consents").json()
        assert staff_view["total"] == 2 and staff_view["seen_as"] == "tenant"
        assert {item["player"]["slug"] for item in staff_view["items"]} == {first, second}
        assert staff_view["items"][0]["guardian"]["email"], "a tenant has to be able to say who answered for a child"
        assert [item["player"]["slug"] for item in one.get(f"{ACADEMY}/{ident}/consents").json()["items"]] == [first]

    def test_a_consent_about_a_child_names_age_and_minority_but_no_other_column(self) -> None:
        owner, ident = _tenant("Consent View Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        consent = _grant(_joined(owner, ident, "parent", "Describing Guardian"), ident, child)
        assert set(consent) == {"id", "player", "guardian", "state", "scopes", "plans_for_this_child", "granted_at", "updated_at"}
        assert consent["player"]["is_minor"] is True and consent["plans_for_this_child"] == 0
        session = SessionLocal()
        try:
            assert int(session.scalar(select(RealPlayer.age).where(RealPlayer.slug == child))) < edu.MINOR_AGE
        finally:
            session.close()


def _minors_rows() -> list[Any]:
    session = SessionLocal()
    try:
        return list(session.scalars(select(RealPlayer).where(RealPlayer.age < edu.MINOR_AGE).order_by(RealPlayer.slug)).all())
    finally:
        session.close()


def _owner_of_elsewhere(ident: str) -> TestClient:
    other = _account("Owner Elsewhere")
    _opened(other, f"Unrelated {uuid4().hex[:6]} FC", kind="club")
    assert ident != other.get(CLUB).json()["items"][0]["slug"]
    return other


class TestAParentReadsTheirOwnChildOnly:
    """The same rows, redacted by the right that opened the door — and the redaction counts itself."""

    def test_a_parent_of_another_child_is_answered_with_a_plan_that_does_not_exist(self) -> None:
        owner, ident = _tenant("Other Family Academy")
        team = _team(owner, ident, "Under 16s")
        first, second = world_child(ident, owner, team["name"], 0), world_child(ident, owner, team["name"], 1)
        one, two = _joined(owner, ident, "parent", "Parent One"), _joined(owner, ident, "parent", "Parent Two")
        _grant(one, ident, first)
        _grant(two, ident, second)
        plan = _plan(owner, ident, first)["id"]
        refused = two.get(f"{ACADEMY}/{ident}/plans/{plan}")
        assert refused.status_code == 404 and _detail(refused)["code"] == "no_such_plan"
        # `plan` is the caller's own string and comes back in the message; what must not appear is anything
        # the row resolved to — the child this plan belongs to, or the guardian who answered for them.
        assert first not in refused.text and _email_of(one) not in refused.text, "a 403 would confirm the row is real"
        assert [item["player"]["slug"] for item in two.get(f"{ACADEMY}/{ident}/plans").json()["items"]] == []

    def test_a_parent_with_no_claim_gets_an_empty_list_rather_than_a_refusal(self) -> None:
        owner, ident = _tenant("No Claim Academy")
        _team(owner, ident, "Under 16s")
        waiting = _joined(owner, ident, "parent", "Waiting Parent")
        listing = waiting.get(f"{ACADEMY}/{ident}/plans").json()
        assert listing["items"] == [] and listing["total"] == 0
        assert listing["read_through"] == "plan.read_own_child" and "empty list" in listing["rule"]
        # One door, one shape. The web page reads `formulas` and `limit` off every answer this door gives, and
        # the empty-guardian branch used to omit them: the door was 200 and the page was a 500, which is the
        # same claim stated in two languages disagreeing. The sentences may differ; the keys may not.
        staff = owner.get(f"{ACADEMY}/{ident}/plans").json()
        assert set(staff) == set(listing), f"the guardian's empty answer is short {sorted(set(staff) - set(listing))}"
        assert listing["formulas"] == staff["formulas"] and listing["limit"] == staff["limit"] and listing["minors_in_list"] == 0

    def test_feedback_a_chose_to_hold_back_is_counted_and_not_shown(self) -> None:
        owner, ident = _tenant("Held Feedback Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        guardian = _joined(owner, ident, "parent", "Feedback Guardian")
        _grant(guardian, ident, child)
        plan = _plan(owner, ident, child)["id"]
        shared = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/feedback", json={"message": "well done on the recovery runs"}).json()["feedback"]
        held = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/feedback", json={"message": "the private note about the captaincy", "shared_with_guardian": False}).json()["feedback"]
        assert held["shared_with_guardian"] is False and shared["shared_with_guardian"] is True
        staff = _read(owner, ident, plan)
        assert len(staff["feedback"]) == 2 and staff["withheld"]["coach_feedback"] == 0
        parent_view = _read(guardian, ident, plan)
        assert [row["message"] for row in parent_view["feedback"]] == ["well done on the recovery runs"]
        assert parent_view["withheld"]["coach_feedback"] == 1
        assert "captaincy" not in parent_view_text(parent_view)
        assert parent_view["withheld"]["rule"].startswith("a count, never a sentence")

    def test_footage_the_consent_did_not_cover_is_withheld_from_the_parent_and_kept_for_staff(self) -> None:
        owner, ident = _tenant("Held Video Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "Under 16s")
            child = world_child(ident, owner, team["name"], 0)
            guardian = _joined(owner, ident, "parent", "Video Guardian")
            _grant(guardian, ident, child)
            plan = _plan(owner, ident, child)["id"]
            refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": _clip_of(owner, session)["id"], "label": "the first touch", "t_start": 1, "t_end": 6})
            assert refused.status_code == 422 and _detail(refused)["code"] == "scope_not_consented"
            _grant(guardian, ident, child, ["plan", "assessment", "feedback", "video"])
            cited = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": _clip_of(owner, session)["id"], "label": "the first touch", "t_start": 1, "t_end": 6}).json()["evidence"]
            assert cited["window_seconds"] == 5.0 and cited["clip_present"] is True
            staff = _read(owner, ident, plan)
            assert len(staff["evidence"]) == 1 and staff["withheld"]["video_evidence"] == 0
            held = _grant(guardian, ident, child, ["plan"])
            assert held["scopes"] == ["plan"]
            parent_view = _read(guardian, ident, plan)
            assert parent_view["evidence"] == [] and parent_view["withheld"]["video_evidence"] == 1
            assert "video" in str(parent_view["withheld"]["why_video"])
        finally:
            session.close()

    def test_a_parents_standing_in_the_answer_names_the_role_and_the_scopes_held(self) -> None:
        owner, ident = _tenant("Standing Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        guardian = _joined(owner, ident, "parent", "Standing Guardian")
        _grant(guardian, ident, child)
        plan = _plan(owner, ident, child)["id"]
        assert _read(guardian, ident, plan)["your_standing"] == {
            "role": "parent",
            "staff": False,
            "guardian_of_this_child": True,
            "scopes_held": list(edu.DEFAULT_SCOPES),
            "read_through": "plan.read_own_child",
        }
        staff = _read(owner, ident, plan)["your_standing"]
        assert staff["role"] == "owner" and staff["staff"] is True and staff["read_through"] == "plan.read_all"

    def test_a_plan_keeps_the_age_it_was_written_at_and_says_when_that_no_longer_applies(self) -> None:
        owner, ident = _tenant("Grown Up Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        _grant(_joined(owner, ident, "parent", "Aged Guardian"), ident, child)
        plan = _plan(owner, ident, child)["id"]
        assert _read(owner, ident, plan)["aged_past_minority"] is False
        session = SessionLocal()
        try:
            row = session.scalar(select(RealPlayer).where(RealPlayer.slug == child))
            assert row is not None
            row.age = edu.MINOR_AGE + 1
            session.commit()
        finally:
            session.close()
        body = _read(owner, ident, plan)
        assert body["plan"]["age_at_open"] < edu.MINOR_AGE and body["plan"]["minor_at_open"] is True
        assert body["player"]["age"] == edu.MINOR_AGE + 1 and body["aged_past_minority"] is True
        session = SessionLocal()
        try:
            row = session.scalar(select(RealPlayer).where(RealPlayer.slug == child))
            assert row is not None
            row.age = edu.MINOR_AGE - 1
            session.commit()
        finally:
            session.close()


def parent_view_text(body: dict[str, Any]) -> str:
    import json

    return json.dumps(body, ensure_ascii=False)


class TestProgressIsArithmetic:
    """§40's Progress has no column: it is the difference between this plan's own reviews, printed with its sum."""

    def test_two_reviews_in_a_direction_and_the_sum_that_shows_it(self) -> None:
        owner, ident = _tenant("Progress Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(5))
        plan = _plan(owner, ident, _adult(5), **{"review_weeks": 4})["id"]
        _review(owner, ident, plan, PAST[2], {**FULL_RATINGS, "technique": 61})
        single = _read(owner, ident, plan)["progress"]
        # The claim that matters is the direction field itself: with one review there is nothing to subtract,
        # and a zero printed here would read as "flat" rather than "not measurable".
        assert single["one_review_is_not_a_direction"] is True and single["axis_change"] == {}
        assert single["overall_change"] is None and single["overall_first"] == single["overall_last"], "one review is not a direction"
        _review(owner, ident, plan, PAST[4], {**FULL_RATINGS, "technique": 68, "tactics": 44})
        progress = _read(owner, ident, plan)["progress"]
        assert progress["assessments"] == 2 and progress["one_review_is_not_a_direction"] is False
        assert progress["axis_change"]["technique"] == 7 and progress["axis_change"]["tactics"] == 4
        assert progress["axis_change"]["physical"] == 0
        assert progress["axis_means"]["technique"] == 64.5
        assert progress["span_days"] == (datetime.date.fromisoformat(PAST[4]) - datetime.date.fromisoformat(PAST[2])).days == 53
        assert progress["overall_change"] == 0, "both ends copy the world's rating of the day, so an unchanged player shows no movement"
        assert "copied" in progress["formulas"]["overall_change"]
        assert progress["not_a_column"].startswith("no figure here is stored")

    def test_an_axis_rated_at_one_end_only_has_no_direction_to_report(self) -> None:
        owner, ident = _tenant("Half Rated Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(6))
        plan = _plan(owner, ident, _adult(6))["id"]
        _review(owner, ident, plan, PAST[2])
        _review(owner, ident, plan, PAST[4], {"technique": 70})
        progress = _read(owner, ident, plan)["progress"]
        assert progress["axis_change"] == {"technique": 9}
        assert sorted(progress["axis_change_unrated_at_one_end"]) == ["competition_readiness", "mental", "physical", "tactics"]
        assert "cannot tell you about" in progress["formulas"]["axis_change"]

    def test_the_cadence_owes_a_review_for_every_window_since_the_plan_opened(self) -> None:
        owner, ident = _tenant("Cadence Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(7))
        plan = _plan(owner, ident, _adult(7), **{"review_weeks": 2})["id"]
        fresh = _read(owner, ident, plan)["progress"]
        assert fresh["assessments"] == 0 and fresh["days_since_review"] is None and fresh["due_in_days"] is None
        assert fresh["plan_days_open"] == 0 and fresh["reviews_due_by_cadence"] == 0 and fresh["reviews_behind"] == 0, "the day a plan opens is not yet a review it owes"
        _review(owner, ident, plan, PAST[0])
        # The debt is measured against the plan's own age, so opening the clock has to move the day the plan
        # opened — a history read only between its first review and its last could never report owing anything.
        session = SessionLocal()
        try:
            row = session.get(DevelopmentPlan, plan)
            assert row is not None
            row.created_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=120)
            session.commit()
        finally:
            session.close()
        progress = _read(owner, ident, plan)["progress"]
        assert progress["plan_days_open"] == 120 and progress["days_since_review"] == 120 and progress["due_in_days"] == 14 - 120
        assert progress["span_days"] == 0, "one review's distance to itself is nothing; the age is the other figure"
        assert progress["reviews_due_by_cadence"] == 120 // 14
        assert progress["reviews_behind"] == progress["reviews_due_by_cadence"] - 1
        assert "plan_days_open" in progress["formulas"]["reviews_due_by_cadence"]
        empty_book = SessionLocal()
        try:
            for assessment in empty_book.scalars(select(PlanAssessment).where(PlanAssessment.plan_id == plan)):
                empty_book.delete(assessment)
            empty_book.commit()
        finally:
            empty_book.close()
        empty = _read(owner, ident, plan)["progress"]
        assert (
            empty["assessments"] == 0 and empty["reviews_due_by_cadence"] == 120 // 14 and empty["reviews_behind"] == 120 // 14
        ), "a plan with no reviews at all still owes what its own age asked for"

    def test_a_review_deleted_underneath_the_plan_moves_the_figures_because_none_is_stored(self) -> None:
        owner, ident = _tenant("Deleted Review Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(8))
        plan = _plan(owner, ident, _adult(8))["id"]
        first = _review(owner, ident, plan, PAST[3], {**FULL_RATINGS, "technique": 50})
        _review(owner, ident, plan, PAST[4], {**FULL_RATINGS, "technique": 65})
        assert _read(owner, ident, plan)["progress"]["axis_change"]["technique"] == 15
        session = SessionLocal()
        try:
            row = session.get(PlanAssessment, first["id"])
            assert row is not None
            session.delete(row)
            session.commit()
        finally:
            session.close()
        after = _read(owner, ident, plan)["progress"]
        assert after["assessments"] == 1 and after["one_review_is_not_a_direction"] is True and after["axis_change"] == {}
        assert after["overall_change"] is None, "the door must not report a change it cannot measure"

    def test_a_review_is_refused_before_it_can_become_the_newest_number(self) -> None:
        owner, ident = _tenant("Back Date Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(9))
        plan = _plan(owner, ident, _adult(9))["id"]
        _review(owner, ident, plan, PAST[1])
        # `PAST[0]` is 120 days back and the review above is 90: the older date is the one that must be refused,
        # because accepting it would silently make the 90-day row the newest number on the plan.
        refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[0], "ratings": FULL_RATINGS})
        assert refused.status_code == 422 and _detail(refused)["code"] == "date_before_plan"
        assert _detail(refused)["newest"] == PAST[1] and _detail(refused)["assessments"] == 1
        future = (TODAY + datetime.timedelta(days=3)).isoformat()
        ahead = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": future, "ratings": FULL_RATINGS})
        assert _detail(ahead)["code"] == "date_in_future" and _detail(ahead)["today"] == TODAY.isoformat()
        shaped = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": "last tuesday", "ratings": FULL_RATINGS})
        assert _detail(shaped)["code"] == "date_shape" and _detail(shaped)["expected"] == "YYYY-MM-DD"
        impossible = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": "2026-13-40", "ratings": FULL_RATINGS})
        assert _detail(impossible)["code"] == "date_shape"

    def test_the_review_cap_is_one_more_than_the_book_holds(self) -> None:
        owner, ident = _tenant("Review Cap Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(10))
            plan_id = _plan(owner, ident, _adult(10))["id"]
            plan = session.get(DevelopmentPlan, plan_id)
            assert plan is not None
            session.add_all(
                [
                    PlanAssessment(
                        id=new_public_id("pas"),
                        plan_id=plan_id,
                        assessed_on=(TODAY - datetime.timedelta(days=edu.MAX_ASSESSMENTS_PER_PLAN + 2 - index)).isoformat(),
                        ratings=dict(FULL_RATINGS),
                        created_at=datetime.datetime.now(datetime.UTC),
                        updated_at=datetime.datetime.now(datetime.UTC),
                    )
                    for index in range(edu.MAX_ASSESSMENTS_PER_PLAN)
                ]
            )
            session.commit()
            refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan_id}/assessments", json={"assessed_on": TODAY.isoformat(), "ratings": FULL_RATINGS})
            assert refused.status_code == 422 and _detail(refused)["code"] == "assessment_limit"
            assert _detail(refused)["held"] == edu.MAX_ASSESSMENTS_PER_PLAN
        finally:
            session.close()


class TestNothingSensitiveIsStored:
    """§40's data-minimisation and privacy lines are columns and refusals, both of which are testable."""

    def test_the_published_column_list_is_the_tables_own(self) -> None:
        session = SessionLocal()
        try:
            for table, fields in edu.STORED_FIELDS.items():
                live = _live_column_names(session, table)
                assert live == set(fields), f"{table}: published {sorted(set(fields) ^ live)}"
        finally:
            session.close()

    def test_no_academy_table_has_a_column_for_anything_the_rulebook_forbids(self) -> None:
        forbidden = (
            "address",
            "postcode",
            "phone",
            "email",
            "birth",
            "dob",
            "location",
            "latitude",
            "longitude",
            "gps",
            "school",
            "medical",
            "injury",
            "diagnosis",
            "passport",
            "national_id",
            "photo",
        )
        session = SessionLocal()
        try:
            for table in edu.STORED_FIELDS:
                for column in _live_column_names(session, table):
                    for token in forbidden:
                        assert token not in column.lower(), f"{table}.{column} holds {token!r}"
        finally:
            session.close()

    def test_a_body_offering_a_forbidden_field_is_refused_and_the_words_do_not_come_back(self) -> None:
        owner, ident = _tenant("Forbidden Field Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        _grant(_joined(owner, ident, "parent", "Offering Guardian"), ident, child)
        refused = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": child, "home address": "12 Elm Street, PE1 1AAA", "date of birth": "2009-04-11"})
        assert refused.status_code == 422
        assert _validation(refused)["code"] == "validation_error"
        assert "Elm Street" not in refused.text and "2009-04-11" not in refused.text
        locations = {tuple(item["loc"]) for item in _validation(refused)["details"]}
        assert ("body", "home address") in locations and ("body", "date of birth") in locations
        for item in _validation(refused)["details"]:
            assert set(item) == {"type", "loc", "msg"}, item
        session = SessionLocal()
        try:
            assert session.scalar(select(func.count()).select_from(DevelopmentPlan).where(DevelopmentPlan.organization_id == _organization_id(session, ident))) == 0
        finally:
            session.close()

    def test_an_over_long_line_is_refused_with_both_figures_and_nothing_else(self) -> None:
        owner, ident = _tenant("Long Text Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(11))
        plan = _plan(owner, ident, _adult(11))["id"]
        # Past the service's cap and still inside the schema's own bound: the door's validator answers first, so
        # reaching `text_too_long` at all is what proves the service cap is a live cap and not a decoration.
        too_long = "x" * (edu.ASSESSMENT_TEXT_MAX + 40)
        assert edu.ASSESSMENT_TEXT_MAX < len(too_long) <= 800, "the schema bound is the ceiling above this test's ceiling"
        refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[4], "ratings": FULL_RATINGS, "strengths": too_long})
        assert refused.status_code == 422 and _detail(refused)["code"] == "text_too_long"
        detail = _detail(refused)
        assert detail["max"] == edu.ASSESSMENT_TEXT_MAX and detail["length"] == len(too_long)
        assert detail["field"] == "a strength line"
        # One code for every over-long field, because the code a caller branches on must not name the wrong fix.
        assert "feedback_limit" != detail["code"]
        absurd = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[4], "ratings": FULL_RATINGS, "strengths": "pressing" * 200})
        assert absurd.status_code == 422 and _validation(absurd)["code"] == "validation_error", "past the schema bound the service cap is never reached"
        long_feedback = "run" * (edu.FEEDBACK_MAX // 3 + 10)
        held = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/feedback", json={"message": long_feedback})
        assert _detail(held)["code"] == "text_too_long" and _detail(held)["field"] == "a feedback message"
        empty = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/feedback", json={"message": "   "})
        assert _detail(empty)["code"] == "feedback_required", "an empty note is not the same problem as too many notes"

    def test_an_axis_that_is_not_published_is_refused_by_name_and_a_rating_by_its_number(self) -> None:
        owner, ident = _tenant("Axis Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(12))
        plan = _plan(owner, ident, _adult(12))["id"]
        refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[4], "ratings": {"heading": 80, "technique": 60}})
        assert refused.status_code == 422 and _detail(refused)["code"] == "unknown_axis"
        assert _detail(refused)["axis"] == "heading" and _detail(refused)["axes"] == list(edu.AXES)
        for score in (150, -1):
            out = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[4], "ratings": {"technique": score}})
            assert _detail(out)["code"] == "rating_range"
            assert _detail(out)["value"] == score and _detail(out)["low"] == 0 and _detail(out)["high"] == 100
        none_rated = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[4], "ratings": {}})
        assert _detail(none_rated)["code"] == "unknown_axis" and "nothing" in _detail(none_rated)["message"]
        for score in (0, 100):
            assert owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[4], "ratings": {"technique": score}}).status_code == 200

    def test_a_rating_that_is_not_a_number_is_answered_by_the_schema_naming_the_axis(self) -> None:
        owner, ident = _tenant("Rating Shape Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(13))
        plan = _plan(owner, ident, _adult(13))["id"]
        refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/assessments", json={"assessed_on": PAST[4], "ratings": {"technique": "flourishing"}})
        assert refused.status_code == 422 and _validation(refused)["code"] == "validation_error"
        assert "flourishing" not in refused.text
        assert ("body", "ratings", "technique") in {tuple(item["loc"]) for item in _validation(refused)["details"]}

    def test_the_plan_answer_prints_what_it_promised_never_to_hold(self) -> None:
        owner, ident = _tenant("Never Held Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(14))
        body = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": _adult(14)}).json()
        for field in edu.RESTRICTED_FIELDS:
            assert field in body["not_stored"], field
        assert "there is no column here for any of them" in body["not_stored"]


class TestEvidenceCitesAndNeverServes:
    """Video evidence is a label and two numbers over somebody else's file — §40 lists footage as never default-public."""

    def test_a_clip_is_cited_with_its_window_and_the_citation_admits_it_is_not_a_way_to_watch(self) -> None:
        owner, ident = _tenant("Citation Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(15))
            plan = _plan(owner, ident, _adult(15))["id"]
            review = _review(owner, ident, plan, PAST[4])
            clip = _clip_of(owner, session, duration=40.0)
            body = owner.post(
                f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "label": "the first touch under pressure", "t_start": 2.5, "t_end": 9.5, "assessment": review["id"]}
            ).json()
            cited = body["evidence"]
            assert cited["t_start"] == 2.5 and cited["t_end"] == 9.5 and cited["window_seconds"] == 7.0
            assert cited["clip_present"] is True and cited["clip"]["duration_s"] == 40.0
            assert cited["assessment_id"] == review["id"]
            assert body["consented_by"] is None, "an adult's evidence needs no consent row, and the answer says so"
            assert "watch" in cited["playback"]
        finally:
            session.close()

    def test_somebody_elses_upload_answers_as_absent(self) -> None:
        owner, ident = _tenant("Foreign Clip Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(16))
            plan = _plan(owner, ident, _adult(16))["id"]
            other = _account("Another Uploader")
            clip = _clip_of(other, session)
            refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": 0, "t_end": 5})
            assert refused.status_code == 404 and _detail(refused)["code"] == "no_such_clip"
            assert _detail(refused)["reason"] == "owned_by_another_account"
            assert "u16 pressing drill" not in refused.text
        finally:
            session.close()

    def test_a_window_has_to_fit_the_footage_that_exists(self) -> None:
        owner, ident = _tenant("Window Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(17))
            plan = _plan(owner, ident, _adult(17))["id"]
            clip = _clip_of(owner, session, duration=12.0)
            backwards = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": 8, "t_end": 8})
            assert _detail(backwards)["code"] == "evidence_window" and _detail(backwards)["start"] == 8.0
            over = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": 0, "t_end": 30})
            assert _detail(over)["code"] == "evidence_window" and _detail(over)["duration"] == 12.0
            assert owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": 0, "t_end": 12}).status_code == 200
        finally:
            session.close()

    def test_two_windows_of_one_clip_are_two_looks_at_the_same_player(self) -> None:
        owner, ident = _tenant("Two Windows Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(18))
            plan = _plan(owner, ident, _adult(18))["id"]
            clip = _clip_of(owner, session, duration=60.0)
            assert owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": 0, "t_end": 8}).status_code == 200
            second = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": 30, "t_end": 38})
            assert second.status_code == 200, "a different window of the same clip is a different moment"
            assert second.json()["evidence_rows"] == 2
            duplicate = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": 0, "t_end": 8})
            assert duplicate.status_code == 409 and _detail(duplicate)["code"] == "already_linked"
            assert owner.get(f"{ACADEMY}/{ident}/plans/{plan}").json()["integrity"]["clean"] is True, "two windows must not light the integrity gate"
        finally:
            session.close()

    def test_a_citation_points_at_this_plans_review_and_no_other(self) -> None:
        owner, ident = _tenant("Foreign Review Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(19))
            plan = _plan(owner, ident, _adult(19))["id"]
            _sheet(owner, ident, team["name"], _adult(20))
            other_plan = owner.post(f"{ACADEMY}/{ident}/plans", json={"player": _adult(20)}).json()
            assert other_plan["plan"]["id"] != plan
            foreign = _review(owner, ident, other_plan["plan"]["id"], PAST[4])
            clip = _clip_of(owner, session)
            refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": 1, "t_end": 4, "assessment": foreign["id"]})
            assert refused.status_code == 404 and _detail(refused)["code"] == "no_such_assessment"
            assert _detail(refused)["plan"] == plan
        finally:
            session.close()

    def test_removing_a_citation_leaves_the_upload_and_the_window_measured(self) -> None:
        owner, ident = _tenant("Unlink Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(21))
            plan = _plan(owner, ident, _adult(21))["id"]
            clip = _clip_of(owner, session, duration=25.0)
            cited = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "label": "recovery run", "t_start": 3, "t_end": 11}).json()["evidence"]
            response = owner.delete(f"{ACADEMY}/{ident}/plans/{plan}/evidence/{cited['id']}")
            assert response.status_code == 200, response.text
            assert response.json()["deleted"] is True and "the clip stays" in response.json()["rule"]
            assert session.get(VideoAsset, clip["id"]) is not None
            assert session.scalar(select(func.count()).select_from(PlanVideoEvidence).where(PlanVideoEvidence.plan_id == plan)) == 0
            missing = owner.delete(f"{ACADEMY}/{ident}/plans/{plan}/evidence/pve_never_existed")
            assert missing.status_code == 404 and _detail(missing)["code"] == "no_such_evidence"
        finally:
            session.close()

    def test_a_deleted_clip_leaves_a_truthful_citation_behind(self) -> None:
        owner, ident = _tenant("Lost Clip Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(22))
            plan = _plan(owner, ident, _adult(22))["id"]
            clip = _clip_of(owner, session, duration=20.0)
            cited = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "label": "the second look", "t_start": 2, "t_end": 7}).json()["evidence"]
            asset = session.get(VideoAsset, clip["id"])
            assert asset is not None
            session.delete(asset)
            session.commit()
            after = _read(owner, ident, plan)["evidence"][0]
            assert after["id"] == cited["id"] and after["clip_present"] is False and after["clip"] is None
            assert after["window_seconds"] == 5.0, "what was seen on the day keeps its own measured window"
            counts = edu.academy_counts(session)
            assert counts["citations_without_clip"] >= 1 and counts["video_citations"] >= 1
        finally:
            session.close()

    def test_evidence_is_capped_and_the_cap_is_the_refusal_s_number(self) -> None:
        owner, ident = _tenant("Citation Cap Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(23))
            plan = _plan(owner, ident, _adult(23))["id"]
            clip = _clip_of(owner, session, duration=600.0)
            for index in range(edu.MAX_EVIDENCE_PER_PLAN):
                assert owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": index * 2, "t_end": index * 2 + 1}).status_code == 200
            refused = owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": 500, "t_end": 501})
            assert _detail(refused)["code"] == "evidence_limit" and _detail(refused)["limit"] == edu.MAX_EVIDENCE_PER_PLAN
        finally:
            session.close()


class TestErasureAndInventory:
    """§40's Deletion: a guardian can ask what is held and can have it removed, and both answers are counts."""

    def test_the_inventory_answers_what_do_you_hold_on_my_child_table_by_table(self) -> None:
        owner, ident = _tenant("Inventory Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "Under 16s")
            child = world_child(ident, owner, team["name"], 0)
            guardian = _joined(owner, ident, "parent", "Inventory Guardian")
            _grant(guardian, ident, child)
            plan = _plan(owner, ident, child)["id"]
            _review(owner, ident, plan, PAST[4])
            owner.post(f"{ACADEMY}/{ident}/plans/{plan}/feedback", json={"message": "one line"})
            body = guardian.get(f"{ACADEMY}/{ident}/players/{child}/data").json()
            assert body["held_by_this_tenant"] == {"development_plans": 1, "plan_assessments": 1, "coach_feedback": 1, "plan_video_evidence": 0, "guardian_consents": 1}
            assert body["total_rows"] == 4
            assert sorted(body["columns"]) == sorted(edu.STORED_FIELDS)
            assert body["never_stored"] == list(edu.RESTRICTED_FIELDS)
            assert body["seen_as"] == "guardian"
            assert "real_players" in body["outside_this_tenant"]["generated_world"]
            assert "uploaded" in body["outside_this_tenant"]["uploaded_clips"]
        finally:
            session.close()

    def test_an_erasure_without_confirmation_prints_the_counts_and_removes_nothing(self) -> None:
        owner, ident = _tenant("Dry Run Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        _grant(_joined(owner, ident, "parent", "Dry Guardian"), ident, child)
        plan = _plan(owner, ident, child)["id"]
        _review(owner, ident, plan, PAST[4])
        before = owner.get(f"{ACADEMY}/{ident}/players/{child}/data").json()["total_rows"]
        refused = owner.delete(f"{ACADEMY}/{ident}/players/{child}/data")
        assert refused.status_code == 422
        detail = _detail(refused)
        assert detail["code"] == "erase_confirmation" and detail["confirm_required"] is True
        assert detail["development_plans"] == 1 and detail["plan_assessments"] == 1 and detail["total"] == before
        assert owner.get(f"{ACADEMY}/{ident}/players/{child}/data").json()["total_rows"] == before

    def test_confirming_removes_every_row_of_the_child_and_none_of_the_world(self) -> None:
        owner, ident = _tenant("Erasure Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "Under 16s")
            child = world_child(ident, owner, team["name"], 0)
            guardian = _joined(owner, ident, "parent", "Erasing Guardian")
            _grant(guardian, ident, child, list(edu.SCOPES))
            plan = _plan(owner, ident, child)["id"]
            _review(owner, ident, plan, PAST[4])
            owner.post(f"{ACADEMY}/{ident}/plans/{plan}/feedback", json={"message": "a line to remove"})
            clip = _clip_of(owner, session)
            owner.post(f"{ACADEMY}/{ident}/plans/{plan}/evidence", json={"clip": clip["id"], "t_start": 1, "t_end": 4})
            body = owner.delete(f"{ACADEMY}/{ident}/players/{child}/data?confirm=true").json()
            assert body["before"] == {"development_plans": 1, "plan_assessments": 1, "coach_feedback": 1, "plan_video_evidence": 1, "guardian_consents": 1}
            assert set(body["after"].values()) == {0} and body["rows_removed"] == 5
            assert body["clips_unlinked"] == 1 and body["consents_removed"] == 1
            assert session.get(VideoAsset, clip["id"]) is not None, "the file belongs to the uploader, not to this tenant's erasure"
            assert session.scalar(select(func.count()).select_from(VideoAsset)) >= 1
            assert session.scalar(select(RealPlayer).where(RealPlayer.slug == child)) is not None
            members = int(
                session.scalar(
                    select(func.count())
                    .select_from(ClubTeamMember)
                    .join(ClubTeam, ClubTeam.id == ClubTeamMember.team_id)
                    .where(ClubTeam.organization_id == _organization_id(session, ident), ClubTeamMember.player_id == _player_id(session, child))
                )
                or 0
            )
            assert members == 1, "the sheet is §39's row and this door is not its owner"
            assert "the world" in body["not_touched"] and "uploaded clip" in body["not_touched"]
            missing = owner.get(f"{ACADEMY}/{ident}/players/{child}/data")
            assert missing.status_code == 200 and missing.json()["total_rows"] == 0
        finally:
            session.close()

    def test_a_guardian_may_erase_their_own_child_without_holding_the_erase_right(self) -> None:
        owner, ident = _tenant("Guardian Erasure Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        guardian = _joined(owner, ident, "parent", "Erasing Parent")
        _grant(guardian, ident, child)
        _plan(owner, ident, child)
        coach = _joined(owner, ident, "coach", "Coach Without Erase")
        assert access.may("coach", "plan.erase") is False and access.may("parent", "plan.erase") is False
        refused = coach.delete(f"{ACADEMY}/{ident}/players/{child}/data?confirm=true")
        assert refused.status_code == 403 and _detail(refused)["permission"] == "plan.erase"
        assert guardian.delete(f"{ACADEMY}/{ident}/players/{child}/data?confirm=true").status_code == 200
        assert owner.get(f"{ACADEMY}/{ident}/players/{child}/data").json()["total_rows"] == 0

    def test_a_parent_of_another_child_cannot_even_ask_what_is_held(self) -> None:
        owner, ident = _tenant("Blind Inventory Academy")
        team = _team(owner, ident, "Under 16s")
        first, second = world_child(ident, owner, team["name"], 0), world_child(ident, owner, team["name"], 1)
        one, two = _joined(owner, ident, "parent", "Parent A"), _joined(owner, ident, "parent", "Parent B")
        held = _grant(one, ident, first)
        _grant(two, ident, second)
        _plan(owner, ident, first)
        refused = two.get(f"{ACADEMY}/{ident}/players/{first}/data")
        assert refused.status_code == 404 and _detail(refused)["code"] == "no_such_player"
        # The slug comes back because this caller typed it; everything the door resolved stays behind the door.
        session = SessionLocal()
        try:
            person = session.get(RealPlayer, _player_id(session, first))
            assert person is not None
            assert person.name not in refused.text, "the answer echoes what was typed and reports nothing it looked up"
        finally:
            session.close()
        assert held["id"] not in refused.text

    def test_erasing_one_plan_leaves_the_consent_that_let_it_exist(self) -> None:
        owner, ident = _tenant("Plan Erasure Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "Under 16s")
            child = world_child(ident, owner, team["name"], 0)
            _grant(_joined(owner, ident, "parent", "Consent Survives"), ident, child)
            plan = _plan(owner, ident, child)["id"]
            _review(owner, ident, plan, PAST[4])
            refused = owner.delete(f"{ACADEMY}/{ident}/plans/{plan}")
            assert refused.status_code == 422 and _detail(refused)["code"] == "erase_confirmation"
            assert _detail(refused)["assessments"] == 1
            body = owner.delete(f"{ACADEMY}/{ident}/plans/{plan}?confirm=true").json()
            assert body["rows_removed"] == 1 and body["player"] == child
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(GuardianConsent)
                    .where(GuardianConsent.player_id == _player_id(session, child), GuardianConsent.organization_id == _organization_id(session, ident))
                )
                == 1
            )
            assert _plan_of(session, ident) is None
        finally:
            session.close()

    def test_one_tenants_erasure_is_not_another_tenants(self) -> None:
        owner, ident = _tenant("Shared Child Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        _grant(_joined(owner, ident, "parent", "Shared Guardian"), ident, child)
        plan = _plan(owner, ident, child)["id"]
        _review(owner, ident, plan, PAST[4])
        elsewhere = _tenant("Other Academy", owner="Owner Of The Other")
        other_team = _team(elsewhere[0], elsewhere[1], "Under 16s")
        other_child = world_child(elsewhere[1], elsewhere[0], other_team["name"], 0)
        _grant(_joined(elsewhere[0], elsewhere[1], "parent", "The Other Guardian"), elsewhere[1], other_child)
        other_plan = _plan(elsewhere[0], elsewhere[1], other_child)["id"]
        assert owner.delete(f"{ACADEMY}/{ident}/players/{child}/data?confirm=true").status_code == 200
        session = SessionLocal()
        try:
            assert session.get(DevelopmentPlan, other_plan) is not None
            assert session.get(DevelopmentPlan, plan) is None
        finally:
            session.close()
        assert elsewhere[0].get(f"{ACADEMY}/{elsewhere[1]}/plans/{other_plan}").status_code == 200, "the other tenant's plan is untouched and still readable"


def _plan_of(session: Session, ident: str) -> Any:
    return session.scalar(select(DevelopmentPlan).join(Organization, Organization.id == DevelopmentPlan.organization_id).where(Organization.slug == ident))


class TestTheAcademyIntegrityGate:
    """§40's invariants, checked over the caller's own tenants — each one a way the consent rule could stop being true."""

    def test_a_well_run_academy_is_clean_and_says_what_it_counted(self) -> None:
        owner, ident = _tenant("Clean Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        _grant(_joined(owner, ident, "parent", "Clean Guardian"), ident, child)
        plan = _plan(owner, ident, child)["id"]
        _review(owner, ident, plan, PAST[4])
        body = _read(owner, ident, plan)["integrity"]
        assert body["clean"] is True and body["problems"] == []
        assert body["checked"] == {"organizations": 1, "plans": 1, "consent_rows": 1}
        assert body["rule"].startswith("every check here is one shape")

    def test_a_minor_s_plan_with_no_consent_behind_it_is_named(self) -> None:
        owner, ident = _tenant("Orphan Plan Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "Under 16s")
            child = world_child(ident, owner, team["name"], 0)
            _grant(_joined(owner, ident, "parent", "Revoked Later"), ident, child)
            plan = _plan(owner, ident, child, focus=["x"])
            # The door will not open without a granted row, so the breach is planted by withdrawing the yes
            # underneath a plan that is already running — the only way this invariant can actually break.
            _revoke_all(session, ident)
            body = _read(owner, ident, plan["id"])["integrity"]
            assert not body["clean"]
            assert any("no granted consent covering 'plan'" in problem for problem in body["problems"]), body["problems"]
        finally:
            session.close()

    def test_a_consent_that_names_a_purpose_this_tier_cannot_honour_is_reported(self) -> None:
        owner, ident = _tenant("Bad Consent Row Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "Under 16s")
            child = world_child(ident, owner, team["name"], 0)
            guardian = _joined(owner, ident, "parent", "Planting Guardian")
            _grant(guardian, ident, child)
            plan = _plan(owner, ident, child)["id"]
            row = session.scalar(select(GuardianConsent).where(GuardianConsent.player_id == _player_id(session, child), GuardianConsent.organization_id == _organization_id(session, ident)))
            assert row is not None
            row.scopes = ["plan", "photos"]
            row.state = "maybe"
            session.commit()
            problems = _read(owner, ident, plan)["integrity"]["problems"]
            assert any("naming ['photos']" in problem for problem in problems), problems
            assert any("consent state 'maybe'" in problem for problem in problems), problems
        finally:
            session.close()

    def test_a_rating_outside_the_published_scale_and_a_date_that_has_not_happened_are_both_found(self) -> None:
        owner, ident = _tenant("Planted Review Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(24))
            plan = _plan(owner, ident, _adult(24))["id"]
            review = _review(owner, ident, plan, PAST[4])
            row = session.get(PlanAssessment, review["id"])
            assert row is not None
            row.ratings = {"technique": 140, "aggression": 60}
            row.assessed_on = (TODAY + datetime.timedelta(days=30)).isoformat()
            session.commit()
            problems = _read(owner, ident, plan)["integrity"]["problems"]
            assert any("rated 'aggression', which is not one of the published axes" in problem for problem in problems), problems
            assert any("the technique rating is 140, outside the published 0 to 100" in problem for problem in problems), problems
            assert any("which has not happened yet" in problem for problem in problems), problems
        finally:
            session.close()

    def test_a_plan_aimed_at_another_tenants_curriculum_is_a_breach_and_says_so(self) -> None:
        owner, ident = _tenant("Aimed Plan Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(25))
            plan = _plan(owner, ident, _adult(25))["id"]
            elsewhere = _tenant("The Curriculum Owner", owner="Owner Of A Curriculum")
            foreign = _curriculum(elsewhere[0], elsewhere[1], "Somebody else's block")
            elsewhere = _tenant("The Team Owner", owner="Owner Of A Team Elsewhere")
            foreign_team = str(_team(elsewhere[0], elsewhere[1], "Under 18s")["id"])
            row = session.get(DevelopmentPlan, plan)
            assert row is not None
            # Both ids are real rows that simply belong to somebody else. An unparseable id would trip the
            # foreign key on PostgreSQL and never reach the tenant check under test.
            row.curriculum_id = foreign["id"]
            row.team_id = foreign_team
            session.commit()
            problems = _read(owner, ident, plan)["integrity"]["problems"]
            assert any("its curriculum belongs to another tenant" in problem for problem in problems), problems
            assert any("its team belongs to another tenant" in problem for problem in problems), problems
        finally:
            session.close()

    def test_two_live_plans_for_one_child_appear_even_though_the_door_refuses_to_write_them(self) -> None:
        owner, ident = _tenant("Twin Plan Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "First Team")
            _sheet(owner, ident, team["name"], _adult(26))
            plan = _plan(owner, ident, _adult(26))["id"]
            twin = DevelopmentPlan(
                id=new_public_id("idp"),
                organization_id=_organization_id(session, ident),
                player_id=_player_id(session, _adult(26)),
                author_user_id=None,
                status="active",
                focus=[],
                goals=[],
                review_weeks=6,
                age_at_open=26,
                minor_at_open=False,
                created_at=datetime.datetime.now(datetime.UTC),
                updated_at=datetime.datetime.now(datetime.UTC),
            )
            session.add(twin)
            session.commit()
            problems = _read(owner, ident, plan)["integrity"]["problems"]
            assert any("plans that are not closed in one tenant" in problem for problem in problems), problems
        finally:
            session.close()

    def test_a_plan_whose_child_left_the_world_is_reported_rather_than_hidden(self) -> None:
        owner, ident = _tenant("Vanished Child Academy")
        session = SessionLocal()
        try:
            team = _team(owner, ident, "Under 16s")
            child = world_child(ident, owner, team["name"], 0)
            _grant(_joined(owner, ident, "parent", "Vanishing Guardian"), ident, child)
            _plan(owner, ident, child)
            row = session.scalar(select(RealPlayer).where(RealPlayer.slug == child))
            assert row is not None
            session.delete(row)
            session.commit()
            # The plan goes with the world's row, so what is left to test is the consent that now gates nothing.
            body = owner.get(f"{ACADEMY}/{ident}/consents").json()
            assert body["total"] == 0
        finally:
            session.close()


def _revoke_all(session: Session, ident: str) -> None:
    for row in session.scalars(select(GuardianConsent).where(GuardianConsent.organization_id == _organization_id(session, ident))):
        row.state = "withdrawn"
    session.commit()


class TestAcademyRowsAreIsolatedToo:
    """§39's sentence has to hold for rows §40 introduced, including when the id is real."""

    def test_a_plan_of_another_tenant_answers_as_one_that_does_not_exist(self) -> None:
        owner, ident = _tenant("Isolated Plan Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(27))
        plan = _plan(owner, ident, _adult(27))["id"]
        stranger = _account("Peeking Owner")
        elsewhere = str(_opened(stranger, "Peeking Academy", kind="academy")["organization"]["slug"])
        for method, url in [("get", f"{ACADEMY}/{elsewhere}/plans/{plan}"), ("patch", f"{ACADEMY}/{elsewhere}/plans/{plan}"), ("delete", f"{ACADEMY}/{elsewhere}/plans/{plan}")]:
            response = getattr(stranger, method)(url, **({} if method != "patch" else {"json": {"status": "paused"}}))
            assert response.status_code == 404, (method, response.text)
            assert _detail(response)["code"] == "no_such_plan"
            assert _email_of(owner) not in response.text, "a 404 on the wrong tenant's door must not name its owner"

    def test_a_curriculum_is_reachable_only_by_the_tenant_that_wrote_it(self) -> None:
        owner, ident = _tenant("Isolated Curriculum Academy")
        row = _curriculum(owner, ident, "Nobody else's block")
        stranger = _account("Curriculum Peeker")
        elsewhere = str(_opened(stranger, "Peeking Two Academy", kind="academy")["organization"]["slug"])
        refused = stranger.patch(f"{ACADEMY}/{elsewhere}/curricula/{row['id']}", json={"weekly_minutes": 30})
        assert refused.status_code == 404 and _detail(refused)["code"] == "no_such_curriculum"
        assert row["name"] not in refused.text
        assert stranger.get(f"{ACADEMY}/{elsewhere}/curricula").json()["items"] == []

    def test_an_id_that_exists_in_another_tenant_cannot_be_named_in_a_new_plan(self) -> None:
        owner, ident = _tenant("Aimed Id Academy")
        team = _team(owner, ident, "First Team")
        _sheet(owner, ident, team["name"], _adult(28))
        row = _curriculum(owner, ident, "A block to aim at")
        stranger = _account("Aimer")
        elsewhere = str(_opened(stranger, "Aiming Academy", kind="academy")["organization"]["slug"])
        other_team = _team(stranger, elsewhere, "First Team")
        _sheet(stranger, elsewhere, other_team["name"], _adult(29))
        refused = stranger.post(f"{ACADEMY}/{elsewhere}/plans", json={"player": _adult(29), "curriculum": row["id"]})
        assert refused.status_code == 404 and _detail(refused)["code"] == "no_such_curriculum"
        assert row["name"] not in refused.text

    def test_a_stranger_knocking_on_an_academy_door_gets_the_same_words_as_a_director_elsewhere(self) -> None:
        owner, ident = _tenant("Knock Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        boss = _account("Boss Elsewhere")
        unrelated = str(_opened(boss, "Elsewhere Sports School", kind="school")["organization"]["slug"])
        insider = _joined(boss, unrelated, "director", "Director Elsewhere")
        answers = []
        for caller in (insider, _account("Total Stranger")):
            response = caller.get(f"{ACADEMY}/{ident}/plans")
            assert response.status_code == 404 and _detail(response)["code"] == "no_such_organization"
            # The slug the caller typed comes back — it is their own string — and nothing the row resolved to does.
            assert "Knock Academy" not in response.text and _email_of(owner) not in response.text and child not in response.text
            answers.append(response.text)
        assert answers[0].replace(_email_of(insider), "X") == answers[1].replace(_email_of(insider), "X")
        anonymous = TestClient(app).get(f"{ACADEMY}/{ident}/players/{child}/data")
        assert anonymous.status_code in (401, 403), anonymous.text
        assert child not in anonymous.text and "development_plans" not in anonymous.text


class TestTheClosedDoorStillCounts:
    """The tier publishes its own readiness, so a page can say what it knows and what it cannot see."""

    def test_an_un_migrated_database_is_reported_not_assumed_sound(self, session: Session) -> None:
        assert edu.academy_tables_present(session) is True
        names = set(inspect(session.get_bind()).get_table_names())
        assert set(edu.STORED_FIELDS) <= names, "every published table has to exist before the door opens"

    def test_the_counts_move_with_writes_and_back_with_erasure(self) -> None:
        session = SessionLocal()
        try:
            before = edu.academy_counts(session)
        finally:
            session.close()
        owner, ident = _tenant("Counted Academy")
        team = _team(owner, ident, "Under 16s")
        child = world_child(ident, owner, team["name"], 0)
        _grant(_joined(owner, ident, "parent", "Counting Guardian"), ident, child)
        plan = _plan(owner, ident, child)["id"]
        _review(owner, ident, plan, PAST[4])
        owner.post(f"{ACADEMY}/{ident}/plans/{plan}/feedback", json={"message": "one", "shared_with_guardian": False})
        session = SessionLocal()
        try:
            after = edu.academy_counts(session)
        finally:
            session.close()
        assert after["plans"] == before["plans"] + 1
        assert after["plans_of_minors"] == before["plans_of_minors"] + 1
        assert after["assessments"] == before["assessments"] + 1
        assert after["consents_granted"] == before["consents_granted"] + 1
        assert after["feedback_held_from_guardian"] == before["feedback_held_from_guardian"] + 1
        owner.delete(f"{ACADEMY}/{ident}/players/{child}/data?confirm=true")
        session = SessionLocal()
        try:
            assert edu.academy_counts(session)["plans"] == before["plans"]
            assert edu.academy_counts(session)["consents_granted"] == before["consents_granted"]
        finally:
            session.close()
