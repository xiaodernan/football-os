"""§36's creator tier: a guide that cites the corpus, and the rows that decide what a reader may see.

The claims this file defends, in the order it attacks them:

* a guide stores **a title, a frame and addresses** — the column list is the minimisation rule, so it is asserted
  as a set: no column on `creator_guides` or `guide_citations` could hold a passage's text, a token total or a
  count of either;
* every figure a reader sees (`citations`, `moved`, `tokens`, `guides`, `subscribers`) is counted from the rows its
  own formula names at the moment of the read, so editing or deleting the *chunk* moves the figure — which a stored
  number could not do, and which is the whole reason a citation is an address;
* a citation is **one row per (guide, document, ordinal)** by unique constraint, and the hash it stores is a
  witness, not a link: a passage whose text changed since it was cited is still readable and says so via `moved`;
* the pricing architecture is §42's, not a new table of money: this tier publishes no currency, provider or
  checkout key anywhere in an answer, asserted by walking every answer's keys;
* each ceiling is one constant that publishes, guards and refuses with the same number (§49), tested at its edge
  and one past it; and somebody else's guide is answered as **absence**, never as a refusal that confirms it
  exists (§35's rule, and no 403 anywhere in this tier);
* the codes this tier answers with belong to it alone — the check that exists because §35's `no_such_member`
  collided with §39's at the same status, which `assemble()` cannot see.
* **reach is §35's predicate**, read from §35's table and not from a second one: a `followers` guide reaches its
  author and the accounts whose follow rows point at that author right now — on the shelf, at its own address and
  through its citations alike — and an unfollow withdraws it without deleting it;
* **the doors are walked as doors**: every private one answers 401 before any row is consulted, every published
  code is earned through a real request, and this tier answers no 403 anywhere.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1 import creator as creator_router
from app.core.db import SessionLocal
from app.main import app
from app.models import CommunityFollow, CreatorGuide, GuideCitation, KnowledgeChunk, KnowledgeDocument, User, utc_today
from app.services import entitlements as ent
from app.services.club import answers as project_answers
from app.services.creator import publishing as cre

TAG = uuid4().hex[:8]


@pytest.fixture()
def session() -> Iterator[Session]:
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _account(db: Session, name: str) -> User:
    """A creator is an account first. The email is unique per call because the run's database outlives one case."""
    tag = uuid4().hex[:8]
    row = User(id=f"usr_{name}_{tag}"[:40], email=f"{name}-{tag}-{TAG}@creator.test", password_hash="not-a-password-just-a-column", display_name=f"{name} {tag}")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def cast(session: Session) -> dict[str, User]:
    return {name: _account(session, name) for name in ("ada", "bo")}


def _passage(db: Session) -> KnowledgeChunk:
    """Cite the corpus as it is — the shipped documents are what a guide would really point at."""
    row = db.scalar(select(KnowledgeChunk).order_by(KnowledgeChunk.document_id, KnowledgeChunk.ordinal).limit(1))
    assert row is not None, "the test database holds no ingested chunks, so there is nothing to cite"
    return row


def _document(db: Session, passage: KnowledgeChunk) -> KnowledgeDocument:
    row = db.get(KnowledgeDocument, passage.document_id)
    assert row is not None
    return row


def _guide(db: Session, author: User, **kwargs: Any) -> dict[str, Any]:
    return cre.publish_guide(db, author.id, **{"section": "plan", "title": f"a frame {uuid4().hex[:6]}", **kwargs})["guide"]


def _refused(callable_: Any, code: str) -> cre.CreatorRefusal:
    with pytest.raises(cre.CreatorRefusal) as caught:
        callable_()
    assert caught.value.code == code, f"expected {code!r}, the door answered {caught.value.code!r}: {caught.value.message}"
    return caught.value


# ------------------------------------------------------------------ the shape of what is stored


def test_the_columns_a_guide_stores_are_the_minimisation_rule() -> None:
    """No column on either table could hold a passage's text, a token total or a count of anything."""
    guide_held = {str(column.name) for column in CreatorGuide.__table__.columns}
    citation_held = {str(column.name) for column in GuideCitation.__table__.columns}
    assert guide_held == {"id", "author_id", "slug", "title", "summary", "section", "visibility", "published_on", "data_origin", "is_demo_data", "created_at", "updated_at"}
    assert citation_held == {"id", "guide_id", "document_id", "ordinal", "cited_text_hash", "note", "data_origin", "is_demo_data", "created_at", "updated_at"}
    forbidden = {"text", "body", "chunk_id", "tokens", "citations", "moved", "reading_minutes", "price", "currency", "provider", "checkout"}
    assert not (guide_held | citation_held) & forbidden, f"{sorted((guide_held | citation_held) & forbidden)} would be a stored copy or a price"


def test_citing_a_passage_stores_its_address_and_its_hash_and_none_of_its_words(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, cast["ada"])
    answer = cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal, note="the part that matters")
    row = session.get(GuideCitation, answer["citation"]["id"])
    assert row is not None and row.document_id == document.id and row.ordinal == passage.ordinal
    assert answer["citation"]["document"] == document.slug, "the answer is the address `cite` accepts, not the key the row is filed under"
    assert cre.read_guide(session, guide["id"], cast["ada"].id)["passages"][0]["document"] == document.slug, "and the list answers that same address"
    assert row.cited_text_hash == passage.text_hash, "the witness is the hash that was there at citation time"
    stored = " ".join(str(getattr(row, name)) for name in ("note",))
    assert passage.text[:60] not in stored and passage.text[:60] not in session.get(CreatorGuide, guide["id"]).summary


def test_a_second_press_of_the_same_citation_is_one_row(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, cast["ada"])
    cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal)
    again = cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal, note="a second thought")
    assert again["citations"] == 1 == int(session.query(GuideCitation).filter_by(guide_id=guide["id"]).count())
    assert again["citation"]["note"] == "a second thought", "the second press edits the annotation, it does not stack a row"


def test_the_unique_constraint_is_what_makes_a_duplicate_citation_impossible(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, cast["ada"])
    session.add(GuideCitation(id=cre.new_public_id("cit"), guide_id=guide["id"], document_id=document.id, ordinal=passage.ordinal, cited_text_hash="", note="", data_origin="user", is_demo_data=False))
    session.commit()
    session.add(GuideCitation(id=cre.new_public_id("cit"), guide_id=guide["id"], document_id=document.id, ordinal=passage.ordinal, cited_text_hash="", note="", data_origin="user", is_demo_data=False))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# ------------------------------------------------------------------ every figure is counted, so the corpus can move


def test_the_token_figure_is_the_corpus_counted_again_and_drops_when_a_passage_goes(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, cast["ada"])
    cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal)
    first = cre.read_guide(session, guide["id"], cast["ada"].id)
    assert first["tokens"] == int(passage.token_estimate or 0) and first["citations"] == 1
    assert first["moved"] == 0, "nothing has moved yet, and the page must not imply otherwise"

    # the passage's text changes under the citation: the hash is the only thing that could notice
    passage.text_hash = "0" * 64
    session.commit()
    after = cre.read_guide(session, guide["id"], cast["ada"].id)
    assert after["moved"] == 1, "a stored count would still be insisting the passage is what was cited"
    assert after["citations"] == 1, "the citation is still there — `moved` says the text is not the one that was seen"


def test_the_subscriber_figure_is_the_other_tier_follow_rows_counted(session: Session, cast: dict[str, User]) -> None:
    cre.ensure_profile(session, cast["ada"].id, headline="a coach who writes things")
    session.add(CommunityFollow(id=cre.new_public_id("fol"), follower_id=cast["bo"].id, followee_id=cast["ada"].id, followed_on=utc_today().isoformat()))
    session.commit()
    profile = cre.profile(session, cast["ada"].id)
    assert profile["subscribers"] == 1 and profile["formulas"]["subscribers"] == cre.FORMULAS["subscribers"]
    assert profile["guides"] == 0, "a creator with no guide is a real state, not an empty answer"


# ------------------------------------------------------------------ ceilings, at their edge and past it


def test_the_guide_ceiling_accepted_at_its_edge_is_refused_one_past_it_with_its_own_figures(session: Session, cast: dict[str, User]) -> None:
    ada = cast["ada"]
    held = int(session.query(CreatorGuide).filter_by(author_id=ada.id).count())
    for index in range(cre.MAX_GUIDES_PER_CREATOR - held - 1):
        session.add(
            CreatorGuide(
                id=cre.new_public_id("guide"), author_id=ada.id, slug=f"filler-{index}-{TAG}", title=f"filler {index}", section="plan", visibility="public", published_on=utc_today().isoformat()
            )
        )
    session.commit()
    _guide(session, ada, title=f"the edge {uuid4().hex[:6]}")
    error = _refused(lambda: cre.publish_guide(session, ada.id, section="plan", title=f"one too many {uuid4().hex[:6]}"), "guide_limit")
    assert error.figures == {"held": cre.MAX_GUIDES_PER_CREATOR, "limit": cre.MAX_GUIDES_PER_CREATOR}


def test_the_citation_ceiling_refuses_with_the_number_it_publishes(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, cast["ada"])
    for index in range(cre.MAX_CITATIONS_PER_GUIDE):
        session.add(
            GuideCitation(id=cre.new_public_id("cit"), guide_id=guide["id"], document_id=document.id, ordinal=10_000 + index, cited_text_hash="", note="", data_origin="user", is_demo_data=False)
        )
    session.commit()
    error = _refused(lambda: cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal), "citation_limit")
    assert error.figures == {"held": cre.MAX_CITATIONS_PER_GUIDE, "limit": cre.MAX_CITATIONS_PER_GUIDE}


@pytest.mark.parametrize(
    ("verb", "code"),
    [("section", "guide_section"), ("title", "guide_title"), ("visibility", "guide_visibility"), ("document", "no_such_document"), ("ordinal", "citation_ordinal")],
)
def test_a_word_or_a_shape_the_door_does_not_know_is_refused_naming_what_it_knows(session: Session, cast: dict[str, User], verb: str, code: str) -> None:
    ada = cast["ada"]
    passage = _passage(session)
    document = _document(session, passage)
    guide = _guide(session, ada)
    if verb == "section":
        error = _refused(lambda: cre.publish_guide(session, ada.id, section="diet", title="x"), code)
        assert error.figures["sections"] == list(cre.GUIDE_SECTIONS)
    elif verb == "title":
        _refused(lambda: cre.publish_guide(session, ada.id, section="plan", title="   "), code)
    elif verb == "visibility":
        _refused(lambda: cre.publish_guide(session, ada.id, section="plan", title="x", visibility="nobody"), code)
    elif verb == "document":
        _refused(lambda: cre.cite(session, guide["id"], ada.id, document="a-slug-nobody-wrote", ordinal=0), code)
    else:
        _refused(lambda: cre.cite(session, guide["id"], ada.id, document=document.slug, ordinal="second"), code)
        _refused(lambda: cre.cite(session, guide["id"], ada.id, document=document.slug, ordinal=-1), code)
        _refused(lambda: cre.cite(session, guide["id"], ada.id, document=document.slug, ordinal=999_999), code)


# ------------------------------------------------------------------ reach, absence, and no 403


def test_an_unlisted_guide_is_readable_at_its_address_and_appears_in_no_listing(session: Session, cast: dict[str, User]) -> None:
    ada = cast["ada"]
    hidden = _guide(session, ada, visibility="unlisted")
    assert [item["id"] for item in cre.list_guides(session, ada.id)["items"] if item["id"] == hidden["id"]] == [], "a feed carries public guides only"
    assert cre.read_guide(session, hidden["id"], cast["bo"].id)["id"] == hidden["id"], "its own address is the door"


def test_a_followers_guide_reaches_exactly_the_accounts_whose_follow_rows_point_at_its_author(session: Session, cast: dict[str, User]) -> None:
    """`CAPS["visibility_rule"]` promises this in words, so the rows are read back against the sentence.

    Until this case existed the tier answered a `followers` guide to its author alone — a narrower rule than the one
    it published, on the shelf and at the address both, and the citations door did not ask at all. §35's own follow
    rows are the predicate, so the case writes one by hand and takes it away again.
    """
    ada, bo = cast["ada"], cast["bo"]
    guide = _guide(session, ada, visibility="followers")
    general = cre.list_guides(session, bo.id)["total"]

    # A stranger reaches neither the guide nor the addresses it cites, and sees no shelf of ada's at all.
    _refused(lambda: cre.read_guide(session, guide["id"], bo.id), "no_such_guide")
    _refused(lambda: cre.citations_view(session, guide["id"], bo.id), "no_such_guide")
    assert cre.list_guides(session, bo.id, creator=ada.id)["total"] == 0
    assert cre.read_guide(session, guide["id"], ada.id)["id"] == guide["id"], "the author never loses their own guide"

    row = CommunityFollow(id=cre.new_public_id("fol"), follower_id=bo.id, followee_id=ada.id, followed_on=utc_today().isoformat())
    session.add(row)
    session.commit()
    assert cre.read_guide(session, guide["id"], bo.id)["id"] == guide["id"]
    assert cre.citations_view(session, guide["id"], bo.id)["items"] == []
    assert cre.list_guides(session, bo.id, creator=ada.id)["total"] == 1
    assert cre.list_guides(session, bo.id)["total"] == general, "a follow row opens the author's shelf, not the general one"

    session.delete(row)
    session.commit()
    _refused(lambda: cre.read_guide(session, guide["id"], bo.id), "no_such_guide")
    assert cre.list_guides(session, bo.id, creator=ada.id)["total"] == 0
    assert cre.list_guides(session, bo.id)["total"] == general, "and the general shelf never moved"
    assert session.get(CreatorGuide, guide["id"]) is not None, "an unfollow withdraws the guide and deletes nothing"


def test_a_guide_that_is_not_yours_is_answered_as_absence_rather_than_as_a_refusal(session: Session, cast: dict[str, User]) -> None:
    passage = _passage(session)
    document = _document(session, passage)
    mine = _guide(session, cast["ada"])
    error = _refused(lambda: cre.cite(session, mine["id"], cast["bo"].id, document=document.slug, ordinal=passage.ordinal), "no_such_guide")
    assert error.figures["guide"] == mine["id"]
    _refused(lambda: cre.erase_guide(session, mine["id"], cast["bo"].id), "no_such_guide")
    assert session.get(CreatorGuide, mine["id"]) is not None, "and neither refusal wrote or erased anything"


def test_every_code_this_tier_answers_with_means_exactly_one_status_and_no_other_tier_owns_it() -> None:
    """Both halves of §51's promise, read off the shipped table and the shipped `TIERS`.

    The disjointness half exists because `assemble()` only refuses a code two tiers answer *differently*: §35 first
    registered `no_such_member`, which §39 already owned at the same 404, and nothing said so.
    """
    # The table is read as shipped, not as a subset assembled for this case: `creator` is registered in
    # `answers.TIERS` by the doors' commit, so a code that fell out of it would be answered 400 by omission.
    assert cre in project_answers.TIERS, "the tier is not registered, so its own door would answer every code with a 400"
    assert set(cre.REFUSALS) <= set(project_answers.ANSWERS)
    for code in cre.REFUSALS:
        expected = 404 if code in cre.NOT_FOUND_CODES else 422 if code in cre.UNPROCESSABLE_CODES else 409 if code in cre.CONFLICT_CODES else None
        assert expected is not None, f"{code} is published but in no set, so its status would be a fall-through"
        assert project_answers.ANSWERS[code] == expected, f"{code} is published as {expected} and the shipped table answers {project_answers.ANSWERS[code]}"
    assert not cre.FORBIDDEN_CODES, "403 is the permission matrix's meaning and this tier has no matrix"
    assert len(cre.REFUSALS) == len(set(cre.REFUSALS))
    for tier in project_answers.TIERS:
        if tier is cre:
            continue  # the census includes the counter: this tier's own codes are not somebody else's
        held = set(getattr(tier, "PUBLISHED", getattr(tier, "REFUSALS", ())) or ())
        shared = held & set(cre.REFUSALS)
        assert not shared, f"{sorted(shared)} belongs to {tier.__name__.rpartition('.')[2]} as well as to this tier"


def test_no_answer_in_this_tier_carries_a_money_shaped_key(session: Session, cast: dict[str, User]) -> None:
    """The claim `ff575a2` narrowed is held here: pricing lives in §42's rows, never in a payload."""
    passage = _passage(session)
    document = _document(session, passage)
    cre.ensure_profile(session, cast["ada"].id, slug=f"ada-{TAG}")
    guide = _guide(session, cast["ada"])
    cre.cite(session, guide["id"], cast["ada"].id, document=document.slug, ordinal=passage.ordinal)
    answers = [cre.rules(session), cre.list_guides(session, cast["ada"].id), cre.read_guide(session, guide["id"], cast["ada"].id), cre.profile(session, cast["ada"].id)]

    def names(node: Any) -> set[str]:
        if isinstance(node, dict):
            return set(node) | {found for value in node.values() for found in names(value)}
        if isinstance(node, list):
            return {found for value in node for found in names(value)}
        return set()

    forbidden = {"price", "currency", "amount", "provider", "checkout", "payout", "plan_id", "subscription"}
    for answer in answers:
        assert not names(answer) & forbidden, f"{sorted(names(answer) & forbidden)} would be a payment field the tier does not have"


def test_the_rulebook_publishes_the_vocabulary_the_guards_apply(session: Session) -> None:
    rules = cre.rules(session)
    assert rules["caps"]["guide_max"] == cre.MAX_GUIDES_PER_CREATOR and rules["caps"]["citation_max"] == cre.MAX_CITATIONS_PER_GUIDE
    assert sorted(rules["refusals"]) == sorted(cre.PUBLISHED)
    assert rules["formulas"] == cre.FORMULAS and rules["limitation"] == cre.LIMITATION
    assert cre.rules(session, ready=False)["counts"] == {"profiles": 0, "guides": 0, "citations": 0}


def test_the_features_the_rulebook_names_are_rows_this_platform_ships(session: Session) -> None:
    """`GET /creator/rules` names the features this tier publishes into §42's table, so the rows have to be there.

    A rulebook that named a feature the matrix does not carry would be a promise with no ceiling behind it, and the
    entitlements door would not know the name at all. The other half matters as much: no door refuses on these yet,
    so the meter must print them as ceilings the data holds rather than as rules.
    """
    body = TestClient(app).get("/api/v1/creator/rules").json()
    named = body["entitlement_features"]
    assert named == ["creator_publish", "creator_guide"]
    assert set(named) <= set(ent.FEATURES), f"the tier names {sorted(set(named) - set(ent.FEATURES))}, which the matrix does not carry"
    for plan in ent.PLANS:
        for feature in named:
            assert ent.DEFAULT_MATRIX[plan][feature][1] == ent.MONTH, f"{plan} has no monthly ceiling for {feature}"

    printed = {row["feature"]: row for row in ent.entitlements_view(session, "usr_never_here", plan=ent.DEFAULT_PLAN, subject_kind="user")["items"]}
    assert set(named) <= set(printed), "an account's own meter has to print the features this tier publishes into"
    assert all(printed[feature]["enforced"] is False for feature in named), "no door refuses on them yet, and the meter must not say otherwise"
    assert "no door refuses on yet" in body["limitation"], "the rulebook has to say which of its ceilings actually bites"


# ------------------------------------------------------------------ the doors


PASSWORD = "strong-pass-1234"

#: The public surface, named once, so a door added later is a private door until this line says otherwise.
PUBLIC_DOORS = frozenset({"/creator/rules"})


def _client(name: str) -> TestClient:
    """Its own client with its own registered account: this tier is made of accounts, so a door needs two."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"creator-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": name, "role": "player", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _actor_id(client: TestClient) -> str:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


def _detail(response: Any) -> Any:
    body = response.json()["detail"]
    assert isinstance(body, dict), f"a refusal must answer with the tier's own payload and figures, and this door sent {body!r}"
    return body


@pytest.fixture()
def voices() -> dict[str, TestClient]:
    """A fresh pair per case: the shelves and the reach these cases assert are exact, and an account shared between
    two of them would make each figure a claim about both."""
    return {"ada": _client("Ada Guide"), "bo": _client("Bo Reader")}


def _live_doors() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route in app.routes:
        path = str(getattr(route, "path", ""))
        if not path.startswith("/api/v1/creator"):
            continue
        for method in set(getattr(route, "methods", ()) or ()) - {"HEAD", "OPTIONS"}:
            routes.add((method, path))
    return routes


def test_the_guide_names_exactly_the_doors_that_are_routed() -> None:
    """Both directions, because the page that reaches these doors reads the guide to find them."""
    declared = {(entry["method"], f"/api/v1{entry['path']}") for entry in creator_router.ROUTE_GUIDE}
    assert len(creator_router.ROUTE_GUIDE) == len(declared), "two entries describe one door"
    live = _live_doors()
    assert declared == live, f"only in the guide: {sorted(declared - live)}; only routed: {sorted(live - declared)}"


def test_this_door_reads_the_same_object_the_club_doors_read() -> None:
    assert creator_router._ANSWERS is project_answers.ANSWERS, "the creator door assembled its own answer table again"


def test_the_one_public_door_prints_the_answers_it_will_give() -> None:
    response = TestClient(app).get("/api/v1/creator/rules")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["routes"] == [dict(item) for item in creator_router.ROUTE_GUIDE]
    assert body["refusal_answers"] == {code: project_answers.ANSWERS[code] for code in cre.REFUSALS}, "the rulebook printed a status the shipped table does not answer with"
    assert body["caps"]["sections"] == list(cre.GUIDE_SECTIONS) and body["caps"]["visibilities"] == list(cre.VISIBILITIES)
    assert set(body["counts"]) == {"profiles", "guides", "citations"}
    # The three ceilings behind these codes are row counts a caller cannot reach inside a test's budget; what a page
    # can check is that they are published with the status they earn, which the line above holds for all fifteen.
    assert all(body["refusal_answers"][code] == 409 for code in ("slug_taken", "guide_limit", "citation_limit"))


@pytest.mark.parametrize("door", [entry for entry in creator_router.ROUTE_GUIDE if entry["path"] not in PUBLIC_DOORS], ids=lambda entry: f"{entry['method']} {entry['path']}")
def test_a_caller_without_a_session_is_answered_401_before_any_row_is_consulted(door: dict[str, str]) -> None:
    """401 for ids that do not exist is the point: a 404 would mean the service ran first.

    Every private door is walked, derived from the guide rather than from a list written here, so a door added to the
    router cannot arrive unguarded — and none of them answers 403, which §51 reserves for the permission matrix.
    """
    path = door["path"].replace("{guide}", "guide_never_written").replace("{citation}", "cit_never_written").replace("{account}", "usr_never_here")
    client = TestClient(app)
    response = client.request(door["method"], f"/api/v1{path}", json={} if door["method"] == "POST" else None)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED, f"{door['method']} {path} answered {response.status_code}: {response.text}"
    assert _detail(response)["code"] == "unauthenticated"


def test_every_code_a_door_can_refuse_with_is_answered_with_the_status_the_table_publishes(voices: dict[str, TestClient], session: Session) -> None:
    ada, bo = voices["ada"], voices["bo"]
    passage = _passage(session)
    document = _document(session, passage)
    mine = ada.post("/api/v1/creator/guides", json={"section": "plan", "title": "a frame the reader can reach"}).json()["guide"]["id"]
    theirs = bo.post("/api/v1/creator/profile", json={}).json()["slug"]

    earned = [
        ("slug_taken", ada.post("/api/v1/creator/profile", json={"slug": theirs})),
        ("profile_headline", ada.post("/api/v1/creator/profile", json={"headline": "x" * (cre.PROFILE_HEADLINE_MAX + 1)})),
        ("profile_bio", ada.post("/api/v1/creator/profile", json={"bio": "x" * (cre.PROFILE_BIO_MAX + 1)})),
        ("guide_section", ada.post("/api/v1/creator/guides", json={"section": "squad", "title": "a slice no page can open"})),
        ("guide_title", ada.post("/api/v1/creator/guides", json={"section": "plan", "title": "   "})),
        ("guide_summary", ada.post("/api/v1/creator/guides", json={"section": "plan", "title": "a frame", "summary": "x" * (cre.GUIDE_SUMMARY_MAX + 1)})),
        ("guide_visibility", ada.post("/api/v1/creator/guides", json={"section": "plan", "title": "a frame", "visibility": "nobody"})),
        ("no_such_document", ada.post(f"/api/v1/creator/guides/{mine}/citations", json={"document": "no-such-document", "ordinal": 0})),
        ("citation_ordinal", ada.post(f"/api/v1/creator/guides/{mine}/citations", json={"document": document.slug, "ordinal": 10_000})),
        ("citation_note", ada.post(f"/api/v1/creator/guides/{mine}/citations", json={"document": document.slug, "ordinal": passage.ordinal, "note": "x" * (cre.CITATION_NOTE_MAX + 1)})),
        ("no_such_guide", ada.get("/api/v1/creator/guides/guide_never_written")),
        ("no_such_creator", ada.get("/api/v1/creator/profiles/usr_never_here")),
        ("no_such_citation", ada.delete(f"/api/v1/creator/guides/{mine}/citations/cit_never_written")),
    ]
    for code, response in earned:
        published = project_answers.ANSWERS[code]
        assert response.status_code == published, f"{code} is published as {published} and the door answered {response.status_code}: {response.text}"
        assert _detail(response)["code"] == code, f"the door answered {published} for the wrong reason: {_detail(response)}"


def test_amending_a_profile_writes_the_fields_that_were_sent_and_leaves_every_other_field_alone(voices: dict[str, TestClient]) -> None:
    """The guide this tier prints says this door amends a headline and a biography, and the page offers the button.

    The defect this holds: an account that had already published was answered 200 and no column was written, so
    "Amend profile" reported a change to a row it had not touched. Three facts pin the repair — the field that was
    sent moves, the field that was *not* sent keeps its value, and the address does not move at all.
    """
    ada = voices["ada"]
    first = ada.post("/api/v1/creator/profile", json={"slug": f"amend-{TAG}", "headline": "as first published", "bio": "the biography it started with"})
    assert first.status_code == 200, first.text
    assert first.json()["created"] is True and first.json()["headline"] == "as first published"

    amended = ada.post("/api/v1/creator/profile", json={"headline": "amended once"})
    assert amended.status_code == 200, amended.text
    assert amended.json()["created"] is False
    assert amended.json()["headline"] == "amended once", "the one field the caller sent did not move"
    assert amended.json()["bio"] == "the biography it started with", "a field the caller never named was blanked"
    assert amended.json()["slug"] == f"amend-{TAG}", "the address moved on an amendment, so a reader link would break"

    refused = ada.post("/api/v1/creator/profile", json={"headline": "half applied", "bio": "x" * (cre.PROFILE_BIO_MAX + 1)})
    assert refused.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY and _detail(refused)["code"] == "profile_bio", refused.text
    assert ada.get("/api/v1/creator/profile").json()["headline"] == "amended once", "a refused request still wrote the half of it that was valid"


def test_erasing_a_guide_through_the_door_takes_its_citations_and_answers_absence_to_everybody_else(voices: dict[str, TestClient], session: Session) -> None:
    ada, bo = voices["ada"], voices["bo"]
    passage = _passage(session)
    document = _document(session, passage)
    guide = ada.post("/api/v1/creator/guides", json={"section": "plan", "title": "a frame with one citation"}).json()["guide"]["id"]
    cited = ada.post(f"/api/v1/creator/guides/{guide}/citations", json={"document": document.slug, "ordinal": passage.ordinal})
    assert cited.status_code == 200, cited.text
    assert cited.json()["recorded_now"] is True and cited.json()["citations"] == 1
    assert ada.get(f"/api/v1/creator/guides/{guide}/citations").json()["total"] == 1

    theirs = bo.delete(f"/api/v1/creator/guides/{guide}")
    assert theirs.status_code == 404 and _detail(theirs)["code"] == "no_such_guide", "somebody else's guide is answered as absence"
    assert ada.get(f"/api/v1/creator/guides/{guide}").status_code == 200, "and the refusal erased nothing"

    erased = ada.delete(f"/api/v1/creator/guides/{guide}")
    assert erased.status_code == 200, erased.text
    assert erased.json()["erased"] == guide and erased.json()["citations"] == 1, "the answer says how many rows went with it"
    assert ada.get(f"/api/v1/creator/guides/{guide}").status_code == 404
    assert session.get(CreatorGuide, guide) is None
    assert list(session.scalars(select(GuideCitation).where(GuideCitation.guide_id == guide))) == []


def test_a_followers_guide_reaches_through_the_door_only_the_accounts_whose_follow_rows_point_at_the_author(voices: dict[str, TestClient]) -> None:
    """The wiring, not the arithmetic: the doors have to pass the caller as the reader — and §35's own follow door is
    what opens the guide, on the shelf and at its address and through its citations alike."""
    ada, bo = voices["ada"], voices["bo"]
    bo_id = _actor_id(bo)
    secret = bo.post("/api/v1/creator/guides", json={"section": "plan", "title": "only for the people who follow me", "visibility": "followers"}).json()["guide"]["id"]

    closed = ada.get(f"/api/v1/creator/guides/{secret}")
    assert closed.status_code == 404 and _detail(closed)["code"] == "no_such_guide", "a guide the reader cannot reach is answered as absence, not as a refusal"
    assert ada.get(f"/api/v1/creator/guides/{secret}/citations").status_code == 404, "the citations door asks the same predicate"
    assert ada.get(f"/api/v1/creator/guides?creator={bo_id}").json()["total"] == 0

    followed = ada.post(f"/api/v1/community/follows/{bo_id}")
    assert followed.status_code == 200, followed.text
    assert ada.get(f"/api/v1/creator/guides/{secret}").json()["id"] == secret
    assert ada.get(f"/api/v1/creator/guides/{secret}/citations").status_code == 200
    assert ada.get(f"/api/v1/creator/guides?creator={bo_id}").json()["total"] == 1
    assert bo.get(f"/api/v1/creator/guides/{secret}").status_code == 200, "the author never loses their own guide"

    withdrawn = ada.delete(f"/api/v1/community/follows/{bo_id}")
    assert withdrawn.status_code == 200, withdrawn.text
    assert ada.get(f"/api/v1/creator/guides/{secret}").status_code == 404
    assert bo.get(f"/api/v1/creator/guides/{secret}").status_code == 200
