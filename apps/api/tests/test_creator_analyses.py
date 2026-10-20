"""§36's third kind of content: a player analysis anchored to a stored footballer, copying none of him.

§36 lists six kinds of content a user can create. The first, a Training Program, is a schedule; the
second, a Tactical Guide, is an address into the tactical catalogue; the third is a **Player
Analysis** - an author's reading of a footballer. The tier's own rule for citations is the rule for
this noun too: **a publication stores an address, never a copy**.

This file defends that rule from both sides:

* the column list is the minimisation rule, asserted as a set: no column on
  `creator_player_analyses` could hold a total, a rate or a sentence about the player;
* every measurement a read shows is computed from the player's stored columns **on that read**, and
  the case proves it the only way that counts: it edits the player's totals and watches the
  analysis's answer move with them - equal to the world door's own season figures fed through the
  published formulas, not to a snapshot;
* the one thing stored about the player is a **witness**: the content address he carried when the
  analysis was written, so a refreshed player is still measurable and says `moved`, exactly as a
  citation's `cited_text_hash` does;
* the anchor is resolved at **publication**, so an analysis of a footballer the world does not hold
  is refused there rather than becoming a page with nothing to read;
* reach is §35's predicate (public / unlisted / followers), somebody else's analysis is **absence**,
  and this tier still answers no 403 anywhere.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import new_public_id
from app.main import app
from app.models import CommunityFollow, CreatorPlayerAnalysis, RealPlayer, User, utc_today
from app.services.creator import analyses as can
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
    email = f"analysis-{tag}{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": f"Analysis Tester {uuid4().hex[:6]}",
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


def _anchor(session: Session) -> RealPlayer:
    row = session.scalar(
        select(RealPlayer)
        .where(RealPlayer.appearances > 0, RealPlayer.minutes > 0)
        .order_by(RealPlayer.slug)
        .limit(1)
    )
    assert row is not None, "the test database holds no world player with minutes, so there is nothing to anchor to"
    return row


def _scratch_player(session: Session) -> RealPlayer:
    """A world row of our own, so the revision case cannot disturb the generated catalogue."""
    tag = uuid4().hex[:10]
    row = RealPlayer(
        id=f"rpl-{tag}",
        slug=f"creator-analysis-{tag}",
        name=f"Scratch Footballer {tag}",
        position="CM",
        secondary_positions=["AM"],
        age=24,
        preferred_foot="right",
        height_cm=180,
        nation="Testland",
        season="2025/26",
        attributes={"passing": 70, "vision": 68},
        overall=72,
        potential=84,
        archetype="Deep-Lying Playmaker",
        archetype_match=0.81,
        minutes=810,
        appearances=10,
        starts=8,
        goals=4,
        assists=3,
        clean_sheets=0,
        yellow_cards=2,
        red_cards=0,
        rating=7.1,
        form=0.4,
        summary="A scratch footballer written by a test.",
        content_hash=f"scratch-{tag}",
        data_origin="synthetic",
        is_demo_data=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _refused(callable_: Any, code: str) -> can.CreatorRefusal:
    with pytest.raises(can.CreatorRefusal) as caught:
        callable_()
    assert caught.value.code == code, f"expected {code!r}, the door answered {caught.value.code!r}: {caught.value.message}"
    return caught.value


def _expected(season: dict[str, Any]) -> dict[str, float]:
    """The five published formulas, applied by the test to the world door's own season figures."""
    appearances = season["appearances"]
    minutes = season["minutes"]
    cards = season["yellow_cards"] + season["red_cards"]
    return {
        "minutes_per_appearance": round(minutes / appearances, 2) if appearances else 0.0,
        "goal_contributions_per_90": round((season["goals"] + season["assists"]) * 90 / minutes, 2) if minutes else 0.0,
        "scoring_rate": round(season["goals"] / appearances, 2) if appearances else 0.0,
        "availability": round(minutes / (90 * appearances), 2) if appearances else 0.0,
        "cards_per_90": round(cards * 90 / minutes, 2) if minutes else 0.0,
    }


# ------------------------------------------------------------------ the shape of what is stored


def test_the_columns_a_player_analysis_stores_are_the_minimisation_rule() -> None:
    """No column could hold a total, a rate or a sentence about the player it points at."""
    held = {str(column.name) for column in CreatorPlayerAnalysis.__table__.columns}
    assert held == {
        "id",
        "author_id",
        "slug",
        "title",
        "summary",
        "visibility",
        "player_slug",
        "player_hash",
        "published_on",
        "data_origin",
        "is_demo_data",
        "created_at",
        "updated_at",
    }
    forbidden = {"metrics", "goals", "assists", "minutes", "appearances", "rating", "formula", "value", "board", "attributes"}
    assert not held & forbidden, f"{sorted(held & forbidden)} would be a copy of the player rather than an address"


def test_the_anchor_publishes_as_the_world_s_own_address(session: Session) -> None:
    player = _anchor(session)
    author = _user(session)
    published = can.publish_player_analysis(
        session,
        author.id,
        player=player.id,
        title="Why this passer breaks the first line",
        summary="A reading of the output and the minutes behind it.",
    )
    assert published["player"]["slug"] == player.slug, "an id on the way in is the slug on the way out"
    assert published["player"]["path"].endswith(f"/{player.slug}")
    assert published["title"] == "Why this passer breaks the first line"
    row = session.get(CreatorPlayerAnalysis, published["id"])
    assert row is not None and row.player_slug == player.slug
    assert row.player_hash == player.content_hash, "the witness is the address the player carried at publication"


def test_the_measurements_are_the_world_door_s_own_season_figures(client: TestClient) -> None:
    """The claim is *computed from the anchored columns*, so the case compares against the world's own read."""
    client = _client("same-")
    with SessionLocal() as db:
        player = _anchor(db)
        slug = player.slug
    published = client.post(
        "/api/v1/creator/players",
        json={"player": slug, "title": "A reading of the output"},
    )
    assert published.status_code == 201, published.text
    analysis = published.json()

    detail = client.get(f"/api/v1/world/players/{slug}")
    assert detail.status_code == 200, detail.text
    season = detail.json()["season_stats"]
    assert {key: metric["value"] for key, metric in analysis["metrics"].items()} == _expected(season), (
        "the analysis's numbers are the world door's season figures through the published formulas"
    )
    assert set(analysis["metrics"]) == set(can.METRIC_FORMULAS)
    assert all(metric["formula"] for metric in analysis["metrics"].values()), "a number without its formula is not a measurement here"


def test_editing_the_player_moves_the_analysis_and_it_says_so(session: Session) -> None:
    """The only proof of *computed on read*: change the totals, and the same analysis answers differently."""
    player = _scratch_player(session)
    author = _user(session, "reviser")
    published = can.publish_player_analysis(session, author.id, player=player.slug, title="A player who will change")
    before = can.read_player_analysis(session, published["id"], author.id)
    assert before["moved"] is False, "an analysis written against the current revision has not moved"
    first = before["metrics"]["goal_contributions_per_90"]["value"]

    player.goals = 9
    player.minutes = 900
    player.content_hash = f"revised-{uuid4().hex}"
    session.commit()

    after = can.read_player_analysis(session, published["id"], author.id)
    assert after["moved"] is True, "the player's content address changed, so the analysis says it moved"
    assert after["metrics"]["goal_contributions_per_90"]["value"] != first, "the measurement followed the totals"
    assert after["metrics"]["minutes_per_appearance"]["value"] == round(900 / player.appearances, 2)
    assert after["metrics"]["goal_contributions_per_90"]["value"] == round((9 + player.assists) * 90 / 900, 2)
    assert after["metrics"]["scoring_rate"]["value"] == round(9 / player.appearances, 2)

    session.delete(session.get(RealPlayer, player.id))
    session.commit()


def test_an_anchor_the_world_does_not_hold_is_refused_at_publication(session: Session) -> None:
    author = _user(session, "missing")
    error = _refused(
        lambda: can.publish_player_analysis(session, author.id, player="no-such-player-anywhere", title="A reading of nobody"),
        "no_such_analysed_player",
    )
    assert error.figures["player"] == "no-such-player-anywhere"
    held = session.scalar(select(CreatorPlayerAnalysis).where(CreatorPlayerAnalysis.author_id == author.id))
    assert held is None, "a refused publication writes no row"


def test_the_open_words_are_refused_with_the_vocabulary_they_broke(session: Session) -> None:
    author = _user(session, "words")
    blank = _refused(
        lambda: can.publish_player_analysis(session, author.id, player=_anchor(session).slug, title=""),
        "analysis_title",
    )
    assert blank.figures["max"] == can.ANALYSIS_TITLE_MAX
    visibility = _refused(
        lambda: can.publish_player_analysis(session, author.id, player=_anchor(session).slug, title="A reading", visibility="friends"),
        "analysis_visibility",
    )
    assert visibility.figures["visibilities"] == list(VISIBILITIES)


def test_the_ceiling_refuses_one_past_it_with_its_own_figures(session: Session) -> None:
    author = _user(session, "ceiling")
    slug = _anchor(session).slug
    for index in range(can.MAX_PLAYER_ANALYSES_PER_CREATOR):
        can.publish_player_analysis(session, author.id, player=slug, title=f"A reading {index}")
    error = _refused(
        lambda: can.publish_player_analysis(session, author.id, player=slug, title="One too many"),
        "analysis_limit",
    )
    assert error.figures == {"analyses": can.MAX_PLAYER_ANALYSES_PER_CREATOR, "max": can.MAX_PLAYER_ANALYSES_PER_CREATOR}


# ------------------------------------------------------------------ reach, absence and erasure


def test_a_followers_analysis_reaches_exactly_the_accounts_following_its_author(session: Session) -> None:
    author = _user(session, "reach")
    stranger = _user(session, "stranger")
    slug = _anchor(session).slug
    analysis = can.publish_player_analysis(session, author.id, player=slug, title="For my followers", visibility="followers")

    _refused(lambda: can.read_player_analysis(session, analysis["id"], stranger.id), "no_such_analysis")
    assert all(item["id"] != analysis["id"] for item in can.list_player_analyses(session, stranger.id)["items"])
    assert can.list_player_analyses(session, stranger.id, creator=author.id)["total"] == 0
    assert can.read_player_analysis(session, analysis["id"], author.id)["id"] == analysis["id"]

    row = CommunityFollow(id=new_public_id("fol"), follower_id=stranger.id, followee_id=author.id, followed_on=utc_today().isoformat())
    session.add(row)
    session.commit()
    assert can.read_player_analysis(session, analysis["id"], stranger.id)["id"] == analysis["id"]
    assert [item["id"] for item in can.list_player_analyses(session, stranger.id, creator=author.id)["items"]] == [analysis["id"]]

    session.delete(row)
    session.commit()
    _refused(lambda: can.read_player_analysis(session, analysis["id"], stranger.id), "no_such_analysis")
    assert session.get(CreatorPlayerAnalysis, analysis["id"]) is not None, "an unfollow withdraws the analysis and deletes nothing"


def test_an_unlisted_analysis_is_readable_at_its_address_and_in_no_listing(session: Session) -> None:
    author = _user(session, "unlisted")
    stranger = _user(session, "reader")
    analysis = can.publish_player_analysis(session, author.id, player=_anchor(session).slug, title="Quietly shared", visibility="unlisted")
    assert can.read_player_analysis(session, analysis["id"], stranger.id)["id"] == analysis["id"], "its own address is the door"
    assert all(item["id"] != analysis["id"] for item in can.list_player_analyses(session, stranger.id)["items"])


def test_another_accounts_analysis_is_answered_as_absence_and_survives_the_attempt(session: Session) -> None:
    owner = _user(session, "owner")
    stranger = _user(session, "intruder")
    analysis = can.publish_player_analysis(session, owner.id, player=_anchor(session).slug, title="Not yours to erase")
    _refused(lambda: can.erase_player_analysis(session, stranger.id, analysis["id"]), "no_such_analysis")
    assert session.get(CreatorPlayerAnalysis, analysis["id"]) is not None, "the refusal wrote and erased nothing"


def test_erasing_an_analysis_leaves_the_player_untouched(session: Session) -> None:
    author = _user(session, "eraser")
    player = _anchor(session)
    analysis = can.publish_player_analysis(session, author.id, player=player.slug, title="An analysis to withdraw")
    answer = can.erase_player_analysis(session, author.id, analysis["id"])
    assert answer == {"status": "erased", "analysis": analysis["id"]}
    assert session.get(CreatorPlayerAnalysis, analysis["id"]) is None
    assert session.get(RealPlayer, player.id) is not None, "a reading never takes its subject with it"
    _refused(lambda: can.read_player_analysis(session, analysis["id"], author.id), "no_such_analysis")


def test_a_retired_player_is_absence_at_the_address_and_a_bare_pointer_on_the_shelf(session: Session) -> None:
    """The anchor is a plain pointer, so a retirement must be survivable: the row stays, the subject does not."""
    author = _user(session, "retired")
    player = _scratch_player(session)
    slug = player.slug
    analysis = can.publish_player_analysis(session, author.id, player=slug, title="A reading of a player who retires")
    session.delete(player)
    session.commit()

    _refused(lambda: can.read_player_analysis(session, analysis["id"], author.id), "no_such_analysed_player")
    shelf = can.list_player_analyses(session, author.id, creator=author.id)
    item = next(row for row in shelf["items"] if row["id"] == analysis["id"])
    assert item["player"] == {"slug": slug, "name": None, "position": None, "overall": None, "team": None, "path": None}, (
        "the shelf keeps the address and leaves nothing behind it"
    )
    assert session.get(CreatorPlayerAnalysis, analysis["id"]) is not None, "the world's retirement deleted nothing of the author's"


# ------------------------------------------------------------------ the doors


def test_the_rulebook_publishes_this_noun_s_vocabulary_and_its_doors(client: TestClient) -> None:
    client = _client("rules-")
    rules = client.get("/api/v1/creator/rules")
    assert rules.status_code == 200, rules.text
    body = rules.json()
    assert body["analysis_caps"]["analysis_max"] == can.MAX_PLAYER_ANALYSES_PER_CREATOR
    assert body["analysis_formulas"] == can.FORMULAS
    assert set(body["analysis_counts"]) == {"player_analyses"}
    assert body["analysis_rule"] == can.LIMITATION
    assert body["refusal_answers"]["no_such_analysis"] == 404
    assert body["refusal_answers"]["analysis_title"] == 422
    assert body["refusal_answers"]["analysis_limit"] == 409
    routed = {(route["method"], route["path"]) for route in body["routes"]}
    assert {
        ("POST", "/creator/players"),
        ("GET", "/creator/players"),
        ("GET", "/creator/players/{analysis}"),
        ("DELETE", "/creator/players/{analysis}"),
    } <= routed


def test_the_shelf_and_the_address_answer_the_same_player(client: TestClient) -> None:
    client = _client("shelf-")
    with SessionLocal() as db:
        slug = _anchor(db).slug
    published = client.post("/api/v1/creator/players", json={"player": slug, "title": "A shelf reading"})
    assert published.status_code == 201, published.text
    analysis = published.json()
    shelf = client.get("/api/v1/creator/players", params={"creator": _user_id_of(client)})
    assert shelf.status_code == 200, shelf.text
    item = next(row for row in shelf.json()["items"] if row["id"] == analysis["id"])
    assert item["player"] == analysis["player"]
    assert item["moved"] is False and set(item) == {
        "id", "slug", "title", "summary", "visibility", "published_on", "author", "player", "moved"
    }, "the shelf names the player and prints no measurement of him"

    stranger = _client("stranger-")
    erased = stranger.delete(f"/api/v1/creator/players/{analysis['id']}")
    assert erased.status_code == 404, erased.text
    assert erased.json()["detail"]["code"] == "no_such_analysis"


def test_every_private_door_is_401_before_any_row_is_consulted() -> None:
    client = TestClient(app)
    for method, path in (
        ("post", "/api/v1/creator/players"),
        ("get", "/api/v1/creator/players"),
        ("get", "/api/v1/creator/players/cpa_nothing"),
        ("delete", "/api/v1/creator/players/cpa_nothing"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401, f"{method.upper()} {path} answered {response.status_code}"
