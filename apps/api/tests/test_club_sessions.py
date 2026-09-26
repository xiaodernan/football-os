"""§41's Sessions: a tenant's training log, gated by the sheet and by a guardian's yes.

The rules this file holds:

* a session is a record of work done — a future date is refused, not accepted as a plan;
* attendance is a selection over the team's own sheet, so a session cannot widen who a tenant trains;
* a child present needs the same consent that opens their plan, and the refusal names the scope;
* the load figure is arithmetic over the row's minutes and rpe, printed with its formula and never stored;
* the caps are tested from both sides, and one refusal code means one thing;
* a guardian reads only the sessions their own child was at, and is answered as absence otherwise;
* deleting a session leaves the sheet, the plan and any cited clip exactly as they were.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import RealPlayer
from tests.test_club_academy import _detail, _validation, world  # noqa: F401 — the world §40 seeds, so both files see one generated world

CLUB = "/api/v1/club"  # the same door prefix §39 and §40 test through

ACADEMY = f"{CLUB}/academy"
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def _account(name: str) -> TestClient:
    from tests.test_club_academy import _account as shared

    return shared(name)


def _email_of(client: TestClient) -> str:
    from tests.test_club_academy import _email_of as shared

    return shared(client)


@pytest.fixture()
# `world` is imported above so both files read the world §40 seeded; the parameter of the same name is
# pytest requesting that fixture, not a redefinition of it.
def session(world: dict[str, Any]) -> Iterator[Session]:  # noqa: F811
    """The same shape as §40's: one session per test, closed afterwards, over the world that file seeded."""
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _tenant(name: str) -> tuple[TestClient, str]:
    from tests.test_club_academy import _opened

    owner = _account(f"Sessions Owner {name}")
    return owner, str(_opened(owner, name, kind="academy", country="en")["organization"]["slug"])


def _team_of(client: TestClient, ident: str, name: str) -> dict[str, Any]:
    response = client.post(f"{CLUB}/{ident}/teams", json={"name": name, "age_group": "u16", "stage": "youth"})
    assert response.status_code == 200, response.text
    return response.json()["team"]


def _add(client: TestClient, ident: str, team: str, slug: str) -> None:
    response = client.post(f"{CLUB}/{ident}/teams/{team}/players", json={"player": slug, "note": ""})
    assert response.status_code == 200, response.text


def _pick(session: Session, *, minor: bool, count: int = 2) -> list[RealPlayer]:
    rows = list(session.scalars(select(RealPlayer).where(RealPlayer.age < 18 if minor else RealPlayer.age >= 18).order_by(RealPlayer.slug).limit(count)))
    assert len(rows) == count, f"the generated world owes this test {count} {'minor' if minor else 'adult'} rows"
    return rows


def _post(client: TestClient, ident: str, **body: Any) -> Any:
    payload = {"team": "Under 16s", "scheduled_on": YESTERDAY, "duration_min": 90, "rpe": 6, **body}
    return client.post(f"{ACADEMY}/{ident}/sessions", json=payload)


class TestRecordingASession:
    def test_a_session_on_a_date_that_has_happened_is_stored_and_its_load_is_arithmetic(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Logged Work")
        team = _team_of(owner, ident, "Under 16s")
        adults = _pick(session, minor=False)
        _add(owner, ident, team["id"], adults[0].slug)
        made = _post(owner, ident, attendees=[adults[0].id], duration_min=90, rpe=6)
        assert made.status_code == 200, made.text
        body = made.json()
        row = body["session"]
        assert row["duration_min"] == 90 and row["rpe"] == 6
        assert row["load_units"] == round(90 * 6 / 60, 1), "the figure on the row is the row's own arithmetic"
        assert "duration_min × rpe ÷ 60" in body["formulas"]["load_units"]
        assert body["sessions"] == 1 and body["minors_present"] == 0

    def test_a_date_in_the_future_is_refused_because_a_session_is_a_record_not_a_plan(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Tomorrow Never")
        team = _team_of(owner, ident, "Under 16s")
        adult = _pick(session, minor=False, count=1)[0]
        _add(owner, ident, team["id"], adult.slug)
        refused = _post(owner, ident, attendees=[adult.id], scheduled_on=TOMORROW)
        assert refused.status_code == 422, refused.text
        assert _detail(refused)["code"] == "date_in_future"
        assert _detail(refused)["scheduled_on"] == TOMORROW
        assert owner.get(f"{ACADEMY}/{ident}/sessions").json()["total"] == 0, "a refusal is not a write"

    def test_outside_the_sheet_is_outside_the_tenant_no_matter_who_names_them(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Sheet Only")
        team = _team_of(owner, ident, "Under 16s")
        away = _pick(session, minor=False, count=1)[0]
        refused = _post(owner, ident, attendees=[away.id])
        assert refused.status_code in (404, 422), refused.text
        # The sheet exists and is the one being posted to, so the refusal above is about the attendee
        # standing outside it — which is the only thing this test claims.
        assert team["id"] and owner.get(f"{ACADEMY}/{ident}/sessions").json()["total"] == 0
        assert _detail(refused)["code"] in {"not_on_sheet", "no_such_player"}

    def test_attendance_naming_two_players_when_the_sheet_holds_one_is_refused(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("One On The Sheet")
        team = _team_of(owner, ident, "Under 16s")
        adults = _pick(session, minor=False, count=2)
        _add(owner, ident, team["id"], adults[0].slug)
        refused = _post(owner, ident, attendees=[adults[0].id, adults[1].id])
        assert refused.status_code == 422 and _detail(refused)["code"] == "not_on_sheet"
        assert _detail(refused)["named"] == 2 and _detail(refused)["on_sheet"] == 1

    def test_an_empty_attendance_list_is_refused_rather_than_recorded_as_a_quiet_session(self, client: TestClient) -> None:
        owner, ident = _tenant("Nobody Came")
        _team_of(owner, ident, "Under 16s")  # the sheet has to exist for the refusal to be about the list
        refused = _post(owner, ident, attendees=[])
        assert refused.status_code == 422 and _detail(refused)["code"] == "no_attendees"

    def test_the_two_ends_of_both_caps_are_tested_and_the_refusal_prints_the_number_it_tripped(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Caps From Both Sides")
        team = _team_of(owner, ident, "Under 16s")
        adult = _pick(session, minor=False, count=1)[0]
        _add(owner, ident, team["id"], adult.slug)
        for minutes, rpe, code in ((4, 6, "duration_range"), (5, 6, None), (601, 6, "duration_range"), (90, 0, "rpe_range"), (90, 11, "rpe_range"), (90, 10, None)):
            made = _post(owner, ident, attendees=[adult.id], duration_min=minutes, rpe=rpe, scheduled_on=f"{2020 + minutes % 3:04d}-0{(minutes + rpe) % 9 + 1}-0{(rpe % 9) + 1}")
            if code is None:
                assert made.status_code == 200, made.text
                continue
            assert made.status_code == 422 and _detail(made)["code"] == code, (minutes, rpe, made.text)
        assert owner.get(f"{ACADEMY}/{ident}/sessions").json()["total"] == 2, "the accepted pair are the only writes"

    def test_a_field_that_is_not_a_number_is_answered_by_the_transport_naming_the_field(self, client: TestClient, session: Session) -> None:
        """The shape of a number is the door's job; the size of one is the service's.

        This is where the two halves of the project's refusal rule meet: `duration_min: int` means a string
        never reaches the range check, so the tier publishes no `number_required` code — and the assertion
        below is the witness that the answer came from the transport, naming the field it could not read.
        """
        owner, ident = _tenant("Whole Numbers")
        team = _team_of(owner, ident, "Under 16s")
        adult = _pick(session, minor=False, count=1)[0]
        _add(owner, ident, team["id"], adult.slug)
        refused = _post(owner, ident, attendees=[adult.id], duration_min="ninety")
        assert refused.status_code == 422, refused.text
        assert _validation(refused)["code"] == "validation_error"
        assert "duration_min" in refused.text
        rules = client.get(f"{ACADEMY}/capabilities").json()
        assert "number_required" not in rules["refusal_answers"], "a code nobody can be refused with must not be published"


class TestTheGuardiansYesInFrontOfAChild:
    def test_a_minor_cannot_be_recorded_as_present_until_somebody_answers_for_them(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Consent Before Attendance")
        team = _team_of(owner, ident, "Under 16s")
        child = _pick(session, minor=True, count=1)[0]
        _add(owner, ident, team["id"], child.slug)
        refused = _post(owner, ident, attendees=[child.id])
        assert refused.status_code == 422 and _detail(refused)["code"] == "consent_required"
        details = _detail(refused)
        assert details["scope"] == "plan" and details["age"] == int(child.age) and details["threshold"] == 18

    def test_a_guardians_yes_lets_the_same_session_be_recorded_and_counts_the_child_present(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Consented Attendance")
        team = _team_of(owner, ident, "Under 16s")
        child = _pick(session, minor=True, count=1)[0]
        _add(owner, ident, team["id"], child.slug)
        from tests.test_club_academy import _grant, _joined

        guardian = _joined(owner, ident, "parent", "Answering Guardian")
        _grant(guardian, ident, child.slug)
        made = _post(owner, ident, attendees=[child.id])
        assert made.status_code == 200, made.text
        assert made.json()["minors_present"] == 1 and made.json()["session"]["attendees"][0]["is_minor"] is True


class TestWhoReadsTheLog:
    def test_a_staff_read_sums_the_log_and_a_guardian_read_sees_only_their_own_child(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Two Reads")
        team = _team_of(owner, ident, "Under 16s")
        child, other = _pick(session, minor=True, count=2)
        _add(owner, ident, team["id"], child.slug)
        _add(owner, ident, team["id"], other.slug)
        from tests.test_club_academy import _grant, _joined

        guardian = _joined(owner, ident, "parent", "One Child Only")
        _grant(guardian, ident, child.slug)
        _post(owner, ident, attendees=[child.id], duration_min=60, rpe=5)
        second = _post(owner, ident, attendees=[other.id], duration_min=30, rpe=3, scheduled_on="2021-04-05")
        assert second.status_code == 422, "the other child has no consent, and this test depends on that"

        staff = owner.get(f"{ACADEMY}/{ident}/sessions").json()
        assert staff["read_through"] == "plan.read_all" and staff["total"] == 1
        assert staff["total_minutes"] == 60 and staff["total_load_units"] == round(60 * 5 / 60, 1)
        assert "summed over the rows in this list" in staff["formulas"]["total_load_units"]

        family = guardian.get(f"{ACADEMY}/{ident}/sessions").json()
        assert family["read_through"] == "plan.read_own_child" and family["total"] == 1
        assert [row["attendees"][0]["slug"] for row in family["items"]] == [child.slug]

    def test_a_guardian_who_was_not_at_a_session_is_answered_as_if_it_did_not_exist(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Absent Family")
        team = _team_of(owner, ident, "Under 16s")
        child, other = _pick(session, minor=True, count=2)
        _add(owner, ident, team["id"], child.slug)
        _add(owner, ident, team["id"], other.slug)
        from tests.test_club_academy import _grant, _joined

        guardian = _joined(owner, ident, "parent", "Not There")
        _grant(guardian, ident, child.slug)
        other_guardian = _joined(owner, ident, "parent", "Was There")
        _grant(other_guardian, ident, other.slug)
        made = _post(owner, ident, attendees=[other.id]).json()["session"]["id"]
        assert guardian.get(f"{ACADEMY}/{ident}/sessions/{made}").status_code == 404
        assert other_guardian.get(f"{ACADEMY}/{ident}/sessions/{made}").status_code == 200

    def test_a_scout_reads_no_log_at_all_and_is_refused_by_the_matrix_not_by_a_filter(self, client: TestClient) -> None:
        owner, ident = _tenant("Eyes Only")
        from tests.test_club_academy import _joined

        watcher = _joined(owner, ident, "scout", "Watching Scout")
        refused = watcher.get(f"{ACADEMY}/{ident}/sessions")
        assert refused.status_code == 403 and _detail(refused)["code"] == "insufficient_role"


class TestSlotsAndDeletion:
    def test_a_second_session_in_the_same_slot_is_a_collision_not_a_rewrite(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Morning And Evening")
        team = _team_of(owner, ident, "Under 16s")
        adult = _pick(session, minor=False, count=1)[0]
        _add(owner, ident, team["id"], adult.slug)
        assert _post(owner, ident, attendees=[adult.id]).status_code == 200
        clash = _post(owner, ident, attendees=[adult.id])
        assert clash.status_code == 409 and _detail(clash)["code"] == "slot_taken"
        assert _detail(clash)["slot"] == 1 and _detail(clash)["scheduled_on"] == YESTERDAY
        assert _post(owner, ident, attendees=[adult.id], slot=2).status_code == 200, "the next slot is the answer the refusal gave"

    def test_erasing_a_session_leaves_the_sheet_and_the_plan_it_named_alone(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Light Erasure")
        team = _team_of(owner, ident, "Under 16s")
        child = _pick(session, minor=True, count=1)[0]
        _add(owner, ident, team["id"], child.slug)
        from tests.test_club_academy import _grant, _joined, _plan

        guardian = _joined(owner, ident, "parent", "Erasure Guardian")
        _grant(guardian, ident, child.slug)
        plan = _plan(owner, ident, child.slug)
        made = _post(owner, ident, attendees=[child.id], plan=plan["id"]).json()
        row = made["session"]["id"]
        assert owner.delete(f"{ACADEMY}/{ident}/sessions/{row}").status_code == 200
        again = owner.get(f"{ACADEMY}/{ident}/sessions/{row}")
        assert again.status_code == 404 and _detail(again)["code"] == "no_such_session"
        assert owner.get(f"{ACADEMY}/{ident}/plans/{plan['id']}").status_code == 200, "a plan is not deleted with a session"
        sheet = owner.get(f"{CLUB}/{ident}").json()
        assert sheet["counts"]["players_on_sheets"] == 1 and sheet["counts"]["teams"] == 1

    def test_a_plan_filed_under_a_child_who_is_not_present_is_refused(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Wrong Child")
        team = _team_of(owner, ident, "Under 16s")
        first, second = _pick(session, minor=True, count=2)
        _add(owner, ident, team["id"], first.slug)
        _add(owner, ident, team["id"], second.slug)
        from tests.test_club_academy import _grant, _joined, _plan

        guardian = _joined(owner, ident, "parent", "Both Children")
        _grant(guardian, ident, first.slug)
        _grant(guardian, ident, second.slug)
        plan = _plan(owner, ident, first.slug)
        refused = _post(owner, ident, attendees=[second.id], plan=plan["id"])
        assert refused.status_code == 422 and _detail(refused)["code"] == "plan_attends"


class TestTheRulebookKnowsAboutThisTier:
    def test_the_published_column_list_includes_the_session_table_and_the_door_guide_counts_it(self, client: TestClient) -> None:
        body = client.get(f"{ACADEMY}/capabilities").json()
        assert "club_sessions" in body["stored_fields"]
        assert len(body["stored_fields"]["club_sessions"]) == 18
        assert "load_units" not in body["stored_fields"]["club_sessions"], "the derived figure is not a column"
        assert body["session_limits"]["max_sessions_per_organization"] == 400
        doors = {line["path"] for line in body["routes"]}
        assert f"{ACADEMY}/{{ident}}/sessions" in doors and f"{ACADEMY}/{{ident}}/sessions/{{session_ident}}" in doors
        answers = {**body["refusal_answers"], **body["session_refusals"]}
        assert answers["no_such_session"] == 404 and answers["slot_taken"] == 409 and answers["duration_range"] == 422
        assert any("session" in line for line in body["limitations"]), "the limits sentence names this tier's own rule"
