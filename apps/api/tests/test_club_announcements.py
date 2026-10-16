"""§39's Communication row: a notice posted to an audience, and the receipts that say who read it.

The rules this file holds, and the shape of the tier they defend:

* an audience is a predicate over the tenant's active memberships, so `recipients` is arithmetic recomputed on
  every read — a revoked member leaves the denominator at once, and their old receipt stops being counted
  without being deleted, which is the difference between a derived figure and a stored one;
* a notice can never name a child: the door has no parameter that could, so §40's minimisation rule is the
  tier's shape rather than a check inside it;
* one receipt per account and notice, however many times it is marked;
* the ceiling is one constant that publishes, guards and refuses with the same number (§49's rule, applied
  before it could recur), and it is tested from both sides of its own edge;
* a pin is capped per board, because three pinned notices to `staff` and three to `parents` are two boards;
* every refusal code means exactly one HTTP answer at every door that can print it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import ClubAnnouncement, ClubAnnouncementRead, utc_today
from app.services.club import announcements as ann
from tests.test_club_academy import _detail, _joined, world  # noqa: F401 — the world §40 seeds, so every club file reads one generated world

CLUB = "/api/v1/club"
TODAY = utc_today().isoformat()


def _account(name: str) -> TestClient:
    from tests.test_club_academy import _account as shared

    return shared(name)


def _email_of(client: TestClient) -> str:
    from tests.test_club_academy import _email_of as shared

    return shared(client)


@pytest.fixture()
# `world` is imported above so the fixture parameter below is pytest requesting that fixture, not a shadow.
def session(world: dict[str, Any]) -> Iterator[Session]:  # noqa: F811
    """One session per test over the seeded world, closed afterwards — the same shape §40 and §41 use."""
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _tenant(name: str) -> tuple[TestClient, str]:
    from tests.test_club_academy import _opened

    owner = _account(f"Notice Owner {name}")
    return owner, str(_opened(owner, name, kind="academy", country="en")["organization"]["slug"])


def _board(client: TestClient, ident: str, **query: Any):
    return client.get(f"{CLUB}/{ident}/announcements", params=query or None)  # type: ignore[arg-type]


def _post(client: TestClient, ident: str, **body: Any):
    return client.post(f"{CLUB}/{ident}/announcements", json={"title": "Training moves to the indoor pitch", **body})


def _read(client: TestClient, ident: str, notice: str):
    return client.post(f"{CLUB}/{ident}/announcements/{notice}/read")


def _seed(session: Session, organization_id: str, *, count: int, audience: str = "members", pinned: bool = False) -> None:
    """Fill a board to a stated height, in the same rows the door writes.

    The cap on this tier is two hundred notices, which is far too many to post over HTTP inside a test: the
    rows go in through the model, and the *refusal* — the thing under test — still comes from the door.
    """
    for index in range(count):
        session.add(
            ClubAnnouncement(
                id=f"ann_seed_{index:04d}",
                organization_id=organization_id,
                audience=audience,
                title=f"Seeded notice {index}",
                body="",
                author_role="owner",
                pinned=pinned,
                published_on=TODAY,
            )
        )
    session.commit()


class TestAnAudienceIsAPredicate:
    def test_an_empty_board_answers_with_a_zero_and_the_ceiling_it_would_refuse_at(self) -> None:
        owner, ident = _tenant("Empty Board")
        body = _board(owner, ident).json()
        assert body["total"] == 0 and body["items"] == []
        assert body["limit"] == ann.MAX_ANNOUNCEMENTS_PER_ORGANIZATION
        assert body["announcements_held"] == 0
        assert body["pinned_by_audience"] == {name: 0 for name in ann.AUDIENCES}
        assert body["read_through"] == "announce.read" and body["today"] == TODAY

    def test_a_notice_selects_its_readers_from_the_roster_and_stores_nobody(self, session: Session) -> None:
        owner, ident = _tenant("Roster Selected")
        _joined(owner, ident, "parent", "Guardian Of One")
        posted = _post(owner, ident, title="Kit change", audience="parents")
        assert posted.status_code == 200, posted.text
        notice = posted.json()["announcement"]
        assert notice["recipients"] == 1 and notice["read_by"] == 0 and notice["unread"] == 1
        # The row holds the predicate, not a list of people: there is nothing here that could name a child.
        row = session.get(ClubAnnouncement, notice["id"])
        assert row is not None and row.audience == "parents" and not hasattr(row, "recipients") and not hasattr(row, "user_id")

    def test_staff_and_parents_are_two_predicates_over_the_one_roster(self) -> None:
        owner, ident = _tenant("Two Predicates")
        _joined(owner, ident, "coach", "Coach Of Two")
        _joined(owner, ident, "parent", "Guardian Of Two")
        staff = _post(owner, ident, title="Staff only", audience="staff").json()["announcement"]
        families = _post(owner, ident, title="For families", audience="parents").json()["announcement"]
        # `owner` and `coach` are staff; `parent` is not; and every role in the tenant is a member.
        assert staff["recipients"] == 2 and staff["unread"] == 2
        assert families["recipients"] == 1
        assert staff["id"] != families["id"]

    def test_an_unknown_audience_is_refused_and_names_the_three_it_knows(self) -> None:
        owner, ident = _tenant("Bad Audience")
        refused = _post(owner, ident, title="Whatever", audience="everyone")
        assert refused.status_code == 422, refused.text
        detail = _detail(refused)
        assert detail["code"] == "announcement_audience"
        assert sorted(detail["audiences"]) == sorted(ann.AUDIENCES)
        assert _board(owner, ident).json()["total"] == 0, "a refused notice must not reach the board"

    def test_the_filter_selects_the_notices_posted_to_one_audience_and_sees_selects_for_the_caller(self) -> None:
        """Two different questions, and the page publishes both: what was *addressed* to a word, and what one
        account's standing actually receives. A guardian receives a notice posted to `members` although no filter
        value would have returned it — which is why the second one is a list of ids rather than a filter."""
        owner, ident = _tenant("Filtered Board")
        guardian = _joined(owner, ident, "parent", "Guardian Filtering")
        posted = {_post(owner, ident, title=f"Notice to {name}", audience=name).json()["announcement"]["id"]: name for name in ann.AUDIENCES}
        assert len(posted) == 3
        board = _board(owner, ident).json()
        assert board["total"] == 3, "the whole board is listed to anyone who holds `announce.read`"
        for name in ann.AUDIENCES:
            one = _board(owner, ident, audience=name).json()
            assert one["total"] == 1 and one["items"][0]["audience"] == name
            assert one["announcements_held"] == 3, "the filter narrows the rows printed, not the tenant's holdings"
        seen = set(_board(guardian, ident).json()["sees"])
        assert seen == {key for key, name in posted.items() if name != "staff"}, "a parent receives everyone's notice and the families' one, and never a staff one"
        assert guardian.get(f"{CLUB}/{ident}/announcements/{[key for key, name in posted.items() if name == 'staff'][0]}").json()["addressed_to_caller"] is False
        wrong = _board(owner, ident, audience="nobody")
        assert wrong.status_code == 422 and _detail(wrong)["code"] == "announcement_audience"


class TestTheTextOfANotice:
    def test_a_blank_title_is_refused_because_a_board_of_blank_rows_tells_a_member_nothing(self) -> None:
        owner, ident = _tenant("Blank Title")
        for blank in ("", "   "):
            refused = _post(owner, ident, title=blank)
            assert refused.status_code == 422, refused.text
            assert _detail(refused)["code"] == "announcement_title"
        assert _board(owner, ident).json()["total"] == 0

    def test_a_title_one_character_over_the_published_cap_is_refused_with_both_figures(self) -> None:
        owner, ident = _tenant("Long Title")
        at_cap = _post(owner, ident, title="K" * ann.TITLE_MAX)
        assert at_cap.status_code == 200, at_cap.text
        over = _post(owner, ident, title="K" * (ann.TITLE_MAX + 1))
        assert over.status_code == 422, over.text
        detail = _detail(over)
        assert detail["code"] == "announcement_title"
        assert detail["length"] == ann.TITLE_MAX + 1 and detail["max"] == ann.TITLE_MAX
        assert _board(owner, ident).json()["total"] == 1, "only the notice at the cap was written"

    def test_a_body_past_the_cap_is_refused_and_a_body_at_it_is_stored_whole(self) -> None:
        owner, ident = _tenant("Long Body")
        assert _post(owner, ident, title="Within", body="x" * ann.BODY_MAX).status_code == 200
        over = _post(owner, ident, title="Beyond", body="x" * (ann.BODY_MAX + 1))
        assert over.status_code == 422, over.text
        detail = _detail(over)
        assert detail["code"] == "announcement_body" and detail["length"] == ann.BODY_MAX + 1
        assert _board(owner, ident).json()["items"][0]["body"] == "x" * ann.BODY_MAX


class TestTheCeilingAndTheBoard:
    def test_the_ceiling_accepted_at_its_edge_is_refused_one_past_it_with_its_own_figures(self, session: Session) -> None:
        owner, ident = _tenant("Full Board")
        slug = owner.get(f"{CLUB}/{ident}").json()["organization"]["id"]
        _seed(session, slug, count=ann.MAX_ANNOUNCEMENTS_PER_ORGANIZATION - 1)
        edge = _post(owner, ident, title="The two hundredth notice")
        assert edge.status_code == 200, edge.text
        assert edge.json()["announcements"] == ann.MAX_ANNOUNCEMENTS_PER_ORGANIZATION
        assert edge.json()["limit"] == ann.MAX_ANNOUNCEMENTS_PER_ORGANIZATION
        over = _post(owner, ident, title="One past the edge")
        assert over.status_code == 409, over.text
        detail = _detail(over)
        assert detail["code"] == "announcement_limit"
        assert detail["held"] == ann.MAX_ANNOUNCEMENTS_PER_ORGANIZATION == detail["limit"]
        assert _board(owner, ident).json()["total"] == ann.MAX_ANNOUNCEMENTS_PER_ORGANIZATION

    def test_a_pin_is_capped_per_board_because_two_audiences_are_two_boards(self) -> None:
        owner, ident = _tenant("Pinned Twice")
        for index in range(ann.PINNED_MAX):
            assert _post(owner, ident, title=f"Pinned {index}", audience="staff", pinned=True).status_code == 200
        fourth = _post(owner, ident, title="One pin too far", audience="staff", pinned=True)
        assert fourth.status_code == 409, fourth.text
        detail = _detail(fourth)
        assert detail["code"] == "pinned_limit" and detail["pinned"] == ann.PINNED_MAX and detail["max"] == ann.PINNED_MAX
        # The same tenant, the same ceiling, a different audience: nothing about `parents` is full yet.
        assert _post(owner, ident, title="Pinned for families", audience="parents", pinned=True).status_code == 200
        assert _board(owner, ident).json()["pinned_by_audience"] == {"members": 0, "staff": ann.PINNED_MAX, "parents": 1}


class TestAReceiptIsAFact:
    def test_marking_a_notice_read_twice_is_one_row_and_the_second_says_so(self, session: Session) -> None:
        owner, ident = _tenant("Read Twice")
        coach = _joined(owner, ident, "coach", "Coach Reader")
        notice = _post(owner, ident, title="Grounds closed", audience="staff").json()["announcement"]["id"]
        first = _read(coach, ident, notice).json()
        assert first["recorded_now"] is True and first["announcement"]["read_by"] == 1 and first["announcement"]["read"] is True
        second = _read(coach, ident, notice).json()
        assert second["recorded_now"] is False and second["receipt"] == "already recorded"
        assert second["announcement"]["read_by"] == 1, "a receipt re-marked must not count twice"
        rows = list(session.scalars(select(ClubAnnouncementRead).where(ClubAnnouncementRead.announcement_id == notice)))
        assert len(rows) == 1 and rows[0].read_on == TODAY
        # And the row the *author* reads is their own: an author is an audience member who has not read it.
        mine = _board(owner, ident).json()["items"][0]
        assert mine["read_by"] == 1 and mine["unread"] == 1 and mine["read"] is False

    def test_a_member_the_audience_does_not_select_cannot_leave_a_receipt_on_it(self) -> None:
        owner, ident = _tenant("Wrong Board")
        guardian = _joined(owner, ident, "parent", "Guardian Excluded")
        notice = _post(owner, ident, title="Staff meeting", audience="staff").json()["announcement"]["id"]
        refused = _read(guardian, ident, notice)
        assert refused.status_code == 422, refused.text
        detail = _detail(refused)
        assert detail["code"] == "not_an_audience" and detail["audience"] == "staff"
        assert _board(owner, ident).json()["items"][0]["read_by"] == 0
        # The door that answers it is still readable — a notice nobody in the audience can acknowledge is a
        # notice the tier would have no way to describe.
        assert _read(owner, ident, notice).status_code == 200

    def test_a_revoked_reader_leaves_the_denominator_without_deleting_their_receipt(self, session: Session) -> None:
        owner, ident = _tenant("Revoked Reader")
        guardian = _joined(owner, ident, "parent", "Guardian Leaving")
        notice = _post(owner, ident, title="Holiday schedule", audience="parents").json()["announcement"]["id"]
        assert _read(guardian, ident, notice).json()["announcement"]["recipients"] == 1
        revoke = owner.delete(f"{CLUB}/{ident}/members/{_email_of(guardian)}")
        assert revoke.status_code == 200, revoke.text
        after = _board(owner, ident).json()["items"][0]
        assert after["recipients"] == 0 and after["read_by"] == 0 and after["unread"] == 0
        assert after["receipts_on_row"] == 1, "the receipt is excluded by the arithmetic, not erased by the revocation"
        assert session.scalar(select(ClubAnnouncementRead).where(ClubAnnouncementRead.announcement_id == notice).limit(1)) is not None


class TestANoticeKeepsItsOwnWords:
    def test_the_author_role_is_the_one_held_at_publish_time_not_the_one_held_now(self) -> None:
        owner, ident = _tenant("Role Drift")
        coach = _joined(owner, ident, "coach", "Coach Demoted")
        notice = _post(coach, ident, title="Session moved", audience="staff").json()["announcement"]
        assert notice["author_role"] == "coach"
        assert owner.patch(f"{CLUB}/{ident}/members", json={"email": _email_of(coach), "role": "scout"}).status_code == 200
        held = coach.get(f"{CLUB}/{ident}/announcements/{notice['id']}").json()
        assert held["announcement"]["author_role"] == "coach", "a demotion must not rewrite who wrote a posted notice"
        assert held["role"] == "scout", "and the caller's own role is still read from the membership row"

    def test_erasing_a_notice_takes_its_receipts_and_leaves_the_roster_alone(self, session: Session) -> None:
        owner, ident = _tenant("Erased Notice")
        _joined(owner, ident, "coach", "Coach Erase")
        notice = _post(owner, ident, title="Cancelled", audience="staff").json()["announcement"]["id"]
        _read(owner, ident, notice)
        erased = owner.delete(f"{CLUB}/{ident}/announcements/{notice}")
        assert erased.status_code == 200, erased.text
        body = erased.json()
        assert body["erased"] == notice and body["receipts_removed"] == 1 and body["announcements"] == 0
        assert _board(owner, ident).json()["total"] == 0
        assert session.get(ClubAnnouncement, notice) is None
        assert list(session.scalars(select(ClubAnnouncementRead).where(ClubAnnouncementRead.announcement_id == notice))) == []
        assert len(_board(owner, ident).json()["items"]) == 0


class TestIsolationAndTheAnswerTable:
    def test_a_stranger_and_another_tenant_are_answered_as_absence_at_every_notice_door(self) -> None:
        owner, ident = _tenant("Privileged Board")
        notice = _post(owner, ident, title="Mine alone", audience="staff").json()["announcement"]["id"]
        stranger, other = _tenant("Unrelated Board")
        doors: list[tuple[str, str, dict[str, Any] | None]] = [
            ("get", f"{CLUB}/{ident}/announcements", None),
            ("post", f"{CLUB}/{ident}/announcements", {"title": "Not yours"}),
            ("get", f"{CLUB}/{ident}/announcements/{notice}", None),
            ("post", f"{CLUB}/{ident}/announcements/{notice}/read", None),
            ("delete", f"{CLUB}/{ident}/announcements/{notice}", None),
        ]
        for method, path, payload in doors:
            send = getattr(stranger, method)
            gone = send(path, json=payload) if payload is not None else send(path)
            assert gone.status_code == 404, f"{method!r} {path!r} answered {gone.status_code!r}, 404 was required; body: {gone.text[:200]!r}"
            assert _detail(gone)["code"] == "no_such_organization", f"{method!r} {path!r} refused with {_detail(gone)!r}, code no_such_organization was required"
        assert _board(owner, ident).json()["total"] == 1, "every foreign knock wrote nothing"

    def test_a_director_of_one_tenant_posts_nothing_on_another(self) -> None:
        owner, ident = _tenant("Board Under Watch")
        director, other = _tenant("Other Board")
        # `director` holds announce.write in their own tenant, which is exactly why this test must exist.
        assert _post(director, other, title="Allowed here", audience="staff").status_code == 200
        refused = _post(director, ident, title="Not allowed here", audience="staff")
        assert refused.status_code == 404, refused.text
        assert _board(owner, ident).json()["total"] == 0

    def test_the_rulebook_publishes_the_ceiling_the_door_applies(self, client: TestClient) -> None:
        body = client.get(f"{CLUB}/capabilities").json()
        caps = body["announcement_caps"]
        assert caps["announcement_max"] == ann.MAX_ANNOUNCEMENTS_PER_ORGANIZATION == ann.CAPS["announcement_max"]
        assert caps["pinned_max"] == ann.PINNED_MAX and caps["title_max"] == ann.TITLE_MAX and caps["body_max"] == ann.BODY_MAX
        assert caps["audiences"] == list(ann.AUDIENCES)
        assert body["announcement_formulas"] == dict(ann.FORMULAS)
        assert body["announcement_limitation"] == ann.LIMITATION
        assert "announcement_limit" in body["announcement_refusals"]

    def test_every_notice_refusal_means_one_http_answer_in_the_assembled_table(self) -> None:
        from fastapi import status

        from app.api.v1.club import _ANSWERS

        expected = {
            "no_such_announcement": status.HTTP_404_NOT_FOUND,
            "announcement_audience": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "announcement_title": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "announcement_body": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "not_an_audience": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "announcement_limit": status.HTTP_409_CONFLICT,
            "pinned_limit": status.HTTP_409_CONFLICT,
        }
        assert set(ann.REFUSALS) == set(expected) and set(ann.PUBLISHED) == set(expected)
        for code, answer in expected.items():
            assert _ANSWERS[code] == answer, code
        assert ann.FORBIDDEN_CODES == frozenset(), "403 stays the permission matrix's single meaning"
        assert set(ann.REFUSALS) == set(ann.NOT_FOUND_CODES | ann.UNPROCESSABLE_CODES | ann.CONFLICT_CODES | ann.FORBIDDEN_CODES)
