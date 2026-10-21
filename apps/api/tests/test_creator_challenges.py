"""§36's fifth kind of content: a career challenge an entrant plays a career of their own under.

§36 lists six kinds of content a user can create. The fifth is a **Career Challenge** - an author
names an objective, a target and a window of rounds, and another account enters it with a career of
their own. The tier's rule holds here too: **a publication stores an address, never a copy**.

This file defends that rule from both sides:

* the column lists of both tables are the minimisation rule, asserted as sets: a challenge holds the
  author's words and the rule, an attempt holds the entrant's career address and the round its window
  opened at - no win, point, goal or verdict is stored anywhere;
* a verdict is summed from the entrant's own `career_fixtures` rows **on the read**, which the case
  proves the only way that counts: it edits one scratch fixture and watches the verdict move, and it
  proves rounds played before entry are outside the window;
* a target only earns once the window has closed, so a run that has already reached its target reads
  `in_progress` until the last round of the window is in;
* an attempt survives its career (a bare address, `career_missing`) and a challenge's erasure takes
  its attempts while leaving every career untouched;
* reach is §35's predicate, an unreachable challenge is **absence**, and this tier still answers no
  403 anywhere.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import new_public_id
from app.main import app
from app.models import (
    OBJECTIVE_FORMULA,
    OBJECTIVE_KINDS,
    Career,
    CareerFixture,
    CommunityFollow,
    CreatorCareerAttempt,
    CreatorCareerChallenge,
    User,
    utc_today,
)
from app.services.creator import challenges as cch
from app.services.creator.publishing import VISIBILITIES

PASSWORD = "TestPass1234!"


@pytest.fixture()
def session() -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _client(tag: str = "") -> TestClient:
    client = TestClient(app)
    email = f"challenge-{tag}{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": f"Challenge Tester {uuid4().hex[:6]}",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, f"registration failed: {response.text}"
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _user_id_of(client: TestClient) -> str:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return str(body["id"])


def _user(session: Session, name: str = "entrant") -> User:
    tag = uuid4().hex[:8]
    row = User(
        id=f"usr_{name}_{tag}"[:40],
        email=f"{name}-{tag}@creator.test",
        password_hash="not-a-password-just-a-column",
        display_name=f"{name} {tag}",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _career(
    session: Session,
    owner_id: str,
    *,
    rounds_played: int = 0,
    status: str = "active",
    challenge_window: int = 0,
) -> Career:
    tag = uuid4().hex[:10]
    row = Career(
        id=new_public_id("car"),
        slug=f"challenge-career-{tag}",
        owner_id=owner_id,
        manager_name="Scratch Manager",
        club_name="Scratch United",
        club_short="SCR",
        season="2025/26",
        philosophy="balanced",
        system_slug="",
        budget=10_000,
        objectives=[],
        rounds_played=rounds_played,
        status=status,
        challenge_window=challenge_window,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


_GOALS = {"W": (2, 0), "D": (1, 1), "L": (0, 1)}
_POINTS = {"W": 3, "D": 1, "L": 0}


def _fixture(session: Session, career_id: str, round_index: int, outcome: str) -> CareerFixture:
    club_goals, opponent_goals = _GOALS[outcome]
    row = CareerFixture(
        id=new_public_id("cf"),
        career_id=career_id,
        round_index=round_index,
        side="home",
        opponent_name="Scratch Rovers",
        opponent_short="SCR",
        venue_name="Scratch Park",
        club_goals=club_goals,
        opponent_goals=opponent_goals,
        outcome=outcome,
        points=_POINTS[outcome],
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _published(session: Session, author_id: str, **kwargs: Any) -> dict[str, Any]:
    params: dict[str, Any] = {
        "title": "A challenge",
        "objective": "wins",
        "target": 2,
        "window_rounds": 3,
    }
    params.update(kwargs)
    return cch.publish_career_challenge(session, author_id, **params)


def _refused(callable_: Any, code: str) -> cch.CreatorRefusal:
    with pytest.raises(cch.CreatorRefusal) as caught:
        callable_()
    assert caught.value.code == code, f"expected {code!r}, the door answered {caught.value.code!r}: {caught.value.message}"
    return caught.value


def _attempt_count(session: Session, challenge_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(CreatorCareerAttempt)
            .where(CreatorCareerAttempt.challenge_id == challenge_id)
        )
        or 0
    )


# ------------------------------------------------------------------ the shape of what is stored


def test_the_columns_a_challenge_and_an_attempt_store_are_the_minimisation_rule() -> None:
    """No column could hold an entrant's result; the only career fact is an address and an entry round."""
    challenged = {str(column.name) for column in CreatorCareerChallenge.__table__.columns}
    assert challenged == {
        "id",
        "author_id",
        "slug",
        "title",
        "summary",
        "visibility",
        "objective_kind",
        "target",
        "window_rounds",
        "published_on",
        "data_origin",
        "is_demo_data",
        "created_at",
        "updated_at",
    }, "a challenge is the author's words and the rule - never an entrant or a result"
    attempted = {str(column.name) for column in CreatorCareerAttempt.__table__.columns}
    assert attempted == {
        "id",
        "challenge_id",
        "account_id",
        "career_slug",
        "start_round",
        "created_at",
        "updated_at",
    }, "an attempt is the entrant's career address and the round its window opened at - and nothing else"
    forbidden = {
        "won",
        "drawn",
        "lost",
        "points",
        "goals_for",
        "goals_against",
        "goal_difference",
        "outcome",
        "club_goals",
        "opponent_goals",
        "result",
        "score",
        "verdict",
        "earned",
    }
    assert not (challenged | attempted) & forbidden, (
        f"{sorted((challenged | attempted) & forbidden)} would be a stored result rather than a rule and an address"
    )


def test_a_published_rule_is_read_back_as_the_author_s_own(session: Session) -> None:
    author = _user(session, "author")
    published = _published(
        session,
        author.id,
        title="Six points from three",
        summary="A short season, judged by its points.",
        objective="points",
        target=6,
        window_rounds=3,
    )
    assert published["objective"] == {
        "kind": "points",
        "target": 6,
        "formula": OBJECTIVE_FORMULA["points"],
    }, "the rule is published beside the formula M6 judges the same sum with"
    assert published["window_rounds"] == 3
    assert published["figures"] == {"attempts": 0}
    assert published["attempt"] is None, "a challenge read by its author shows no run until one is entered"
    assert published["rule"] == cch.LIMITATION
    assert set(published["formulas"]) == set(cch.FORMULAS)
    row = session.get(CreatorCareerChallenge, published["id"])
    assert row is not None and (row.objective_kind, row.target, row.window_rounds) == ("points", 6, 3)


def test_a_career_that_cannot_play_another_round_is_refused_at_entry(session: Session) -> None:
    """A retired career, or one whose own M6 window has closed, would open a window that can never close."""
    author = _user(session, "author")
    entrant = _user(session, "inactive")
    retired = _career(session, entrant.id, status="retired")
    closed = _career(session, entrant.id, rounds_played=4, challenge_window=4)
    challenge = _published(session, author.id)
    error = _refused(
        lambda: cch.enter_career_challenge(session, entrant.id, challenge["id"], career=retired.slug),
        "career_challenge_inactive",
    )
    assert error.figures == {
        "career": retired.slug,
        "status": "retired",
        "challenge_window": 0,
        "rounds_played": 0,
    }
    closed_error = _refused(
        lambda: cch.enter_career_challenge(session, entrant.id, challenge["id"], career=closed.slug),
        "career_challenge_inactive",
    )
    assert closed_error.figures["challenge_window"] == 4 and closed_error.figures["rounds_played"] == 4
    assert _attempt_count(session, challenge["id"]) == 0, "a refused entry writes no attempt"


# ------------------------------------------------------------------ the verdict, summed on the read


def test_the_verdict_is_summed_from_the_entrant_s_own_rows_inside_the_window(session: Session) -> None:
    """The only proof of *summed on read* and *the window opens at entry*: edit one row, watch it move."""
    author = _user(session, "author")
    entrant = _user(session, "runner")
    career = _career(session, entrant.id, rounds_played=2)
    _fixture(session, career.id, 1, "W")
    _fixture(session, career.id, 2, "W")
    challenge = _published(
        session, author.id, title="Six points in three", objective="points", target=6, window_rounds=3
    )
    entered = cch.enter_career_challenge(session, entrant.id, challenge["id"], career=career.slug)
    attempt = entered["attempt"]
    assert attempt["start_round"] == 2, "the window opens where the career stood at entry"
    assert attempt["window"] == {
        "start_round": 2,
        "end_round": 5,
        "rounds": 3,
        "played": 0,
        "remaining": 3,
        "closed": False,
    }
    assert attempt["actual"] == 0, "two wins played before entry are outside the window"
    assert attempt["status"] == "in_progress"
    assert attempt["rounds"] == []

    _fixture(session, career.id, 3, "W")
    _fixture(session, career.id, 4, "W")
    early = cch.read_career_challenge(session, challenge["id"], entrant.id)["attempt"]
    assert early["actual"] == 6 and early["target_met"] is True
    assert early["status"] == "in_progress" and early["earned"] is False, (
        "the target is reached, but a run is judged only when the window closes"
    )
    assert [row["outcome"] for row in early["rounds"]] == ["W", "W"]

    _fixture(session, career.id, 5, "L")
    closed = cch.read_career_challenge(session, challenge["id"], entrant.id)["attempt"]
    assert closed["window"]["played"] == 3 and closed["window"]["closed"] is True
    assert closed["actual"] == 6 and closed["status"] == "met" and closed["earned"] is True

    third = session.scalar(
        select(CareerFixture).where(
            CareerFixture.career_id == career.id, CareerFixture.round_index == 3
        )
    )
    assert third is not None
    third.outcome, third.points, third.club_goals, third.opponent_goals = "L", 0, 0, 3
    session.commit()
    missed = cch.read_career_challenge(session, challenge["id"], entrant.id)["attempt"]
    assert missed["actual"] == 3 and missed["status"] == "missed", (
        "nothing was stored, so editing one fixture row moves the verdict on the next read"
    )


def test_a_run_that_misses_its_target_reads_missed_when_the_window_closes(session: Session) -> None:
    author = _user(session, "author")
    entrant = _user(session, "loser")
    career = _career(session, entrant.id, rounds_played=0)
    for index, outcome in enumerate(("W", "W", "L"), start=1):
        _fixture(session, career.id, index, outcome)
    challenge = _published(session, author.id, objective="wins", target=3, window_rounds=3)
    entered = cch.enter_career_challenge(session, entrant.id, challenge["id"], career=career.slug)
    attempt = entered["attempt"]
    assert attempt["status"] == "missed" and attempt["earned"] is False
    assert attempt["actual"] == 2 and attempt["target"] == 3 and attempt["target_met"] is False
    assert "window closed after 3 of 3 rounds" in attempt["reason"]


def test_an_entrant_s_career_erased_after_entry_leaves_a_bare_address(session: Session) -> None:
    """The attempt keeps the address, and the read says so rather than summing nothing into a zero."""
    author = _user(session, "author")
    entrant = _user(session, "deleter")
    career = _career(session, entrant.id)
    slug = career.slug
    challenge = _published(session, author.id)
    entered = cch.enter_career_challenge(session, entrant.id, challenge["id"], career=career.slug)
    attempt_id = entered["attempt"]["id"]

    session.delete(career)
    session.commit()
    read = cch.read_career_challenge(session, challenge["id"], entrant.id)
    attempt = read["attempt"]
    assert attempt["id"] == attempt_id, "the attempt outlives the career it pinned"
    assert attempt["status"] == "career_missing"
    assert attempt["career"] == {
        "slug": slug,
        "manager_name": None,
        "club_name": None,
        "status": None,
        "path": None,
        "stored": False,
    }
    assert attempt["actual"] is None and attempt["rounds"] == []
    assert attempt["window"]["played"] is None and attempt["window"]["closed"] is False
    assert read["figures"]["attempts"] == 1
    assert session.get(CreatorCareerAttempt, attempt_id) is not None


def test_a_career_retired_mid_run_reads_as_retired_not_as_progress(session: Session) -> None:
    author = _user(session, "author")
    entrant = _user(session, "retiring")
    career = _career(session, entrant.id)
    _fixture(session, career.id, 1, "W")
    challenge = _published(session, author.id, objective="wins", target=1, window_rounds=3)
    cch.enter_career_challenge(session, entrant.id, challenge["id"], career=career.slug)
    career.status = "retired"
    session.commit()
    attempt = cch.read_career_challenge(session, challenge["id"], entrant.id)["attempt"]
    assert attempt["status"] == "career_retired" and attempt["earned"] is False
    assert attempt["actual"] == 1 and attempt["career"]["status"] == "retired"
    assert "cannot close" in attempt["reason"]


# ------------------------------------------------------------------ entry, withdrawal and erasure


def test_an_unknown_or_foreign_career_is_the_same_absence_at_entry(session: Session) -> None:
    author = _user(session, "author")
    entrant = _user(session, "pinner")
    owner = _user(session, "owner")
    foreign = _career(session, owner.id)
    challenge = _published(session, author.id)
    unknown = _refused(
        lambda: cch.enter_career_challenge(session, entrant.id, challenge["id"], career="no-such-career"),
        "no_such_attempted_career",
    )
    assert unknown.figures == {"career": "no-such-career"}
    other = _refused(
        lambda: cch.enter_career_challenge(session, entrant.id, challenge["id"], career=foreign.slug),
        "no_such_attempted_career",
    )
    assert other.figures == {"career": foreign.slug}, "somebody else's career is answered as if it did not exist"
    assert _attempt_count(session, challenge["id"]) == 0


def test_a_second_entry_is_refused_with_the_first_run_s_own_figures(session: Session) -> None:
    author = _user(session, "author")
    entrant = _user(session, "twice")
    first = _career(session, entrant.id, rounds_played=1)
    _fixture(session, first.id, 1, "D")
    second = _career(session, entrant.id)
    challenge = _published(session, author.id)
    entered = cch.enter_career_challenge(session, entrant.id, challenge["id"], career=first.slug)
    error = _refused(
        lambda: cch.enter_career_challenge(session, entrant.id, challenge["id"], career=second.slug),
        "career_challenge_entered",
    )
    assert error.figures == {
        "attempt": entered["attempt"]["id"],
        "career": first.slug,
        "start_round": 1,
    }
    assert _attempt_count(session, challenge["id"]) == 1, "the second entry wrote nothing"


def test_withdrawing_removes_the_run_and_leaves_the_career(session: Session) -> None:
    author = _user(session, "author")
    entrant = _user(session, "withdrawer")
    career = _career(session, entrant.id)
    challenge = _published(session, author.id)
    cch.enter_career_challenge(session, entrant.id, challenge["id"], career=career.slug)
    answer = cch.withdraw_career_challenge(session, entrant.id, challenge["id"])
    assert answer == {"status": "withdrawn", "challenge": challenge["id"], "career": career.slug}
    assert _attempt_count(session, challenge["id"]) == 0
    assert session.get(Career, career.id) is not None, "withdrawing a run never touches the career"
    _refused(
        lambda: cch.withdraw_career_challenge(session, entrant.id, challenge["id"]),
        "no_such_career_attempt",
    )


def test_erasing_a_challenge_takes_its_runs_and_leaves_the_careers(session: Session) -> None:
    author = _user(session, "author")
    entrant = _user(session, "runner")
    career = _career(session, entrant.id)
    challenge = _published(session, author.id)
    cch.enter_career_challenge(session, entrant.id, challenge["id"], career=career.slug)
    answer = cch.erase_career_challenge(session, author.id, challenge["id"])
    assert answer == {"status": "erased", "challenge": challenge["id"]}
    assert session.get(CreatorCareerChallenge, challenge["id"]) is None
    assert _attempt_count(session, challenge["id"]) == 0, "the runs on the challenge went with it"
    assert session.get(Career, career.id) is not None, "a challenge never takes its entrants' careers with it"
    _refused(
        lambda: cch.read_career_challenge(session, challenge["id"], entrant.id),
        "no_such_career_challenge",
    )


def test_another_account_s_challenge_is_absence_and_survives_the_attempt(session: Session) -> None:
    owner = _user(session, "owner")
    stranger = _user(session, "intruder")
    challenge = _published(session, owner.id, title="Not yours to erase")
    _refused(
        lambda: cch.erase_career_challenge(session, stranger.id, challenge["id"]),
        "no_such_career_challenge",
    )
    assert session.get(CreatorCareerChallenge, challenge["id"]) is not None, "the refusal wrote and erased nothing"


# ------------------------------------------------------------------ reach


def test_a_followers_challenge_reaches_exactly_the_accounts_following_its_author(session: Session) -> None:
    author = _user(session, "reach")
    stranger = _user(session, "stranger")
    challenge = _published(session, author.id, title="For my followers", visibility="followers")

    _refused(
        lambda: cch.read_career_challenge(session, challenge["id"], stranger.id),
        "no_such_career_challenge",
    )
    assert all(
        item["id"] != challenge["id"] for item in cch.list_career_challenges(session, stranger.id)["items"]
    )
    assert cch.list_career_challenges(session, stranger.id, creator=author.id)["total"] == 0
    assert cch.read_career_challenge(session, challenge["id"], author.id)["id"] == challenge["id"]

    row = CommunityFollow(
        id=new_public_id("fol"),
        follower_id=stranger.id,
        followee_id=author.id,
        followed_on=utc_today().isoformat(),
    )
    session.add(row)
    session.commit()
    assert cch.read_career_challenge(session, challenge["id"], stranger.id)["id"] == challenge["id"]
    assert [
        item["id"]
        for item in cch.list_career_challenges(session, stranger.id, creator=author.id)["items"]
    ] == [challenge["id"]]

    session.delete(row)
    session.commit()
    _refused(
        lambda: cch.read_career_challenge(session, challenge["id"], stranger.id),
        "no_such_career_challenge",
    )
    assert session.get(CreatorCareerChallenge, challenge["id"]) is not None, (
        "an unfollow withdraws the challenge and deletes nothing"
    )


def test_an_unlisted_challenge_is_readable_at_its_address_and_in_no_listing(session: Session) -> None:
    author = _user(session, "unlisted")
    stranger = _user(session, "reader")
    challenge = _published(session, author.id, title="Quietly shared", visibility="unlisted")
    assert cch.read_career_challenge(session, challenge["id"], stranger.id)["id"] == challenge["id"]
    assert all(
        item["id"] != challenge["id"] for item in cch.list_career_challenges(session, stranger.id)["items"]
    )


# ------------------------------------------------------------------ limits and vocabulary


def test_the_ceiling_refuses_one_past_it_with_its_own_figures(session: Session) -> None:
    author = _user(session, "ceiling")
    for index in range(cch.MAX_CAREER_CHALLENGES_PER_CREATOR):
        _published(session, author.id, title=f"A challenge {index}")
    error = _refused(
        lambda: _published(session, author.id, title="One too many"),
        "career_challenge_limit",
    )
    assert error.figures == {
        "challenges": cch.MAX_CAREER_CHALLENGES_PER_CREATOR,
        "max": cch.MAX_CAREER_CHALLENGES_PER_CREATOR,
    }


def test_the_open_words_and_the_rule_are_refused_with_the_vocabulary_they_broke(session: Session) -> None:
    author = _user(session, "words")
    blank = _refused(lambda: _published(session, author.id, title=""), "career_challenge_title")
    assert blank.figures["max"] == cch.CAREER_CHALLENGE_TITLE_MAX
    long_summary = _refused(
        lambda: _published(session, author.id, summary="x" * (cch.CAREER_CHALLENGE_SUMMARY_MAX + 1)),
        "career_challenge_summary",
    )
    assert long_summary.figures["max"] == cch.CAREER_CHALLENGE_SUMMARY_MAX
    visibility = _refused(
        lambda: _published(session, author.id, visibility="friends"),
        "career_challenge_visibility",
    )
    assert visibility.figures["visibilities"] == list(VISIBILITIES)
    objective = _refused(
        lambda: _published(session, author.id, objective="assists"),
        "career_challenge_objective",
    )
    assert objective.figures == {"sent": "assists", "kinds": list(OBJECTIVE_KINDS)}
    target = _refused(lambda: _published(session, author.id, target=0), "career_challenge_target")
    assert target.figures == {
        "target": 0,
        "min": cch.CAREER_CHALLENGE_TARGET_MIN,
        "max": cch.CAREER_CHALLENGE_TARGET_MAX,
    }
    window = _refused(
        lambda: _published(session, author.id, window_rounds=cch.CAREER_CHALLENGE_WINDOW_MAX + 1),
        "career_challenge_window",
    )
    assert window.figures["window"] == cch.CAREER_CHALLENGE_WINDOW_MAX + 1
    assert session.scalar(
        select(func.count())
        .select_from(CreatorCareerChallenge)
        .where(CreatorCareerChallenge.author_id == author.id)
    ) == 0, "a refused publication writes no rule"


def test_two_rules_from_one_author_are_held_apart_by_their_slugs(session: Session) -> None:
    author = _user(session, "slugger")
    _published(session, author.id, title="Same name")
    error = _refused(lambda: _published(session, author.id, title="Same name"), "slug_taken")
    assert error.figures == {"slug": "same-name"}


# ------------------------------------------------------------------ the doors


def test_the_rulebook_publishes_this_noun_s_vocabulary_and_its_doors(client: TestClient) -> None:
    client = _client("rules-")
    rules = client.get("/api/v1/creator/rules")
    assert rules.status_code == 200, rules.text
    body = rules.json()
    caps = body["career_challenge_caps"]
    assert caps["career_challenge_max"] == cch.MAX_CAREER_CHALLENGES_PER_CREATOR
    assert caps["career_challenge_target_max"] == cch.CAREER_CHALLENGE_TARGET_MAX
    assert caps["career_challenge_window_max"] == cch.CAREER_CHALLENGE_WINDOW_MAX
    assert body["career_challenge_objective_kinds"] == OBJECTIVE_FORMULA
    assert body["career_challenge_formulas"] == cch.FORMULAS
    assert set(body["career_challenge_counts"]) == {"career_challenges", "career_attempts"}
    assert body["career_challenge_rule"] == cch.LIMITATION
    assert body["refusal_answers"]["no_such_career_challenge"] == 404
    assert body["refusal_answers"]["no_such_career_attempt"] == 404
    assert body["refusal_answers"]["no_such_attempted_career"] == 404
    assert body["refusal_answers"]["career_challenge_target"] == 422
    assert body["refusal_answers"]["career_challenge_objective"] == 422
    assert body["refusal_answers"]["career_challenge_entered"] == 409
    assert body["refusal_answers"]["career_challenge_inactive"] == 409
    assert body["refusal_answers"]["career_challenge_limit"] == 409
    routed = {(route["method"], route["path"]) for route in body["routes"]}
    assert {
        ("POST", "/creator/challenges"),
        ("GET", "/creator/challenges"),
        ("GET", "/creator/challenges/{challenge}"),
        ("DELETE", "/creator/challenges/{challenge}"),
        ("POST", "/creator/challenges/{challenge}/enter"),
        ("DELETE", "/creator/challenges/{challenge}/enter"),
    } <= routed


def test_the_shelf_names_each_challenge_by_its_runs_and_marks_your_own_entry(client: TestClient) -> None:
    client = _client("shelf-")
    account = _user_id_of(client)
    with SessionLocal() as db:
        career = _career(db, account)
        career_slug = career.slug
    published = client.post(
        "/api/v1/creator/challenges",
        json={
            "title": "A shelf challenge",
            "summary": "Judged by wins.",
            "objective": "wins",
            "target": 1,
            "window_rounds": 2,
        },
    )
    assert published.status_code == 201, published.text
    challenge = published.json()
    entered = client.post(
        f"/api/v1/creator/challenges/{challenge['id']}/enter", json={"career": career_slug}
    )
    assert entered.status_code == 201, entered.text
    run = entered.json()["attempt"]
    assert run["status"] == "in_progress" and run["career"]["slug"] == career_slug
    assert run["start_round"] == 0 and run["target"] == 1

    shelf = client.get("/api/v1/creator/challenges", params={"creator": account})
    assert shelf.status_code == 200, shelf.text
    item = next(row for row in shelf.json()["items"] if row["id"] == challenge["id"])
    assert item["attempts"] == 1 and item["entered"] is True
    assert set(item) == {
        "id",
        "slug",
        "title",
        "summary",
        "visibility",
        "published_on",
        "author",
        "objective",
        "window_rounds",
        "attempts",
        "entered",
    }, "the shelf names the rule and the runs, and prints nothing about an entrant's career"
    assert career_slug not in str(item)

    stranger = _client("reader-")
    stranger_view = stranger.get(f"/api/v1/creator/challenges/{challenge['id']}")
    assert stranger_view.status_code == 200, stranger_view.text
    body = stranger_view.json()
    assert body["attempt"] is None, "another account's run is not part of a public challenge's read"
    assert body["figures"]["attempts"] == 1, "the number of runs is public; the career behind one is not"
    assert career_slug not in str(body)


def test_every_private_door_is_401_before_any_row_is_consulted() -> None:
    client = TestClient(app)
    for method, path in (
        ("post", "/api/v1/creator/challenges"),
        ("get", "/api/v1/creator/challenges"),
        ("get", "/api/v1/creator/challenges/ccc_nothing"),
        ("delete", "/api/v1/creator/challenges/ccc_nothing"),
        ("post", "/api/v1/creator/challenges/ccc_nothing/enter"),
        ("delete", "/api/v1/creator/challenges/ccc_nothing/enter"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401, f"{method.upper()} {path} answered {response.status_code}"
