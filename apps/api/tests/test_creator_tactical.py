"""§36's second kind of content: a tactical guide anchored to a stored system, copying none of it.

§36 lists six kinds of content a user can create. The first, a Training Program, is a schedule; the
second is a **Tactical Guide** - an author's reading of a shape. The tier's own rule for citations is
the rule for this noun too: **a publication stores an address, never a copy**.

This file defends that rule from both sides:

* the column list is the minimisation rule, asserted as a set: no column on `creator_tactical_guides`
  could hold a metric, a coordinate or a sentence about the shape;
* every measurement a read shows is computed from the system's stored dots **on that read**, and the
  case proves it the only way that counts: it edits the system's board and watches the guide's answer
  move with it - equal to what `/api/v1/tactics/{slug}` says about the same dots, not to a snapshot;
* the one thing stored about the system is a **witness**: the content address it carried when the
  guide was written, so a revised system is still measurable and says `moved`, exactly as a citation's
  `cited_text_hash` does;
* the anchor is resolved at **publication**, so a guide about a system the catalogue does not hold is
  refused there rather than becoming a page with nothing to read;
* reach is §35's predicate (public / unlisted / followers), somebody else's guide is **absence**, and
  this tier still answers no 403 anywhere.
"""

from __future__ import annotations

import copy
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
from app.models import CommunityFollow, CreatorTacticalGuide, TacticalSystem, User, utc_today
from app.services.creator import tactical as ctr
from app.services.creator.publishing import VISIBILITIES
from app.services.tactics.analysis import METRIC_KEYS, metrics_of, shape_from_rows

PASSWORD = "TestPass1234!"
SYSTEM_SLUG = "4-3-3-press-high"


@pytest.fixture(scope="module", autouse=True)
def _catalogue() -> None:
    """The fifty systems are stored by the app's boot; a service-level case needs them without a door."""
    from app.services.tactics.sync import sync_tactics

    with SessionLocal() as db:
        sync_tactics(db)


@pytest.fixture()
def session() -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _client(tag: str = "") -> TestClient:
    client = TestClient(app)
    email = f"tactical-{tag}{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": f"Tactical Tester {uuid4().hex[:6]}",
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


def _user(session: Session, name: str = "tactical") -> User:
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


def _anchor(session: Session) -> TacticalSystem:
    row = session.scalar(select(TacticalSystem).where(TacticalSystem.slug == SYSTEM_SLUG))
    assert row is not None, "the test database holds no tactical catalogue, so there is nothing to anchor to"
    return row


def _scratch_system(session: Session) -> TacticalSystem:
    """A catalogue row of our own, so the revision case cannot disturb the shipped fifty."""
    source = _anchor(session)
    tag = uuid4().hex[:10]
    row = TacticalSystem(
        id=f"tsys-{tag}",
        slug=f"creator-tactical-{tag}",
        name=f"Scratch Shape {tag}",
        formation=source.formation,
        temperament_key=source.temperament_key,
        press_line_y=source.press_line_y,
        block_depth=source.block_depth,
        defensive_narrowing=source.defensive_narrowing,
        board=copy.deepcopy(source.board),
        content_hash=f"scratch-{tag}",
        data_origin="project-authored",
        is_demo_data=False,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _refused(callable_: Any, code: str) -> ctr.CreatorRefusal:
    with pytest.raises(ctr.CreatorRefusal) as caught:
        callable_()
    assert caught.value.code == code, f"expected {code!r}, the door answered {caught.value.code!r}: {caught.value.message}"
    return caught.value


# ------------------------------------------------------------------ the shape of what is stored


def test_the_columns_a_tactical_guide_stores_are_the_minimisation_rule() -> None:
    """No column could hold a metric, a coordinate or a sentence about the shape it points at."""
    held = {str(column.name) for column in CreatorTacticalGuide.__table__.columns}
    assert held == {
        "id",
        "author_id",
        "slug",
        "title",
        "summary",
        "visibility",
        "system_slug",
        "system_hash",
        "published_on",
        "data_origin",
        "is_demo_data",
        "created_at",
        "updated_at",
    }
    forbidden = {"board", "phase_in", "phase_out", "metrics", "width", "depth", "coverage", "spacing", "formation", "pitch", "points"}
    assert not held & forbidden, f"{sorted(held & forbidden)} would be a copy of the system rather than an address"


def test_the_anchor_publishes_as_the_catalogue_s_own_address(session: Session) -> None:
    system = _anchor(session)
    author = _user(session)
    published = ctr.publish_tactical_guide(
        session,
        author.id,
        system=system.id,
        title="Why this shape squeezes the midfield",
        summary="A reading of the width and the space behind.",
    )
    assert published["system"]["slug"] == system.slug, "an id on the way in is the slug on the way out"
    assert published["system"]["path"] == f"/tactics/{system.slug}"
    assert published["title"] == "Why this shape squeezes the midfield"
    row = session.get(CreatorTacticalGuide, published["id"])
    assert row is not None and row.system_slug == system.slug
    assert row.system_hash == system.content_hash, "the witness is the address the system carried at publication"


def test_the_measurements_are_the_tactics_door_s_own_answer(client: TestClient) -> None:
    """The claim is *recomputed by the same function*, so the case compares whole answers, not labels."""
    client = _client("same-")
    published = client.post(
        "/api/v1/creator/tactics",
        json={"system": SYSTEM_SLUG, "title": "A reading of the press"},
    )
    assert published.status_code == 201, published.text
    guide = published.json()

    detail = client.get(f"/api/v1/tactics/{SYSTEM_SLUG}")
    assert detail.status_code == 200, detail.text
    system = detail.json()
    assert guide["metrics"]["phase_in"] == {metric["key"]: metric for metric in system["metrics_in"]}, "the guide's in-possession numbers are the tactics door's"
    assert guide["metrics"]["phase_out"] == {metric["key"]: metric for metric in system["metrics_out"]}, "and so are the out-of-possession ones"
    assert set(guide["metrics"]["phase_in"]) == set(METRIC_KEYS)
    assert all(metric["formula"] for metric in guide["metrics"]["phase_in"].values()), "a number without its formula is not a measurement here"


def test_editing_the_system_moves_the_guide_and_it_says_so(session: Session) -> None:
    """The only proof of *computed on read*: change the dots, and the same guide answers differently."""
    system = _scratch_system(session)
    author = _user(session, "reviser")
    published = ctr.publish_tactical_guide(session, author.id, system=system.slug, title="A shape that will change")
    before = ctr.read_tactical_guide(session, published["id"], author.id)
    assert before["moved"] is False, "a guide written against the current revision has not moved"
    first_spacing = before["metrics"]["phase_in"]["spacing"]["value"]

    board = copy.deepcopy(system.board)
    board["phase_in"][1]["x"] = float(board["phase_in"][1]["x"]) + 3.0
    system.board = board
    system.content_hash = f"revised-{uuid4().hex}"
    session.commit()

    after = ctr.read_tactical_guide(session, published["id"], author.id)
    assert after["moved"] is True, "the system's content address changed, so the guide says it moved"
    assert after["metrics"]["phase_in"]["spacing"]["value"] != first_spacing, "the measurement followed the dots"
    pure = {metric.key: metric.to_dict() for metric in metrics_of(shape_from_rows(board["phase_in"]))}
    assert after["metrics"]["phase_in"] == pure, "and it is still the pure function's answer for the revised dots"

    session.delete(session.get(TacticalSystem, system.id))
    session.commit()


def test_an_anchor_the_catalogue_does_not_hold_is_refused_at_publication(session: Session) -> None:
    author = _user(session, "missing")
    error = _refused(
        lambda: ctr.publish_tactical_guide(session, author.id, system="no-such-system-anywhere", title="A reading of nothing"),
        "no_such_system",
    )
    assert error.figures["system"] == "no-such-system-anywhere"
    held = session.scalar(
        select(CreatorTacticalGuide).where(CreatorTacticalGuide.author_id == author.id)
    )
    assert held is None, "a refused publication writes no row"


def test_the_open_words_are_refused_with_the_vocabulary_they_broke(session: Session) -> None:
    author = _user(session, "words")
    blank = _refused(
        lambda: ctr.publish_tactical_guide(session, author.id, system=SYSTEM_SLUG, title=""),
        "tactical_title",
    )
    assert blank.figures["max"] == ctr.TACTICAL_TITLE_MAX
    visibility = _refused(
        lambda: ctr.publish_tactical_guide(session, author.id, system=SYSTEM_SLUG, title="A reading", visibility="friends"),
        "tactical_visibility",
    )
    assert visibility.figures["visibilities"] == list(VISIBILITIES)


def test_the_ceiling_refuses_one_past_it_with_its_own_figures(session: Session) -> None:
    author = _user(session, "ceiling")
    for index in range(ctr.MAX_TACTICAL_GUIDES_PER_CREATOR):
        ctr.publish_tactical_guide(session, author.id, system=SYSTEM_SLUG, title=f"A reading {index}")
    error = _refused(
        lambda: ctr.publish_tactical_guide(session, author.id, system=SYSTEM_SLUG, title="One too many"),
        "tactical_limit",
    )
    assert error.figures == {"guides": ctr.MAX_TACTICAL_GUIDES_PER_CREATOR, "max": ctr.MAX_TACTICAL_GUIDES_PER_CREATOR}


# ------------------------------------------------------------------ reach, absence and erasure


def test_a_followers_guide_reaches_exactly_the_accounts_following_its_author(session: Session) -> None:
    author = _user(session, "reach")
    stranger = _user(session, "stranger")
    guide = ctr.publish_tactical_guide(
        session, author.id, system=SYSTEM_SLUG, title="For my followers", visibility="followers"
    )

    _refused(lambda: ctr.read_tactical_guide(session, guide["id"], stranger.id), "no_such_tactical")
    assert all(item["id"] != guide["id"] for item in ctr.list_tactical_guides(session, stranger.id)["items"])
    assert ctr.list_tactical_guides(session, stranger.id, creator=author.id)["total"] == 0
    assert ctr.read_tactical_guide(session, guide["id"], author.id)["id"] == guide["id"]

    row = CommunityFollow(id=new_public_id("fol"), follower_id=stranger.id, followee_id=author.id, followed_on=utc_today().isoformat())
    session.add(row)
    session.commit()
    assert ctr.read_tactical_guide(session, guide["id"], stranger.id)["id"] == guide["id"]
    assert [item["id"] for item in ctr.list_tactical_guides(session, stranger.id, creator=author.id)["items"]] == [guide["id"]]

    session.delete(row)
    session.commit()
    _refused(lambda: ctr.read_tactical_guide(session, guide["id"], stranger.id), "no_such_tactical")
    assert session.get(CreatorTacticalGuide, guide["id"]) is not None, "an unfollow withdraws the guide and deletes nothing"


def test_an_unlisted_guide_is_readable_at_its_address_and_in_no_listing(session: Session) -> None:
    author = _user(session, "unlisted")
    stranger = _user(session, "reader")
    guide = ctr.publish_tactical_guide(
        session, author.id, system=SYSTEM_SLUG, title="Quietly shared", visibility="unlisted"
    )
    assert ctr.read_tactical_guide(session, guide["id"], stranger.id)["id"] == guide["id"], "its own address is the door"
    assert all(item["id"] != guide["id"] for item in ctr.list_tactical_guides(session, stranger.id)["items"])


def test_another_accounts_guide_is_answered_as_absence_and_survives_the_attempt(session: Session) -> None:
    owner = _user(session, "owner")
    stranger = _user(session, "intruder")
    guide = ctr.publish_tactical_guide(session, owner.id, system=SYSTEM_SLUG, title="Not yours to erase")
    _refused(lambda: ctr.erase_tactical_guide(session, stranger.id, guide["id"]), "no_such_tactical")
    assert session.get(CreatorTacticalGuide, guide["id"]) is not None, "the refusal wrote and erased nothing"


def test_erasing_a_guide_leaves_the_system_untouched(session: Session) -> None:
    author = _user(session, "eraser")
    system = _anchor(session)
    guide = ctr.publish_tactical_guide(session, author.id, system=system.slug, title="A guide to withdraw")
    answer = ctr.erase_tactical_guide(session, author.id, guide["id"])
    assert answer == {"status": "erased", "guide": guide["id"]}
    assert session.get(CreatorTacticalGuide, guide["id"]) is None
    assert session.get(TacticalSystem, system.id) is not None, "a reading never takes its subject with it"
    _refused(lambda: ctr.read_tactical_guide(session, guide["id"], author.id), "no_such_tactical")


def test_a_retired_system_is_absence_at_the_address_and_a_bare_pointer_on_the_shelf(session: Session) -> None:
    """The anchor is a plain pointer, so a retirement must be survivable: the row stays, the subject does not."""
    author = _user(session, "retired")
    system = _scratch_system(session)
    slug = system.slug
    guide = ctr.publish_tactical_guide(session, author.id, system=slug, title="A reading of a shape that retires")
    session.delete(system)
    session.commit()

    _refused(lambda: ctr.read_tactical_guide(session, guide["id"], author.id), "no_such_system")
    item = next(row for row in ctr.list_tactical_guides(session, author.id, creator=author.id)["items"] if row["id"] == guide["id"])
    assert item["system"] == {"slug": slug, "name": None, "formation": None, "path": None}, (
        "the shelf keeps the address and leaves nothing behind it"
    )
    assert session.get(CreatorTacticalGuide, guide["id"]) is not None, "the catalogue's retirement deleted nothing of the author's"


# ------------------------------------------------------------------ the doors


def test_the_rulebook_publishes_this_noun_s_vocabulary_and_its_doors(client: TestClient) -> None:
    client = _client("rules-")
    rules = client.get("/api/v1/creator/rules")
    assert rules.status_code == 200, rules.text
    body = rules.json()
    assert body["tactical_caps"]["tactical_guide_max"] == ctr.MAX_TACTICAL_GUIDES_PER_CREATOR
    assert body["tactical_formulas"] == ctr.FORMULAS
    assert set(body["tactical_counts"]) == {"tactical_guides"}
    assert body["tactical_rule"] == ctr.LIMITATION
    assert body["refusal_answers"]["no_such_tactical"] == 404
    assert body["refusal_answers"]["tactical_title"] == 422
    assert body["refusal_answers"]["tactical_limit"] == 409
    routed = {(route["method"], route["path"]) for route in body["routes"]}
    assert {
        ("POST", "/creator/tactics"),
        ("GET", "/creator/tactics"),
        ("GET", "/creator/tactics/{guide}"),
        ("DELETE", "/creator/tactics/{guide}"),
    } <= routed


def test_the_shelf_and_the_address_answer_the_same_anchor(client: TestClient) -> None:
    client = _client("shelf-")
    published = client.post("/api/v1/creator/tactics", json={"system": SYSTEM_SLUG, "title": "A shelf reading"})
    assert published.status_code == 201, published.text
    guide = published.json()
    shelf = client.get("/api/v1/creator/tactics", params={"creator": _user_id_of(client)})
    assert shelf.status_code == 200, shelf.text
    item = next(row for row in shelf.json()["items"] if row["id"] == guide["id"])
    assert item["system"] == guide["system"]
    assert item["moved"] is False and set(item) == {
        "id", "slug", "title", "summary", "visibility", "published_on", "author", "system", "moved"
    }, "the shelf names the anchor and prints no measurement of it"

    stranger = _client("stranger-")
    erased = stranger.delete(f"/api/v1/creator/tactics/{guide['id']}")
    assert erased.status_code == 404, erased.text
    assert erased.json()["detail"]["code"] == "no_such_tactical"


def test_every_private_door_is_401_before_any_row_is_consulted() -> None:
    client = TestClient(app)
    for method, path in (
        ("post", "/api/v1/creator/tactics"),
        ("get", "/api/v1/creator/tactics"),
        ("get", "/api/v1/creator/tactics/ctg_nothing"),
        ("delete", "/api/v1/creator/tactics/ctg_nothing"),
    ):
        response = getattr(client, method)(path)
        assert response.status_code == 401, f"{method.upper()} {path} answered {response.status_code}"
