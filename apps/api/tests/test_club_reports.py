"""§41's Reports: a saved question, answered from whatever the reader may see.

The rules this file holds:

* a report stores the question and no figure, so re-reading it after a correction prints the correction;
* the same saved report answers a director and a guardian differently, because the scope is applied at read time;
* an empty window says it is empty rather than printing a mean over nothing;
* an unknown kind is refused by name, with the kinds that do exist beside it;
* the window's own arithmetic is checked (reversed, too wide, mis-shaped) and each refusal prints its figures;
* re-asking the same question updates one row rather than stacking a second document;
* deleting a report removes the question and touches nothing it was asking about.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.test_club_academy import _detail, _grant as grant_other, _joined, session, world  # noqa: F401

CLUB = "/api/v1/club"
ACADEMY = f"{CLUB}/academy"


def _tenant(name: str) -> tuple[TestClient, str]:
    from tests.test_club_academy import _opened

    owner = _account(f"Reports Owner {name}")
    return owner, str(_opened(owner, name, kind="academy", country="en")["organization"]["slug"])


def _account(name: str) -> TestClient:
    from tests.test_club_academy import _account as shared

    return shared(name)


def _email_of(client: TestClient) -> str:
    from tests.test_club_academy import _email_of as shared

    return shared(client)


def _team_of(client: TestClient, ident: str, name: str) -> dict[str, Any]:
    response = client.post(f"{CLUB}/{ident}/teams", json={"name": name, "age_group": "u16", "stage": "youth"})
    assert response.status_code == 200, response.text
    return response.json()["team"]


def _add(client: TestClient, ident: str, team: str, player: str) -> None:
    response = client.post(f"{CLUB}/{ident}/teams/{team}/players", json={"player": player, "note": ""})
    assert response.status_code == 200, response.text


def _session_of(client: TestClient, ident: str, team: str, player: str, **body: Any) -> Any:
    payload = {"team": team, "scheduled_on": "2021-04-04", "duration_min": 60, "rpe": 5, "attendees": [player], **body}
    return client.post(f"{ACADEMY}/{ident}/sessions", json=payload)


def _ask(client: TestClient, ident: str, **body: Any) -> Any:
    payload = {"kind": "squad_load", "window_from": "2021-01-01", "window_to": "2021-12-31", **body}
    return client.post(f"{ACADEMY}/{ident}/reports", json=payload)


class TestAReportStoresTheQuestion:
    def test_a_squad_load_report_sums_the_sessions_in_its_window_and_prints_where_each_figure_came_from(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Load Reading")
        team = _team_of(owner, ident, "Under 16s")["name"]
        from app.models import RealPlayer

        adult = session.scalars(select(RealPlayer).where(RealPlayer.age >= 18).order_by(RealPlayer.slug)).first()
        assert adult is not None
        _add(owner, ident, team, adult.slug)
        assert _session_of(owner, ident, team, adult.id, duration_min=60, rpe=5).status_code == 200
        assert _session_of(owner, ident, team, adult.id, scheduled_on="2021-05-06", slot=2, duration_min=30, rpe=4).status_code == 200

        asked = _ask(owner, ident)
        assert asked.status_code == 200, asked.text
        body = asked.json()["report"]["body"]
        assert body["sessions"] == 2 and body["total_minutes"] == 90
        assert body["total_load_units"] == round(60 * 5 / 60 + 30 * 4 / 60, 1)
        assert body["mean_rpe"] == round((5 + 4) / 2, 2)
        assert body["figures_from"] == {"club_sessions": 2}
        assert "not stored" in asked.json()["rule"] or "re-summed" in asked.json()["rule"]
        assert asked.json()["report"]["asked_by"]["display_name"], "the row says who asked"

    def test_the_same_report_read_after_a_correction_prints_the_correction_because_nothing_was_frozen(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Re-Read The Same Row")
        team = _team_of(owner, ident, "Under 16s")["name"]
        from app.models import RealPlayer

        adult = session.scalars(select(RealPlayer).where(RealPlayer.age >= 18).order_by(RealPlayer.slug)).first()
        _add(owner, ident, team, adult.slug)
        _session_of(owner, ident, team, adult.id, duration_min=60, rpe=5)
        report = _ask(owner, ident).json()["report"]["id"]

        assert owner.get(f"{ACADEMY}/{ident}/reports/{report}").json()["report"]["body"]["total_minutes"] == 60
        _session_of(owner, ident, team, adult.id, scheduled_on="2021-07-09", duration_min=45, rpe=2)
        after = owner.get(f"{ACADEMY}/{ident}/reports/{report}").json()
        assert after["report"]["body"]["total_minutes"] == 105, "a report is a read, not a saved document"
        assert after["generated_on"], "and the answer says when it was computed"

    def test_a_window_with_nothing_in_it_says_so_and_prints_no_mean_over_nothing(self, client: TestClient) -> None:
        owner, ident = _tenant("An Empty Quarter")
        _team_of(owner, ident, "Under 16s")
        asked = _ask(owner, ident, window_from="2019-01-01", window_to="2019-03-31")
        assert asked.status_code == 200, asked.text
        body = asked.json()["report"]["body"]
        assert body["sessions"] == 0 and body["empty_window"] is True
        assert body["mean_rpe"] is None and body["total_minutes"] == 0
        assert body["most_worked"] is None, "no direction and no champion over an empty window"

    def test_asking_the_same_question_again_updates_one_row_rather_than_stacking_a_second_document(self, client: TestClient) -> None:
        owner, ident = _tenant("One Question Twice")
        first = _ask(owner, ident).json()["report"]["id"]
        second = _ask(owner, ident)
        assert second.status_code == 200 and second.json()["report"]["id"] == first
        assert second.json()["reports"] == 1 and owner.get(f"{ACADEMY}/{ident}/reports").json()["total"] == 1


class TestWhatAReportRefuses:
    def test_a_reading_this_tier_cannot_produce_is_refused_by_name_with_the_ones_it_can_printed(self, client: TestClient) -> None:
        owner, ident = _tenant("No Such Reading")
        refused = _ask(owner, ident, kind="xg_by_halfspace")
        assert refused.status_code == 422 and _detail(refused)["code"] == "unknown_kind"
        assert refused.json() and set(_detail(refused)["kinds"]) == {"squad_load", "consent_gap"}
        assert _detail(refused)["kind"] == "xg_by_halfspace"

    def test_a_window_that_runs_backwards_is_refused_with_both_of_its_dates(self, client: TestClient) -> None:
        owner, ident = _tenant("Yesterday To Last Year")
        refused = _ask(owner, ident, window_from="2021-08-08", window_to="2021-02-02")
        assert refused.status_code == 422 and _detail(refused)["code"] == "window_reversed"
        assert _detail(refused)["window_from"] == "2021-08-08" and _detail(refused)["window_to"] == "2021-02-02"

    def test_a_window_wider_than_the_published_one_is_refused_with_the_days_it_was_given(self, client: TestClient) -> None:
        owner, ident = _tenant("A Decade")
        refused = _ask(owner, ident, window_from="2010-01-01", window_to="2020-12-31")
        assert refused.status_code == 422 and _detail(refused)["code"] == "window_too_wide"
        assert _detail(refused)["max"] == 366 and _detail(refused)["days"] > 366

    def test_a_kind_that_is_a_stored_figure_is_impossible_because_the_body_is_not_a_column(self, client: TestClient) -> None:
        rules = client.get(f"{ACADEMY}/capabilities").json()
        assert "club_reports" in rules["stored_fields"] and len(rules["stored_fields"]["club_reports"]) == 11
        assert not [name for name in rules["stored_fields"]["club_reports"] if "figure" in name or "body" in name or "payload" in name]
        assert rules["report_kinds"] == ["squad_load", "consent_gap"]
        assert rules["report_refusals"]["no_such_report"] == 404 and rules["report_refusals"]["unknown_kind"] == 422
        assert any("report stores the question" in line for line in rules["limitations"])


class TestWhoMayAskAndRead:
    def test_a_guardian_reads_the_same_report_as_a_smaller_tenant_than_the_director_who_saved_it(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Two Readers One Question")
        team = _team_of(owner, ident, "Under 16s")["name"]
        from app.models import RealPlayer

        mine = session.scalars(select(RealPlayer).where(RealPlayer.age < 18).order_by(RealPlayer.slug)).first()
        theirs = session.scalars(select(RealPlayer).where(RealPlayer.age < 18, RealPlayer.slug != mine.slug).order_by(RealPlayer.slug)).first()
        _add(owner, ident, team, mine.slug)
        _add(owner, ident, team, theirs.slug)
        guardian = _joined(owner, ident, "parent", "Load Reader")
        grant_other(guardian, ident, mine.slug)
        assert _session_of(owner, ident, team, mine.id, duration_min=60, rpe=5).status_code == 200
        # The other child needs an answer too — a session cannot name a minor nobody has consented for, which
        # is exactly the gate §40 built and this report is read through. Somebody else gives it.
        other_guardian = _joined(owner, ident, "parent", "The Other Family")
        grant_other(other_guardian, ident, theirs.slug)
        assert _session_of(owner, ident, team, theirs.id, scheduled_on="2021-06-06", duration_min=40, rpe=9).status_code == 200

        report = _ask(owner, ident).json()["report"]["id"]
        director_view = owner.get(f"{ACADEMY}/{ident}/reports/{report}").json()["report"]["body"]
        family_view = guardian.get(f"{ACADEMY}/{ident}/reports/{report}").json()["report"]["body"]
        assert director_view["sessions"] == 2 and director_view["total_minutes"] == 100
        assert family_view["sessions"] == 1 and family_view["total_minutes"] == 60, "the window is the same question; the rows are what this reader may see"

    def test_a_scout_may_read_the_log_it_cannot_read_and_is_refused_by_the_matrix(self, client: TestClient) -> None:
        owner, ident = _tenant("Scout Asking")
        watcher = _joined(owner, ident, "scout", "Asking Scout")
        refused = watcher.post(f"{ACADEMY}/{ident}/reports", json={"kind": "squad_load", "window_from": "2021-01-01", "window_to": "2021-12-31"})
        assert refused.status_code == 403 and _detail(refused)["code"] == "insufficient_role"

    def test_the_consent_gap_reads_the_sheet_for_children_nobody_has_answered_for(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Gap On The Sheet")
        team = _team_of(owner, ident, "Under 16s")["name"]
        from app.models import RealPlayer

        minors = list(session.scalars(select(RealPlayer).where(RealPlayer.age < 18).order_by(RealPlayer.slug).limit(2)))
        for player in minors:
            _add(owner, ident, team, player.slug)
        guardian = _joined(owner, ident, "parent", "Gap Guardian")
        grant_other(guardian, ident, minors[0].slug)
        asked = _ask(owner, ident, kind="consent_gap")
        assert asked.status_code == 200, asked.text
        body = asked.json()["report"]["body"]
        assert body["minors_on_sheets"] == 2 and body["without_consent"] == 1
        assert [entry["slug"] for entry in body["waiting_for_an_answer"]] == [minors[1].slug]
        assert body["threshold"] == 18 and body["figures_from"]["guardian_consents"] >= 1

        family = guardian.get(f"{ACADEMY}/{ident}/reports").json()
        assert family["total"] == 1, "a guardian reads the tenant's saved question, and the answer they get is about their own child"
        assert family["items"][0]["body"]["minors_on_sheets"] == 1 and family["items"][0]["body"]["without_consent"] == 0

    def test_erasing_a_report_leaves_every_row_it_was_asking_about_alone(self, client: TestClient, session: Session) -> None:
        owner, ident = _tenant("Question Withdrawn")
        team = _team_of(owner, ident, "Under 16s")["name"]
        from app.models import RealPlayer

        adult = session.scalars(select(RealPlayer).where(RealPlayer.age >= 18).order_by(RealPlayer.slug)).first()
        _add(owner, ident, team, adult.slug)
        _session_of(owner, ident, team, adult.id)
        report = _ask(owner, ident).json()["report"]["id"]
        deleted = owner.delete(f"{ACADEMY}/{ident}/reports/{report}")
        assert deleted.status_code == 200 and deleted.json()["deleted"] is True and deleted.json()["reports"] == 0
        assert owner.get(f"{ACADEMY}/{ident}/reports/{report}").status_code == 404
        assert owner.get(f"{ACADEMY}/{ident}/sessions").json()["total"] == 1, "the sessions the report read are untouched"
        assert owner.get(f"{CLUB}/{ident}").json()["counts"]["players_on_sheets"] == 1
