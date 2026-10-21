"""§36's sixth kind of content: a scouting list of world players, addressed rather than copied.

§36 lists six kinds of content a user can create. The sixth is a **Scouting List** - an author's
selection of footballers, published as their addresses and the author's own note on each. The tier's
rule holds here too: **a publication stores an address, never a copy**.

This file defends that rule from both sides:

* the column lists of both tables are the minimisation rule, asserted as sets: no column could hold
  a name, a position, an overall, a club or any other attribute of a player;
* every attribute a read shows is read from `real_players` **on that read**, and the case proves it
  the only way that counts: it edits one scratch player and watches that entry's answer move with
  the row while the other entry stands still;
* the witness is per entry, because the anchors are: a refreshed player says `moved` on their own
  line, and a retired player leaves a bare address (`retired: true`) without erasing the list -
  deliberately unlike a single-anchor analysis, where the retired anchor is absence;
* every anchor is resolved at **publication**, so a list naming a footballer the world does not hold
  is refused there rather than becoming a page with broken rows;
* reach is §35's predicate (public / unlisted / followers), somebody else's list is **absence**, and
  this tier still answers no 403 anywhere.
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
from app.models import (
    CommunityFollow,
    CreatorScoutingEntry,
    CreatorScoutingList,
    RealPlayer,
    User,
    utc_today,
)
from app.services.creator import scouting as csc
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
    email = f"scouting-{tag}{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": f"Scouting Tester {uuid4().hex[:6]}",
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


def _user(session: Session, name: str = "scout") -> User:
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


def _scratch_player(session: Session, name: str = "Scratch Footballer") -> RealPlayer:
    """A world row of our own, so the revision and retirement cases cannot disturb the catalogue."""
    tag = uuid4().hex[:10]
    row = RealPlayer(
        id=f"rpl-{tag}",
        slug=f"creator-scouting-{tag}",
        name=f"{name} {tag}",
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


def _refused(callable_: Any, code: str) -> csc.CreatorRefusal:
    with pytest.raises(csc.CreatorRefusal) as caught:
        callable_()
    assert caught.value.code == code, f"expected {code!r}, the door answered {caught.value.code!r}: {caught.value.message}"
    return caught.value


# ------------------------------------------------------------------ the shape of what is stored


def test_the_columns_a_scouting_list_stores_are_the_minimisation_rule() -> None:
    """No column could hold an attribute of a player; the only player fact is an address and a witness."""
    listed = {str(column.name) for column in CreatorScoutingList.__table__.columns}
    assert listed == {
        "id",
        "author_id",
        "slug",
        "title",
        "summary",
        "visibility",
        "published_on",
        "data_origin",
        "is_demo_data",
        "created_at",
        "updated_at",
    }
    selected = {str(column.name) for column in CreatorScoutingEntry.__table__.columns}
    assert selected == {
        "id",
        "list_id",
        "position",
        "player_slug",
        "player_hash",
        "note",
        "created_at",
        "updated_at",
    }, "an entry is an address, a witness and the author's note - and nothing else"
    forbidden = {"name", "position_name", "overall", "age", "nation", "team", "club", "rating", "form", "attributes"}
    assert not (listed | selected) & forbidden, f"{sorted((listed | selected) & forbidden)} would be a copy of a player rather than an address"


def test_each_selection_publishes_as_the_world_s_own_address(session: Session) -> None:
    first = _scratch_player(session)
    second = _scratch_player(session)
    author = _user(session)
    published = csc.publish_scouting_list(
        session,
        author.id,
        title="Two midfielders worth watching",
        players=[
            {"player": first.id, "note": "An id on the way in is the address on the way out."},
            {"player": second.slug},
        ],
    )
    assert [entry["player"]["slug"] for entry in published["entries"]] == [first.slug, second.slug]
    assert [entry["position"] for entry in published["entries"]] == [1, 2]
    assert published["entries"][0]["note"] == "An id on the way in is the address on the way out."
    row = session.get(CreatorScoutingList, published["id"])
    assert row is not None
    held = list(
        session.scalars(
            select(CreatorScoutingEntry)
            .where(CreatorScoutingEntry.list_id == row.id)
            .order_by(CreatorScoutingEntry.position)
        ).all()
    )
    assert [entry.player_slug for entry in held] == [first.slug, second.slug]
    assert [entry.player_hash for entry in held] == [first.content_hash, second.content_hash], (
        "each witness is the address the player carried at publication"
    )


def test_the_entries_are_the_world_door_s_own_player_figures(client: TestClient) -> None:
    """The claim is *read from the player row*, so the case compares against the world's own read."""
    client = _client("same-")
    with SessionLocal() as db:
        player = _anchor(db)
        slug = player.slug
    published = client.post(
        "/api/v1/creator/scouting-lists",
        json={"title": "A list of one", "players": [{"player": slug}]},
    )
    assert published.status_code == 201, published.text
    listing = published.json()
    entry = listing["entries"][0]

    detail = client.get(f"/api/v1/world/players/{slug}")
    assert detail.status_code == 200, detail.text
    world = detail.json()["player"]
    assert entry["player"] == {
        "slug": slug,
        "name": world["name"],
        "position": world["position"],
        "overall": world["overall"],
        "team": world["club"]["name"],
        "path": world["path"],
    }, "every attribute in the list is the world door's own player, read on this request"
    assert listing["figures"] == {"players": 1, "moved": 0, "retired": 0}
    assert set(listing["formulas"]) == set(csc.FORMULAS)
    assert listing["rule"] == csc.LIMITATION


def test_editing_one_player_moves_only_their_entry(session: Session) -> None:
    """The only proof of *read on read* and *witnessed per entry*: edit one row, watch one line move."""
    first = _scratch_player(session)
    second = _scratch_player(session)
    author = _user(session, "reviser")
    published = csc.publish_scouting_list(
        session,
        author.id,
        title="A list that will partly change",
        players=[{"player": first.slug}, {"player": second.slug}],
    )
    before = csc.read_scouting_list(session, published["id"], author.id)
    assert [entry["moved"] for entry in before["entries"]] == [False, False]

    first.name = "A Footballer Rewritten by a Test"
    first.overall = 81
    first.content_hash = f"revised-{uuid4().hex}"
    session.commit()

    after = csc.read_scouting_list(session, published["id"], author.id)
    assert [entry["moved"] for entry in after["entries"]] == [True, False], (
        "the witness belongs to the entry, so the player who was not touched has not moved"
    )
    assert after["entries"][0]["player"]["name"] == "A Footballer Rewritten by a Test"
    assert after["entries"][0]["player"]["overall"] == 81
    assert after["entries"][1]["player"]["name"] == second.name
    assert after["figures"] == {"players": 2, "moved": 1, "retired": 0}


def test_a_retired_player_leaves_a_bare_address_without_erasing_the_list(session: Session) -> None:
    """A list is a selection of many addresses: one retirement is not the end of the author's list."""
    retired = _scratch_player(session)
    kept = _scratch_player(session)
    author = _user(session, "retired")
    published = csc.publish_scouting_list(
        session,
        author.id,
        title="A list of two",
        players=[{"player": retired.slug, "note": "Watch the passing."}, {"player": kept.slug}],
    )
    session.delete(retired)
    session.commit()

    read = csc.read_scouting_list(session, published["id"], author.id)
    assert read["entries"][0]["retired"] is True and read["entries"][0]["moved"] is False
    assert read["entries"][0]["player"] == {
        "slug": retired.slug, "name": None, "position": None, "overall": None, "team": None, "path": None
    }, "the list keeps the address and leaves nothing behind it"
    assert read["entries"][0]["note"] == "Watch the passing.", "the author's words survive the world's retirement"
    assert read["entries"][1]["retired"] is False and read["entries"][1]["player"]["name"] == kept.name
    assert read["figures"] == {"players": 2, "moved": 0, "retired": 1}
    assert session.get(CreatorScoutingList, published["id"]) is not None, "the world's retirement deleted nothing of the author's"


def test_an_anchor_the_world_does_not_hold_is_refused_at_publication(session: Session) -> None:
    author = _user(session, "missing")
    error = _refused(
        lambda: csc.publish_scouting_list(
            session, author.id, title="A list of nobody", players=[{"player": "no-such-player-anywhere"}]
        ),
        "no_such_scouted_player",
    )
    assert error.figures["player"] == "no-such-player-anywhere"
    held = session.scalar(select(CreatorScoutingList).where(CreatorScoutingList.author_id == author.id))
    assert held is None, "a refused publication writes no row"
    assert session.scalar(select(CreatorScoutingEntry).where(CreatorScoutingEntry.player_slug == "no-such-player-anywhere")) is None


def test_two_selections_naming_one_player_are_refused(session: Session) -> None:
    player = _scratch_player(session)
    author = _user(session, "duplicate")
    error = _refused(
        lambda: csc.publish_scouting_list(
            session,
            author.id,
            title="The same footballer twice",
            players=[{"player": player.id}, {"player": player.slug, "note": "And again"}],
        ),
        "scouting_duplicate_player",
    )
    assert error.figures == {"player": player.slug, "first": 1, "again": 2}


def test_the_size_of_a_list_is_refused_with_its_own_bounds(session: Session) -> None:
    player = _scratch_player(session)
    author = _user(session, "size")
    empty = _refused(
        lambda: csc.publish_scouting_list(session, author.id, title="An empty list", players=[]),
        "scouting_players",
    )
    assert empty.figures == {"players": 0, "min": csc.SCOUTING_PLAYERS_MIN, "max": csc.SCOUTING_PLAYERS_MAX}
    too_many = _refused(
        lambda: csc.publish_scouting_list(
            session,
            author.id,
            title="A list of too many",
            players=[{"player": player.slug} for _ in range(csc.SCOUTING_PLAYERS_MAX + 1)],
        ),
        "scouting_players",
    )
    assert too_many.figures["players"] == csc.SCOUTING_PLAYERS_MAX + 1


def test_the_open_words_are_refused_with_the_vocabulary_they_broke(session: Session) -> None:
    author = _user(session, "words")
    player = _scratch_player(session)
    blank = _refused(
        lambda: csc.publish_scouting_list(session, author.id, title="", players=[{"player": player.slug}]),
        "scouting_list_title",
    )
    assert blank.figures["max"] == csc.SCOUTING_LIST_TITLE_MAX
    visibility = _refused(
        lambda: csc.publish_scouting_list(
            session, author.id, title="A list", players=[{"player": player.slug}], visibility="friends"
        ),
        "scouting_list_visibility",
    )
    assert visibility.figures["visibilities"] == list(VISIBILITIES)
    note = _refused(
        lambda: csc.publish_scouting_list(
            session,
            author.id,
            title="A long note",
            players=[{"player": player.slug, "note": "x" * (csc.SCOUTING_NOTE_MAX + 1)}],
        ),
        "scouting_note",
    )
    assert note.figures["max"] == csc.SCOUTING_NOTE_MAX


def test_the_ceiling_refuses_one_past_it_with_its_own_figures(session: Session) -> None:
    author = _user(session, "ceiling")
    player = _scratch_player(session)
    for index in range(csc.MAX_SCOUTING_LISTS_PER_CREATOR):
        csc.publish_scouting_list(
            session, author.id, title=f"A list {index}", players=[{"player": player.slug}]
        )
    error = _refused(
        lambda: csc.publish_scouting_list(
            session, author.id, title="One too many", players=[{"player": player.slug}]
        ),
        "scouting_list_limit",
    )
    assert error.figures == {"lists": csc.MAX_SCOUTING_LISTS_PER_CREATOR, "max": csc.MAX_SCOUTING_LISTS_PER_CREATOR}


# ------------------------------------------------------------------ reach, absence and erasure


def test_a_followers_list_reaches_exactly_the_accounts_following_its_author(session: Session) -> None:
    author = _user(session, "reach")
    stranger = _user(session, "stranger")
    player = _scratch_player(session)
    listing = csc.publish_scouting_list(
        session, author.id, title="For my followers", players=[{"player": player.slug}], visibility="followers"
    )

    _refused(lambda: csc.read_scouting_list(session, listing["id"], stranger.id), "no_such_scouting_list")
    assert all(item["id"] != listing["id"] for item in csc.list_scouting_lists(session, stranger.id)["items"])
    assert csc.list_scouting_lists(session, stranger.id, creator=author.id)["total"] == 0
    assert csc.read_scouting_list(session, listing["id"], author.id)["id"] == listing["id"]

    row = CommunityFollow(
        id=new_public_id("fol"), follower_id=stranger.id, followee_id=author.id, followed_on=utc_today().isoformat()
    )
    session.add(row)
    session.commit()
    assert csc.read_scouting_list(session, listing["id"], stranger.id)["id"] == listing["id"]
    assert [item["id"] for item in csc.list_scouting_lists(session, stranger.id, creator=author.id)["items"]] == [listing["id"]]

    session.delete(row)
    session.commit()
    _refused(lambda: csc.read_scouting_list(session, listing["id"], stranger.id), "no_such_scouting_list")
    assert session.get(CreatorScoutingList, listing["id"]) is not None, "an unfollow withdraws the list and deletes nothing"


def test_an_unlisted_list_is_readable_at_its_address_and_in_no_listing(session: Session) -> None:
    author = _user(session, "unlisted")
    stranger = _user(session, "reader")
    player = _scratch_player(session)
    listing = csc.publish_scouting_list(
        session, author.id, title="Quietly shared", players=[{"player": player.slug}], visibility="unlisted"
    )
    assert csc.read_scouting_list(session, listing["id"], stranger.id)["id"] == listing["id"], "its own address is the door"
    assert all(item["id"] != listing["id"] for item in csc.list_scouting_lists(session, stranger.id)["items"])


def test_another_accounts_list_is_answered_as_absence_and_survives_the_attempt(session: Session) -> None:
    owner = _user(session, "owner")
    stranger = _user(session, "intruder")
    player = _scratch_player(session)
    listing = csc.publish_scouting_list(session, owner.id, title="Not yours to erase", players=[{"player": player.slug}])
    _refused(lambda: csc.erase_scouting_list(session, stranger.id, listing["id"]), "no_such_scouting_list")
    assert session.get(CreatorScoutingList, listing["id"]) is not None, "the refusal wrote and erased nothing"


def test_erasing_a_list_leaves_the_players_untouched_and_takes_its_entries(session: Session) -> None:
    author = _user(session, "eraser")
    player = _scratch_player(session)
    listing = csc.publish_scouting_list(session, author.id, title="A list to withdraw", players=[{"player": player.slug}])
    answer = csc.erase_scouting_list(session, author.id, listing["id"])
    assert answer == {"status": "erased", "list": listing["id"]}
    assert session.get(CreatorScoutingList, listing["id"]) is None
    assert session.scalar(
        select(CreatorScoutingEntry).where(CreatorScoutingEntry.list_id == listing["id"])
    ) is None, "the list's selections went with it"
    assert session.get(RealPlayer, player.id) is not None, "a list never takes its subjects with it"
    _refused(lambda: csc.read_scouting_list(session, listing["id"], author.id), "no_such_scouting_list")


# ------------------------------------------------------------------ the doors


def test_the_rulebook_publishes_this_noun_s_vocabulary_and_its_doors(client: TestClient) -> None:
    client = _client("rules-")
    rules = client.get("/api/v1/creator/rules")
    assert rules.status_code == 200, rules.text
    body = rules.json()
    caps = body["scouting_list_caps"]
    assert caps["scouting_list_max"] == csc.MAX_SCOUTING_LISTS_PER_CREATOR
    assert caps["scouting_players_max"] == csc.SCOUTING_PLAYERS_MAX
    assert caps["scouting_note_max"] == csc.SCOUTING_NOTE_MAX
    assert body["scouting_list_formulas"] == csc.FORMULAS
    assert set(body["scouting_list_counts"]) == {"scouting_lists", "scouting_entries"}
    assert body["scouting_list_rule"] == csc.LIMITATION
    assert body["refusal_answers"]["no_such_scouting_list"] == 404
    assert body["refusal_answers"]["no_such_scouted_player"] == 404
    assert body["refusal_answers"]["scouting_list_title"] == 422
    assert body["refusal_answers"]["scouting_duplicate_player"] == 422
    assert body["refusal_answers"]["scouting_list_limit"] == 409
    routed = {(route["method"], route["path"]) for route in body["routes"]}
    assert {
        ("POST", "/creator/scouting-lists"),
        ("GET", "/creator/scouting-lists"),
        ("GET", "/creator/scouting-lists/{list_id}"),
        ("DELETE", "/creator/scouting-lists/{list_id}"),
    } <= routed


def test_the_shelf_and_the_address_answer_the_same_selections(client: TestClient) -> None:
    client = _client("shelf-")
    with SessionLocal() as db:
        player = _anchor(db)
        slug = player.slug
    published = client.post(
        "/api/v1/creator/scouting-lists",
        json={"title": "A shelf list", "players": [{"player": slug, "note": "The first name on the sheet."}]},
    )
    assert published.status_code == 201, published.text
    listing = published.json()
    shelf = client.get("/api/v1/creator/scouting-lists", params={"creator": _user_id_of(client)})
    assert shelf.status_code == 200, shelf.text
    item = next(row for row in shelf.json()["items"] if row["id"] == listing["id"])
    assert item["players"] == len(listing["entries"]) == 1
    assert set(item) == {
        "id", "slug", "title", "summary", "visibility", "published_on", "author", "players"
    }, "the shelf names the list and its size, and prints no attribute of any player"
    assert slug not in str(item), "not even the address belongs on the shelf"

    stranger = _client("stranger-")
    erased = stranger.delete(f"/api/v1/creator/scouting-lists/{listing['id']}")
    assert erased.status_code == 404, erased.text
    assert erased.json()["detail"]["code"] == "no_such_scouting_list"


def test_every_private_door_is_401_before_any_row_is_consulted() -> None:
    client = TestClient(app)
    for method, path in (
        ("post", "/api/v1/creator/scouting-lists"),
        ("get", "/api/v1/creator/scouting-lists"),
        ("get", "/api/v1/creator/scouting-lists/csl_nothing"),
        ("delete", "/api/v1/creator/scouting-lists/csl_nothing"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401, f"{method.upper()} {path} answered {response.status_code}"
