"""§36's fourth kind of content: a match analysis anchored to a played fixture, copying none of it.

§36 lists six kinds of content a user can create. The fourth is a **Match Analysis** - an author's
reading of a played match. The tier's rule for citations is the rule for this noun too: **a
publication stores an address, never a copy**.

This file defends that rule from both sides:

* the column list is the minimisation rule, asserted as a set: no column on
  `creator_match_analyses` could hold a score, a shot count or a sentence about the match;
* every measurement a read shows is computed from the match row's own stored score and `stats`
  **on that read**, and the case proves it the only way that counts: it edits the fixture and watches
  the analysis's answer move with it - equal to the world door's own match figures fed through the
  published formulas, not to a snapshot;
* the one thing stored about the match is a **witness**: the content address it carried when the
  analysis was written, so a refreshed fixture is still measurable and says `moved`, exactly as a
  citation's `cited_text_hash` does;
* the anchor is resolved at **publication**, so an analysis of a fixture the world does not hold -
  or of one that has not been played - is refused there rather than becoming a page with nothing to
  read;
* reach is §35's predicate (public / unlisted / followers), somebody else's analysis is **absence**,
  and this tier still answers no 403 anywhere.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import new_public_id
from app.main import app
from app.models import CommunityFollow, CreatorMatchAnalysis, RealMatch, Team, User, utc_today
from app.services.creator import matches as cma
from app.services.creator.publishing import VISIBILITIES

PASSWORD = "TestPass1234!"


@pytest.fixture(scope="module", autouse=True)
def _catalogue() -> None:
    """The world is stored by the app's boot; a service-level case needs it without a door."""
    from app.services.world import sync_world

    with SessionLocal() as db:
        sync_world(db)


@pytest.fixture()
def session() -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _client(tag: str = "") -> TestClient:
    client = TestClient(app)
    email = f"match-analysis-{tag}{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": f"Match Analysis Tester {uuid4().hex[:6]}",
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


def _user(session: Session, name: str = "analysis") -> User:
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


def _anchor(session: Session) -> RealMatch:
    row = session.scalar(
        select(RealMatch)
        .where(RealMatch.status == "completed", RealMatch.home_goals.is_not(None), RealMatch.away_goals.is_not(None))
        .order_by(RealMatch.slug)
        .limit(1)
    )
    assert row is not None, "the test database holds no played world fixture, so there is nothing to anchor to"
    return row


def _scratch_match(session: Session, *, status: str = "completed") -> RealMatch:
    """A world fixture of our own, so the revision case cannot disturb the generated catalogue."""
    teams = list(session.scalars(select(Team).order_by(Team.slug).limit(2)).all())
    assert len(teams) == 2, "the test database holds fewer than two clubs, so a fixture cannot be built"
    tag = uuid4().hex[:10]
    played = status == "completed"
    row = RealMatch(
        id=f"rmt_{tag}",
        slug=f"creator-match-{tag}",
        season="2025/26",
        competition_id=None,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        round_label="Test Round",
        kickoff_at=datetime(2026, 10, 1, 15, 0, tzinfo=UTC),
        venue_name="A Scratch Ground",
        venue_city="Testville",
        status=status,
        home_goals=3 if played else None,
        away_goals=1 if played else None,
        stats={
            "possession": {"home": 58.0, "away": 42.0},
            "shots": {"home": 12, "away": 7},
            "shots_on_target": {"home": 6, "away": 3},
            "passes": {"home": 480, "away": 390},
            "passes_accurate": {"home": 410, "away": 320},
            "discipline": {"home": 2, "away": 3},
        }
        if played
        else {},
        haystack="",
        summary="A scratch fixture written by a test.",
        content_hash=f"scratch-{tag}",
        data_origin="synthetic",
        is_demo_data=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _refused(callable_: Any, code: str) -> cma.CreatorRefusal:
    with pytest.raises(cma.CreatorRefusal) as caught:
        callable_()
    assert caught.value.code == code, f"expected {code!r}, the door answered {caught.value.code!r}: {caught.value.message}"
    return caught.value


def _expected(stats: dict[str, Any], home_goals: int, away_goals: int) -> dict[str, Any]:
    """The five published formulas, applied by the test to the world door's own match figures."""
    shots_home = stats["shots"]["home"]
    shots_away = stats["shots"]["away"]
    on_home = stats["shots_on_target"]["home"]
    on_away = stats["shots_on_target"]["away"]
    shots = shots_home + shots_away
    return {
        "total_goals": home_goals + away_goals,
        "goal_margin": abs(home_goals - away_goals),
        "shot_accuracy": round((on_home + on_away) / shots, 2) if shots else 0.0,
        "chance_conversion": round((home_goals + away_goals) / shots, 2) if shots else 0.0,
        "possession_edge": round(float(stats["possession"]["home"]) - float(stats["possession"]["away"]), 2),
    }


# ------------------------------------------------------------------ the shape of what is stored


def test_the_columns_a_match_analysis_stores_are_the_minimisation_rule() -> None:
    """No column could hold a score, a shot count or a sentence about the match it points at."""
    held = {str(column.name) for column in CreatorMatchAnalysis.__table__.columns}
    assert held == {
        "id",
        "author_id",
        "slug",
        "title",
        "summary",
        "visibility",
        "match_slug",
        "match_hash",
        "published_on",
        "data_origin",
        "is_demo_data",
        "created_at",
        "updated_at",
    }
    forbidden = {"metrics", "home_goals", "away_goals", "shots", "possession", "rating", "formula", "value", "stats"}
    assert not held & forbidden, f"{sorted(held & forbidden)} would be a copy of the match rather than an address"


def test_the_anchor_publishes_as_the_world_s_own_address(session: Session) -> None:
    match = _anchor(session)
    author = _user(session)
    published = cma.publish_match_analysis(
        session,
        author.id,
        match=match.id,
        title="Why the press broke in the second half",
        summary="A reading of the shots and the possession behind them.",
    )
    assert published["match"]["slug"] == match.slug, "an id on the way in is the slug on the way out"
    assert published["match"]["path"].endswith(f"/{match.slug}")
    assert published["title"] == "Why the press broke in the second half"
    row = session.get(CreatorMatchAnalysis, published["id"])
    assert row is not None and row.match_slug == match.slug
    assert row.match_hash == match.content_hash, "the witness is the address the match carried at publication"


def test_the_measurements_are_the_world_door_s_own_match_figures(client: TestClient) -> None:
    """The claim is *computed from the anchored columns*, so the case compares against the world's own read."""
    client = _client("same-")
    with SessionLocal() as db:
        match = _anchor(db)
        slug = match.slug
    published = client.post(
        "/api/v1/creator/matches",
        json={"match": slug, "title": "A reading of the result"},
    )
    assert published.status_code == 201, published.text
    analysis = published.json()

    detail = client.get(f"/api/v1/world/matches/{slug}")
    assert detail.status_code == 200, detail.text
    read = detail.json()["match"]
    assert {key: metric["value"] for key, metric in analysis["metrics"].items()} == _expected(
        read["stats"], read["home_goals"], read["away_goals"]
    ), "the analysis's numbers are the world door's match figures through the published formulas"
    assert set(analysis["metrics"]) == set(cma.METRIC_FORMULAS)
    assert all(metric["formula"] for metric in analysis["metrics"].values()), "a number without its formula is not a measurement here"


def test_editing_the_match_moves_the_analysis_and_it_says_so(session: Session) -> None:
    """The only proof of *computed on read*: change the fixture, and the same analysis answers differently."""
    match = _scratch_match(session)
    author = _user(session, "reviser")
    published = cma.publish_match_analysis(session, author.id, match=match.slug, title="A fixture that will change")
    before = cma.read_match_analysis(session, published["id"], author.id)
    assert before["moved"] is False, "an analysis written against the current revision has not moved"
    assert before["metrics"]["total_goals"]["value"] == 4
    assert before["metrics"]["shot_accuracy"]["value"] == round(9 / 19, 2)

    match.home_goals = 5
    match.away_goals = 2
    match.stats = {
        **match.stats,
        "shots": {"home": 20, "away": 10},
        "shots_on_target": {"home": 12, "away": 5},
        "possession": {"home": 61.5, "away": 38.5},
    }
    match.content_hash = f"revised-{uuid4().hex}"
    session.commit()

    after = cma.read_match_analysis(session, published["id"], author.id)
    assert after["moved"] is True, "the fixture's content address changed, so the analysis says it moved"
    assert after["metrics"]["total_goals"]["value"] == 7, "the measurement followed the score"
    assert after["metrics"]["goal_margin"]["value"] == 3
    assert after["metrics"]["shot_accuracy"]["value"] == round(17 / 30, 2)
    assert after["metrics"]["chance_conversion"]["value"] == round(7 / 30, 2)
    assert after["metrics"]["possession_edge"]["value"] == 23.0

    session.delete(session.get(RealMatch, match.id))
    session.commit()


def test_an_anchor_the_world_does_not_hold_is_refused_at_publication(session: Session) -> None:
    author = _user(session, "missing")
    error = _refused(
        lambda: cma.publish_match_analysis(session, author.id, match="no-such-fixture-anywhere", title="A reading of nobody"),
        "no_such_match",
    )
    assert error.figures["match"] == "no-such-fixture-anywhere"
    held = session.scalar(select(CreatorMatchAnalysis).where(CreatorMatchAnalysis.author_id == author.id))
    assert held is None, "a refused publication writes no row"


def test_a_fixture_that_has_not_been_played_is_refused_with_its_status(session: Session) -> None:
    author = _user(session, "scheduled")
    match = _scratch_match(session, status="scheduled")
    error = _refused(
        lambda: cma.publish_match_analysis(session, author.id, match=match.slug, title="A reading before kickoff"),
        "match_not_played",
    )
    assert error.figures == {"match": match.slug, "status": "scheduled"}
    held = session.scalar(select(CreatorMatchAnalysis).where(CreatorMatchAnalysis.author_id == author.id))
    assert held is None, "a fixture with no result has no analysis to publish"

    session.delete(match)
    session.commit()


def test_the_open_words_are_refused_with_the_vocabulary_they_broke(session: Session) -> None:
    author = _user(session, "words")
    blank = _refused(
        lambda: cma.publish_match_analysis(session, author.id, match=_anchor(session).slug, title=""),
        "match_title",
    )
    assert blank.figures["max"] == cma.MATCH_TITLE_MAX
    visibility = _refused(
        lambda: cma.publish_match_analysis(session, author.id, match=_anchor(session).slug, title="A reading", visibility="friends"),
        "match_visibility",
    )
    assert visibility.figures["visibilities"] == list(VISIBILITIES)


def test_the_ceiling_refuses_one_past_it_with_its_own_figures(session: Session) -> None:
    author = _user(session, "ceiling")
    slug = _anchor(session).slug
    for index in range(cma.MAX_MATCH_ANALYSES_PER_CREATOR):
        cma.publish_match_analysis(session, author.id, match=slug, title=f"A reading {index}")
    error = _refused(
        lambda: cma.publish_match_analysis(session, author.id, match=slug, title="One too many"),
        "match_limit",
    )
    assert error.figures == {"analyses": cma.MAX_MATCH_ANALYSES_PER_CREATOR, "max": cma.MAX_MATCH_ANALYSES_PER_CREATOR}


# ------------------------------------------------------------------ reach, absence and erasure


def test_a_followers_analysis_reaches_exactly_the_accounts_following_its_author(session: Session) -> None:
    author = _user(session, "reach")
    stranger = _user(session, "stranger")
    slug = _anchor(session).slug
    analysis = cma.publish_match_analysis(session, author.id, match=slug, title="For my followers", visibility="followers")

    _refused(lambda: cma.read_match_analysis(session, analysis["id"], stranger.id), "no_such_match_analysis")
    assert all(item["id"] != analysis["id"] for item in cma.list_match_analyses(session, stranger.id)["items"])
    assert cma.list_match_analyses(session, stranger.id, creator=author.id)["total"] == 0
    assert cma.read_match_analysis(session, analysis["id"], author.id)["id"] == analysis["id"]

    row = CommunityFollow(id=new_public_id("fol"), follower_id=stranger.id, followee_id=author.id, followed_on=utc_today().isoformat())
    session.add(row)
    session.commit()
    assert cma.read_match_analysis(session, analysis["id"], stranger.id)["id"] == analysis["id"]
    assert [item["id"] for item in cma.list_match_analyses(session, stranger.id, creator=author.id)["items"]] == [analysis["id"]]

    session.delete(row)
    session.commit()
    _refused(lambda: cma.read_match_analysis(session, analysis["id"], stranger.id), "no_such_match_analysis")
    assert session.get(CreatorMatchAnalysis, analysis["id"]) is not None, "an unfollow withdraws the analysis and deletes nothing"


def test_an_unlisted_analysis_is_readable_at_its_address_and_in_no_listing(session: Session) -> None:
    author = _user(session, "unlisted")
    stranger = _user(session, "reader")
    analysis = cma.publish_match_analysis(session, author.id, match=_anchor(session).slug, title="Quietly shared", visibility="unlisted")
    assert cma.read_match_analysis(session, analysis["id"], stranger.id)["id"] == analysis["id"], "its own address is the door"
    assert all(item["id"] != analysis["id"] for item in cma.list_match_analyses(session, stranger.id)["items"])


def test_another_accounts_analysis_is_answered_as_absence_and_survives_the_attempt(session: Session) -> None:
    owner = _user(session, "owner")
    stranger = _user(session, "intruder")
    analysis = cma.publish_match_analysis(session, owner.id, match=_anchor(session).slug, title="Not yours to erase")
    _refused(lambda: cma.erase_match_analysis(session, stranger.id, analysis["id"]), "no_such_match_analysis")
    assert session.get(CreatorMatchAnalysis, analysis["id"]) is not None, "the refusal wrote and erased nothing"


def test_erasing_an_analysis_leaves_the_fixture_untouched(session: Session) -> None:
    author = _user(session, "eraser")
    match = _anchor(session)
    analysis = cma.publish_match_analysis(session, author.id, match=match.slug, title="An analysis to withdraw")
    answer = cma.erase_match_analysis(session, author.id, analysis["id"])
    assert answer == {"status": "erased", "analysis": analysis["id"]}
    assert session.get(CreatorMatchAnalysis, analysis["id"]) is None
    assert session.get(RealMatch, match.id) is not None, "a reading never takes its subject with it"
    _refused(lambda: cma.read_match_analysis(session, analysis["id"], author.id), "no_such_match_analysis")


def test_a_retired_match_is_absence_at_the_address_and_a_bare_pointer_on_the_shelf(session: Session) -> None:
    """The anchor is a plain pointer, so a retirement must be survivable: the row stays, the subject does not."""
    author = _user(session, "retired")
    match = _scratch_match(session)
    slug = match.slug
    analysis = cma.publish_match_analysis(session, author.id, match=slug, title="A reading of a fixture that retires")
    session.delete(match)
    session.commit()

    _refused(lambda: cma.read_match_analysis(session, analysis["id"], author.id), "no_such_match")
    shelf = cma.list_match_analyses(session, author.id, creator=author.id)
    item = next(row for row in shelf["items"] if row["id"] == analysis["id"])
    assert item["match"] == {"slug": slug, "home": None, "away": None, "kickoff_at": None, "status": None, "path": None}, (
        "the shelf keeps the address and leaves nothing behind it"
    )
    assert session.get(CreatorMatchAnalysis, analysis["id"]) is not None, "the world's retirement deleted nothing of the author's"


# ------------------------------------------------------------------ the doors


def test_the_rulebook_publishes_this_noun_s_vocabulary_and_its_doors(client: TestClient) -> None:
    client = _client("rules-")
    rules = client.get("/api/v1/creator/rules")
    assert rules.status_code == 200, rules.text
    body = rules.json()
    assert body["match_caps"]["match_analysis_max"] == cma.MAX_MATCH_ANALYSES_PER_CREATOR
    assert body["match_formulas"] == cma.FORMULAS
    assert set(body["match_counts"]) == {"match_analyses"}
    assert body["match_rule"] == cma.LIMITATION
    assert body["refusal_answers"]["no_such_match_analysis"] == 404
    assert body["refusal_answers"]["no_such_match"] == 404
    assert body["refusal_answers"]["match_title"] == 422
    assert body["refusal_answers"]["match_limit"] == 409
    assert body["refusal_answers"]["match_not_played"] == 409
    routed = {(route["method"], route["path"]) for route in body["routes"]}
    assert {
        ("POST", "/creator/matches"),
        ("GET", "/creator/matches"),
        ("GET", "/creator/matches/{analysis}"),
        ("DELETE", "/creator/matches/{analysis}"),
    } <= routed


def test_the_shelf_and_the_address_answer_the_same_match(client: TestClient) -> None:
    client = _client("shelf-")
    with SessionLocal() as db:
        slug = _anchor(db).slug
    published = client.post("/api/v1/creator/matches", json={"match": slug, "title": "A shelf reading"})
    assert published.status_code == 201, published.text
    analysis = published.json()
    shelf = client.get("/api/v1/creator/matches", params={"creator": _user_id_of(client)})
    assert shelf.status_code == 200, shelf.text
    item = next(row for row in shelf.json()["items"] if row["id"] == analysis["id"])
    assert item["match"] == analysis["match"]
    assert item["moved"] is False and set(item) == {
        "id", "slug", "title", "summary", "visibility", "published_on", "author", "match", "moved"
    }, "the shelf names the fixture and prints no measurement of it"

    stranger = _client("stranger-")
    erased = stranger.delete(f"/api/v1/creator/matches/{analysis['id']}")
    assert erased.status_code == 404, erased.text
    assert erased.json()["detail"]["code"] == "no_such_match_analysis"


def test_every_private_door_is_401_before_any_row_is_consulted() -> None:
    client = TestClient(app)
    for method, path in (
        ("post", "/api/v1/creator/matches"),
        ("get", "/api/v1/creator/matches"),
        ("get", "/api/v1/creator/matches/cma_nothing"),
        ("delete", "/api/v1/creator/matches/cma_nothing"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401, f"{method.upper()} {path} answered {response.status_code}"
